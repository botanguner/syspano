"""Günlük kaynakları (geliştirici log dosyaları) testleri.

Keşif, kuyruk okuma, hata/uyarı özeti, süzgeç ve önbellek davranışı sınanır.
Hepsi geçici dizinlerle çalışır: gerçek `/var/log` gerekmez, Tk gerekmez.
"""

import os

import tempfile
import time
from types import SimpleNamespace

from syspano.cihaz import loglar as L
from syspano.cihaz import ortak


def _yaz(klasor, ad, satirlar, satir_sonu="\n"):
    yol = os.path.join(klasor, ad)
    with open(yol, "w") as f:
        f.write(satir_sonu.join(satirlar) + satir_sonu)
    return yol


# ─── kuyruk (kuyruk okuma) ───────────────────────────────────────────────────
def test_kuyruk_son_satirlari_verir():
    with tempfile.TemporaryDirectory() as d:
        yol = _yaz(d, "buyuk.log", [f"satir-{i}" for i in range(500)])
        metin = ortak.kuyruk(yol, 5)
        assert metin.splitlines() == [f"satir-{i}" for i in range(495, 500)]


def test_kuyruk_satir_sonu_olmayan_dosya():
    with tempfile.TemporaryDirectory() as d:
        yol = os.path.join(d, "sonsuz.log")
        with open(yol, "w") as f:
            f.write("bir\niki\nuc")             # son satırda \n yok
        assert ortak.kuyruk(yol, 2).splitlines() == ["iki", "uc"]


def test_kuyruk_crlf_ve_bos_satirlari_temizler():
    with tempfile.TemporaryDirectory() as d:
        yol = _yaz(d, "windows.log", ["bir", "iki"], satir_sonu="\r\n")
        metin = ortak.kuyruk(yol, 10)
        assert metin.splitlines() == ["bir", "iki"]
        assert "\r" not in metin


def test_kuyruk_bayt_sinirini_asmaz():
    """Tek satırlık dev dosya belleği şişirmemeli (SD kartta okuma da sınırlı)."""
    with tempfile.TemporaryDirectory() as d:
        yol = os.path.join(d, "dev.log")
        icerik = "a" * 200_000
        with open(yol, "w") as f:
            f.write(icerik)
        metin = ortak.kuyruk(yol, 200, azami_bayt=4096)
        assert len(metin) <= 4096, f"{len(metin)} bayt okundu"
        assert metin == icerik[-len(metin):], "dosyanın SONU okunmalı"


def test_kuyruk_olmayan_dosya_mesaj_dondurur():
    metin = ortak.kuyruk("/yok/boyle/bir/dosya.log", 5)
    assert metin.startswith("(okunamadı")


# ─── keşif ───────────────────────────────────────────────────────────────────
def test_bul_desenleri_genisletir_ve_siralar():
    with tempfile.TemporaryDirectory() as d:
        php = _yaz(d, "php8.2-fpm.log", ["x"])
        apache = _yaz(d, "error.log", ["y"])
        _yaz(d, "ilgisiz.txt", ["z"])
        desenler = [("apache", "Apache", os.path.join(d, "err*.log")),
                    ("php", "PHP-FPM", os.path.join(d, "php*-fpm.log"))]
        kaynaklar = L.bul(desenler)
        assert [k["etiket"] for k in kaynaklar] == ["PHP-FPM", "Apache"], \
            "grup sırası korunmalı (php önce)"
        yol = {k["yol"] for k in kaynaklar}
        assert yol == {php, apache}
        k = kaynaklar[0]
        assert k["boyut"] == 2 and k["okunabilir"] is True
        assert abs(k["son"] - time.time()) < 60


def test_bul_ayni_dosyayi_iki_kez_saymaz():
    with tempfile.TemporaryDirectory() as d:
        yol = _yaz(d, "error.log", ["x"])
        bag = os.path.join(d, "kopya.log")
        os.symlink(yol, bag)
        kaynaklar = L.bul([("apache", "Apache", yol), ("ozel", "Kopya", bag)])
        assert len(kaynaklar) == 1, f"aynı dosya iki kez: {[k['yol'] for k in kaynaklar]}"


def test_bul_olmayan_deseni_sessizce_eler():
    assert L.bul([("php", "PHP", "/yok/boyle/*.log")]) == []


def test_okunamayan_dosya_izin_yok_der_ve_kartta_isaretlenir():
    if os.geteuid() == 0:
        print("    (root — izin testi atlandı)")
        return
    hedef = "/etc/shadow"
    if not os.path.exists(hedef):
        print("    (/etc/shadow yok — atlandı)")
        return
    metin, kaynak = L.gunluk(hedef, 5)
    assert kaynak == "izin yok", kaynak
    assert "usermod" in metin, "çözüm önerisi yok"
    kaynaklar = L.bul([("sunucu", "Kimlik", hedef)])
    assert kaynaklar and kaynaklar[0]["okunabilir"] is False


