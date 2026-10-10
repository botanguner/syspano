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
        kaynaklar = L.bul(desenler, journal=False)
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
        kaynaklar = L.bul([("apache", "Apache", yol), ("ozel", "Kopya", bag)], journal=False)
        assert len(kaynaklar) == 1, f"aynı dosya iki kez: {[k['yol'] for k in kaynaklar]}"


def test_bul_olmayan_deseni_sessizce_eler():
    assert L.bul([("php", "PHP", "/yok/boyle/*.log")], journal=False) == []


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
    kaynaklar = L.bul([("sunucu", "Kimlik", hedef)], journal=False)
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


# ─── journald kaynakları (dosya günlüğü olmayan servisler) ───────────────────
def _sahte_systemctl(units):
    """systemctl/journalctl çağrılarını taklit eder; çağrıları kaydeder."""
    cagrilar = []

    def sahte(cmd, zaman=8):
        cagrilar.append(list(cmd))
        if "show" in cmd:
            bloklar = []
            for ad, durum in units.items():
                bloklar.append(f"Id={ad}\nLoadState={durum[0]}\nActiveState={durum[1]}")
            return 0, "\n\n".join(bloklar)
        if "journalctl" in cmd:
            return 0, "2026-10-08 21:00:00 mariadb[1]: hazır"
        return 1, ""

    return sahte, cagrilar


def test_journal_kaynaklari_yalniz_calisan_birimleri_alir():
    from syspano.cihaz import servisler as S
    sahte, cagrilar = _sahte_systemctl({
        "mariadb.service": ("loaded", "active"),
        "postgresql.service": ("loaded", "inactive"),
        "mysql.service": ("not-found", "inactive"),
    })
    gercek = S._calistir
    S._calistir = sahte
    try:
        kaynaklar = L.journal_kaynaklari({})
    finally:
        S._calistir = gercek
    birimler = [k["birim"] for k in kaynaklar]
    assert "mariadb.service" in birimler, birimler
    assert "postgresql.service" not in birimler, "durmuş servis listeye girmemeli"
    assert "mysql.service" not in birimler, "kurulu olmayan servis girmemeli"
    assert all(k["tur"] == "journal" for k in kaynaklar)
    # keşif TEK çağrıyla yapılmalı (her birim için ayrı systemctl değil)
    assert sum(1 for c in cagrilar if "show" in c) == 1, cagrilar


def test_journal_kaynagi_dosyalardan_sonra_gelir():
    from syspano.cihaz import servisler as S
    sahte, _ = _sahte_systemctl({"mariadb.service": ("loaded", "active")})
    gercek = S._calistir
    S._calistir = sahte
    try:
        with tempfile.TemporaryDirectory() as d:
            yol = _yaz(d, "error.log", ["hata: bir şey"])
            kaynaklar = L.bul([("veritabani", "MySQL", yol)], ayar={})
    finally:
        S._calistir = gercek
    turler = [(k["grup"], k["tur"]) for k in kaynaklar]
    assert turler[0] == ("veritabani", "dosya"), turler
    assert turler[1] == ("veritabani", "journal"), turler
    assert kaynaklar[1]["etiket"] == "MariaDB"


def test_journal_kaynagi_yapilandirmayla_eklenir():
    from syspano.cihaz import servisler as S
    sahte, _ = _sahte_systemctl({"benim-servisim.service": ("loaded", "active")})
    gercek = S._calistir
    S._calistir = sahte
    try:
        kaynaklar = L.journal_kaynaklari({"log_dosyalari": ["journal:benim-servisim"]})
    finally:
        S._calistir = gercek
    ozel = [k for k in kaynaklar if k["grup"] == "ozel"]
    assert ozel and ozel[0]["birim"] == "benim-servisim.service", kaynaklar


def test_gunluk_journal_birim_ve_cekirdek():
    from syspano.cihaz import servisler as S
    sahte, cagrilar = _sahte_systemctl({})
    gercek = S._calistir
    S._calistir = sahte
    try:
        metin, kaynak = L.gunluk_journal("mariadb.service", 5)
        assert "mariadb" in metin and kaynak == "journalctl"
        assert any("mariadb.service" in c for c in cagrilar if "journalctl" in c)
        metin, kaynak = L.gunluk_journal(L.CEKIRDEK_BIRIMI, 7)
        assert kaynak == "journalctl -k"
        cekirdek_cagri = [c for c in cagrilar if "journalctl" in c and "-k" in c]
        assert cekirdek_cagri and "7" in cekirdek_cagri[0], cagrilar
    finally:
        S._calistir = gercek


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


def test_ozet_journal_zaman_penceresi():
    """journald sayımı son N dakikaya göre yapılmalı (--since ile)."""
    from syspano.cihaz import servisler as S
    cagrilar = []

    def sahte(cmd, zaman=10):
        cagrilar.append(list(cmd))
        return 0, "\n".join([
            "2026-10-08 23:00:00 mariadbd[1]: ready for connections",
            "2026-10-08 23:00:01 mariadbd[1]: ERROR: tablo bozuk",
            "2026-10-08 23:00:02 mariadbd[1]: [Warning] access denied",
        ])

    gercek = S._calistir
    S._calistir = sahte
    try:
        o = L.ozet_journal("mariadb.service", 15)
    finally:
        S._calistir = gercek
    assert o == {"hata": 1, "uyari": 1, "satir": 3, "pencere_dk": 15}, o
    komut = cagrilar[0]
    assert "--since" in komut and "-15min" in komut, komut
    assert "-u" in komut and "mariadb.service" in komut, komut


def test_ozet_journal_cekirdek_ve_varsayilan_pencere():
    from syspano.cihaz import servisler as S
    cagrilar = []
    gercek = S._calistir
    S._calistir = lambda cmd, zaman=10: (cagrilar.append(list(cmd)), (0, "bir hata"))[1]
    try:
        o = L.ozet_journal(L.CEKIRDEK_BIRIMI)
    finally:
        S._calistir = gercek
    assert o["pencere_dk"] == L.VARSAYILAN_PENCERE_DK == 60
    assert "-k" in cagrilar[0] and "-u" not in cagrilar[0], cagrilar[0]


def test_ozet_journal_hata_durumunda_sifir_doner():
    from syspano.cihaz import servisler as S
    gercek = S._calistir
    S._calistir = lambda cmd, zaman=10: (1, "")
    try:
        o = L.ozet_journal("yok.service", 60)
    finally:
        S._calistir = gercek
    assert o["hata"] == 0 and o["uyari"] == 0 and o.get("hata_mesaji")


# ─── dosya günlüklerinde zaman penceresi ─────────────────────────────────────
def test_satir_zamani_bicimleri():
    import time as _t
    iso = L.satir_zamani("[2026-10-10 12:48:12] production.ERROR: bağlantı yok")
    assert iso and abs(iso - _t.mktime((2026, 10, 10, 12, 48, 12, 0, 0, -1))) < 1
    egik = L.satir_zamani("2026/10/10 12:48:12 [error] 1#1: mesaj")
    assert egik and abs(egik - iso) < 1
    apache = L.satir_zamani("[Thu Oct 08 16:42:53.327959 2026] [ssl:warn] AH01906: x")
    assert apache and abs(apache - _t.mktime((2026, 10, 8, 16, 42, 53, 0, 0, -1))) < 1
    assert L.satir_zamani("damgasız satır") is None
    assert L.satir_zamani("") is None


def test_ozet_metin_penceresi():
    simdi = 1_800_000_000.0
    def damga(sn):
        import time as _t
        return _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(simdi - sn))
    metin = "\n".join([
        f"[{damga(30)}] ERROR: yeni hata",          # pencere içinde
        f"[{damga(60 * 55)}] ERROR: 55 dk önce",    # pencere içinde
        f"[{damga(60 * 90)}] ERROR: 90 dk önce",    # dışında → sayılmaz
        f"[{damga(60 * 90)}] WARNING: eski uyarı",  # dışında
        "damgasız ERROR satırı",                    # damgasız → sayılır
    ])
    o = L.ozet_metin(metin, 60, simdi)
    assert o["pencereli"] is True and o["damgali"] == 4, o
    assert (o["hata"], o["uyari"]) == (3, 0), o
    # hiç damga yoksa pencereli False
    o2 = L.ozet_metin("ERROR bir\nWARN iki", 60, simdi)
    assert o2["pencereli"] is False and o2["hata"] == 1 and o2["uyari"] == 1, o2


def test_ozet_dosya_pencereyi_uygular():
    import time as _t
    with tempfile.TemporaryDirectory() as d:
        simdi = _t.time()
        eski = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(simdi - 7200))
        yeni = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(simdi - 60))
        yol = _yaz(d, "error.log", [f"[{eski}] ERROR: eski hata",
                                    f"[{yeni}] ERROR: yeni hata",
                                    f"[{yeni}] [ssl:warn] uyarı"])
        o = L.ozet_dosya(yol, 60)
        assert o["pencereli"] is True and o["hata"] == 1 and o["uyari"] == 1, o


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
        d.log_kaynaklar = L.bul([("ozel", "Proje", yol)], journal=False)
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