def test_gunluk_olmayan_dosya():
    metin, kaynak = L.gunluk("/yok/boyle/x.log", 5)
    assert kaynak == "yok" and "dosya yok" in metin


def test_desenler_yapilandirmayi_ekler():
    ayar = {"log_dosyalari": ["~/projelerim/*/storage/logs/*.log",
                              "/tmp/ozel.log"]}
    hepsi = L.desenler(ayar)
    eklenen = [x for x in hepsi if x[0] == "ozel"]
    assert len(eklenen) == 2
    assert ("ozel", "logs/*.log", "~/projelerim/*/storage/logs/*.log") in hepsi
    assert ("ozel", "ozel.log", "/tmp/ozel.log") in hepsi
    assert all(etiket and "*" not in etiket[:1] for _, etiket, _ in eklenen)


def test_desenler_kendi_dosyalarimizi_bulur():
    """Kullanıcının eklediği desen keşifte gerçekten bulunuyor mu?"""
    with tempfile.TemporaryDirectory() as d:
        yol = _yaz(d, "proje.log", ["bir hata: error"])
        ayar = {"log_dosyalari": [os.path.join(d, "*.log")]}
        ozel = [k for k in L.bul(L.desenler(ayar)) if k["grup"] == "ozel"]
        assert [k["yol"] for k in ozel] == [yol]


# ─── özet ve süzgeç ──────────────────────────────────────────────────────────
def test_ozet_hata_ve_uyari_sayar():
    metin = "\n".join([
        "2026-10-08 21:31:03 production.ERROR: SQLSTATE bağlantı yok",
        "2026-10-08 21:31:04 PHP Warning: Undefined variable $x",
        "[notice] Apache/2.4 yapılandırma tamam",
        "2026-10-08 21:31:05 istek tamamlandı",
        "2026-10-08 21:31:06 PHP Fatal error: Allowed memory size exhausted",
    ])
    ozet = L.ozet(metin)
    assert ozet == {"hata": 2, "uyari": 2}, ozet


def test_suz_yalniz_hata_ve_uyari_birakir():
    metin = "bilgi satiri\nerror: bozuk\nwarn: yavaş\nnormal"
    s = L.suz(metin, True)
    assert s.splitlines() == ["error: bozuk", "warn: yavaş"]
    assert L.suz(metin, False) == metin


# ─── toplayıcı arayüzü (önbellek) ────────────────────────────────────────────
def _durum():
    return SimpleNamespace(log_kaynaklar=None, log_kesif=0.0, log_son=0.0, log_sonuc={})


def test_oku_kesfi_onbellekler():
    d = _durum()
    ilk = L.oku(d, {})
    assert "kaynaklar" in ilk and isinstance(ilk["yok"], bool)
    assert d.log_kaynaklar is not None, "keşif sonucu saklanmalı"

    # keşif ömrü dolmadıysa yeniden taranmaz: sahte (var olmayan) listeyle kanıtla
    d.log_kaynaklar = [{"grup": "php", "etiket": "PHP", "ad": "x.log",
                        "yol": "/yok/x.log", "boyut": 1, "son": 1.0,
                        "okunabilir": True}]
    d.log_son = 0.0
    sonuc = L.oku(d, {})
    assert sonuc["yok"] is True, "keşif yeniden çalıştı (önbellek çalışmıyor)"


def test_oku_stat_araliginda_aynı_sonucu_dondurur():
    d = _durum()
    L.oku(d, {})
    ilk_sonuc = d.log_sonuc
    assert L.oku(d, {}) is ilk_sonuc, "5 saniye dolmadan yeniden stat yapılmamalı"


def test_oku_dosya_kaybolunca_listeden_duser():
    with tempfile.TemporaryDirectory() as klasor:
        yol = _yaz(klasor, "proje.log", ["x"])
        d = _durum()
        d.log_kaynaklar = L.bul([("ozel", "Proje", yol)])
        d.log_kesif = ortak.zaman()          # keşif taze; yeniden taranmasın
        assert len(d.log_kaynaklar) == 1
        os.unlink(yol)
        sonuc = L.oku(d, {})
        assert sonuc["kaynaklar"] == [] and sonuc["yok"] is True


if __name__ == "__main__":
    import sys
    import traceback
    gecen, kalan = 0, 0
    for ad, fonk in sorted(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            try:
                fonk()
                print(f"  ✓ {ad}")
                gecen += 1
            except Exception:
                print(f"  ✗ {ad}")
                traceback.print_exc()
                kalan += 1
    print(f"\n{gecen} geçti, {kalan} kaldı")
    sys.exit(1 if kalan else 0)
