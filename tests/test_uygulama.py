"""Uygulama duman testi: pano kurulur, çizilir, büyüteç ve terminal denenir.

Tk bir görüntü gerektirir (X11/Xwayland); yoksa test atlanır. Pencere gizli
tutulur, ana döngü elle adımlanır.
"""

import os
import time

from syspano import ortam
from syspano.arayuz import kartlar as kartlar_modul


def _pano_olustur(**ek):
    import tkinter as tk
    from syspano.arayuz.pano import Pano
    ayar = {"pencere": [900, 560], "kartlar": ["cpu", "bellek", "sicaklik", "pil",
                                              "cekirdek", "disk_ag", "servisler", "surecler"],
            "buyutec": True, "guncelleme_ms": 400, "tepsi": False}
    ayar.update(ek)
    try:
        tk.Tk().destroy()
    except Exception as hata:
        print(f"atlandı (görüntü yok: {hata})")
        return None
    p = Pano(ayar, cikis=None, mod="pencere")
    p.kok.withdraw()
    return p


def _veri_bekle(pano, sn=4.0):
    """İlk veri örneği gelene kadar bekle.

    Toplayıcı ilk örneği üretmeden pano hiçbir kare çizmez (`if not v: return`),
    bu yüzden çizime bağlı iddialar veri gelmeden kurulmamalı.
    """
    son = time.monotonic() + sn
    while time.monotonic() < son:
        if pano.t.al():
            return True
        pano.kok.update()
        time.sleep(0.05)
    return bool(pano.t.al())


def _metinler(pano, aranan=None, sn=2.0):
    """Canvas'taki yazıları döndürür; `aranan` verilirse görünene kadar bekler."""
    son = time.monotonic() + sn
    while True:
        pano.ciz()
        pano.kok.update()
        metinler = [pano.c.itemcget(o, "text") for o in pano.c.find_all()
                    if pano.c.type(o) == "text"]
        if aranan is None or aranan in metinler or time.monotonic() > son:
            return metinler
        time.sleep(0.05)


def _bekle(pano, sn=1.4):
    son = time.monotonic() + sn
    while time.monotonic() < son:
        pano.kok.update()
        time.sleep(0.05)


def test_pano_cizilir():
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p)
        assert p.c.find_all(), "tuval boş"
        plan = p._plan(p.t.al())
        assert plan and plan["kartlar"], "yerleşim boş"
        p.ciz()
        p.kok.update()
        assert not p._max_kaydir or p._max_kaydir >= 0
    finally:
        p.kapat()


def test_buyutec():
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.2)
        p.mercek = (p.w // 2, p.h // 2)
        p._mercek_ciz(p.t.al())
        assert p.c.find_withtag("mercek"), "büyüteç çizilmedi"
        # bekçi zamanlayıcı (imleç yok) büyüteci gizlemeli
        p.mercek_yer = None
        p._mercek_denetle()
        assert not p.c.find_withtag("mercek"), "büyüteç gizlenmedi"
    finally:
        p.kapat()


def test_terminal_gecisi():
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.0)
        p.gorunum_degistir("terminal")
        assert p.terminal is not None, "terminal başlamadı"
        p.terminal.baslat()
        _bekle(p, 1.0)
        p.gorunum_degistir("pano")
        assert p.gorunum == "pano"
    finally:
        p.kapat()


def test_kaydirma():
    p = _pano_olustur(kartlar=None)
    if p is None:
        return
    try:
        _bekle(p, 1.2)
        p.ciz()
        if p._max_kaydir > 0:
            p.kaydir = p._max_kaydir
            p.ciz()
            assert abs(p.cek.kaydir - p._max_kaydir) < 1
    finally:
        p.kapat()


def test_buyutec_karari():
    """'auto' modu fare yokken kapanmalı, elle verilen değerler korunmalı."""
    p = _pano_olustur()
    if p is None:
        return
    try:
        eski = ortam.goreli_isaretci_var
        try:
            p.ayarlar["buyutec"] = "auto"
            ortam.goreli_isaretci_var = lambda: False
            karar, neden = p._buyutec_karar()
            assert karar is False, "fare yokken büyüteç açık kaldı"
            assert "fare" in neden
            ortam.goreli_isaretci_var = lambda: True
            assert p._buyutec_karar()[0] is True
        finally:
            ortam.goreli_isaretci_var = eski
        p.ayarlar["buyutec"] = False
        assert p._buyutec_karar()[0] is False
        p.ayarlar["buyutec"] = True
        assert p._buyutec_karar()[0] is True
    finally:
        p.kapat()


def test_buyutec_gercek_hareket_ister():
    """Fare oynamadan büyüteç belirmemeli; dokunma/tıklama onu kapatmalı."""
    p = _pano_olustur(buyutec=True)
    if p is None:
        return
    try:
        _bekle(p, 1.0)
        p.mercek = None
        p.mercek_yer = (p.w // 2, p.h // 2)
        p.mercek_zaman = time.monotonic() - 5
        p._mercek_denetle()
        assert p.mercek is None, "hareket olmadan büyüteç belirdi"

        class Olay:
            pass

        o = Olay()
        o.x, o.y = 200, 200
        p._fare(o)                       # ilk olay: hareket sayılmaz
        o.x, o.y = 260, 240
        p._fare(o)                       # imleç gerçekten oynadı
        assert p._gercek_hareket is True
        p.mercek_zaman = time.monotonic() - 5
        p._mercek_denetle()
        assert p.mercek == (260, 240), "hareketten sonra büyüteç belirmedi"

        p._basildi(o)                    # tıklama/dokunma büyüteci kapatır
        assert p.mercek is None
        assert p._gercek_hareket is False

        # imleç pencereden çıkınca sıfırlanır
        p._fare_cikti()
        assert p.mercek_yer is None and p._fare_son is None
    finally:
        p.kapat()


def test_ayar_ekrani_dokunma():
    """Ayar ekranında dokunma: anahtar ve tema değişmeli, yapılandırmaya yazılmalı."""
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.environ["SYSPANO_YAPILANDIRMA_DIZINI"] = d
        p = None
        try:
            p = _pano_olustur(terminal=True, tema="koyu")
            if p is None:
                return
            _bekle(p, 1.0)
            p.gorunum_degistir("ayar")
            assert p._ayar_plan and p._ayar_plan["kutular"], "ayar yerleşimi yok"

            def dokun(rect):
                """Tasarım dikdörtgeninin ortasına dokunma olayı üret."""
                x, y, w, h = rect
                dx, dy = x + w / 2, y + h / 2

                class Olay:
                    pass

                o = Olay()
                o.x = int(dx * p.S)
                o.y = int(dy * p.S - p.kaydir)
                p._basildi(o)
                p._birakildi(o)

            # 1) terminal anahtarını kapat
            kutu = p._ayar_kutusu("terminal")
            assert kutu and kutu["deger"] is True
            dokun(kutu["anahtar"])
            assert p.ayarlar["terminal"] is False, "terminal anahtarı değişmedi"

            # 2) tema seçeneği
            kutu = p._ayar_kutusu("tema")
            acik = [r for dg, _e, r in kutu["secenekler"] if dg == "acik"][0]
            dokun(acik)
            assert p.ayarlar["tema"] == "acik"
            assert p.R["ad"] == "acik", "tema canlı uygulanmadı"

            # 3) kart anahtarını kapat
            kutu = p._ayar_kutusu("kart:cekirdek")
            assert kutu and kutu["deger"] is True
            dokun(kutu["anahtar"])
            assert "cekirdek" not in p.ayarlar["kartlar"]

            # yapılandırma dosyasına yazıldı mı?
            with open(os.path.join(d, "config.json")) as f:
                kayitli = json.load(f)
            assert kayitli.get("tema") == "acik", kayitli
            assert kayitli.get("terminal") is False, kayitli
            assert "cekirdek" not in (kayitli.get("kartlar") or []), kayitli

            # 4) "Oto" düğmesi ölçeği DPI otomatiğine döndürmeli
            p.ayarlar["olcek"] = 1.9
            p._ayar_isle("olcek_oto", "dugme", None)
            assert p.ayarlar["olcek"] is None

            # 5) ölçek değişince tasarım uzayı güncellenmeli
            onceki = p.tasarim_g
            p._ayar_isle("olcek", "sec", 1.6)
            assert p.ayarlar["olcek"] == 1.6
            assert p.tasarim_g != onceki
            assert abs(p.cek.S - p.S) < 1e-9

            # 6) kaydırdıktan sonra dokunma yine doğru öğeye isabet etmeli
            p.kaydir = min(150.0, p._max_kaydir)
            p.ciz()
            p.kok.update()
            assert p.kaydir > 0, "kaydırma uygulanmadı"
            kutu = p._ayar_kutusu("kart:surecler")
            assert kutu and kutu["deger"] is True
            dokun(kutu["anahtar"])
            assert "surecler" not in p.ayarlar["kartlar"], "kaydırmadan sonra yanlış öğe"
        finally:
            os.environ.pop("SYSPANO_YAPILANDIRMA_DIZINI", None)
            if p is not None:
                p.kapat()


def _bekleyen_zamanlayici(p):
    """Panoda bekleyen `after` sayısı (çizim döngüsü çoğalıyor mu?)."""
    try:
        return len(p.kok.tk.call("after", "info"))
    except Exception:
        return -1


def test_kare_degistirme_ogeleri_biriktirmez():
    """Yeni kare eskisi dururken çizilir; eski öğeler silinmeli.

    (Bu yöntem Tk'de silme-sonrası-çizim bedelini kaldırır — ölçüm: kare
    başına 20,6 ms → 3,6 ms. Öğe birikirse bellek ve çizim süresi büyür.)
    """
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.2)
        p.ciz()
        p.kok.update()
        ilk = len(p.c.find_all())
        assert ilk > 20, f"beklenenden az öğe: {ilk}"
        for _ in range(25):
            p.ciz()
        p.kok.update()
        son = len(p.c.find_all())
        assert son <= ilk + 5, f"kare öğeleri birikiyor: {ilk} → {son}"
        # içerik ve kare etiketleri yerinde mi?
        assert p.c.find_withtag("kare"), "kare etiketi yok"
        assert p.c.find_withtag("icerik"), "içerik etiketi yok"
    finally:
        p.kapat()


def test_pencere_gizliyken_cizilmez():
    """Pencere gizliyken (tepsiden saklandı) çizim yapılmamalı."""
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.0)
        p.ciz()
        p.kok.update()
        p.gizle()
        once = len(p.c.find_all())
        p.ciz()
        p.kok.update()
        assert len(p.c.find_all()) == once, "gizliyken de çiziliyor"
    finally:
        p.kapat()


def test_cizim_dongusu_cogalmaz():
    """Elle tetiklenen çizimler zamanlayıcı biriktirmemeli.

    Bir dönem `ciz()` her çağrısında yeni bir döngü kuruyordu; kaydırma her
    parmak hareketinde `ciz()` çağırdığı için saniyede onlarca çizim döngüsü
    birikiyor ve pano (özellikle Pi'de) kilitleniyordu.
    """
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.0)
        once = _bekleyen_zamanlayici(p)
        assert once > 0, "çizim döngüsü hiç kurulmamış"
        for _ in range(12):
            p.ciz()
        sonra = _bekleyen_zamanlayici(p)
        assert sonra <= once + 1, f"çizim zamanlayıcıları çoğalıyor: {once} → {sonra}"
    finally:
        p.kapat()


def test_surukleyerek_kaydirma():
    """Parmakla kaydırma: içerik takip etmeli, zamanlayıcı çoğalmamalı."""
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.2)
        p.gorunum_degistir("ayar")
        p.ciz()
        p.kok.update()
        assert p._max_kaydir > 0, "ayar ekranı kaydırılabilir olmalı"
        assert p.c.find_withtag("icerik"), "içerik etiketi yok (kaydırma çalışmaz)"

        class Olay:
            pass

        o = Olay()
        o.x, o.y = 100, 300
        p._basildi(o)
        once = _bekleyen_zamanlayici(p)
        for adim in range(0, 200, 10):        # parmağı yukarı sürükle
            o.y = 300 - adim
            p._surukle(o)
            p.kok.update()
        o.y = 100
        p._surukle(o)                         # son hareket
        p._birakildi(o)
        p.kok.update()

        assert abs(p.kaydir - 200) < 2, f"kaydırma konumu {p.kaydir}"
        assert p.kaydir <= p._max_kaydir
        sonra = _bekleyen_zamanlayici(p)
        assert sonra <= once + 1, f"sürükleme zamanlayıcı biriktirdi: {once} → {sonra}"
    finally:
        p.kapat()


def test_servis_karti_ve_gunluk():
    """Servis satırları tıklanabilir olmalı; günlük başlığı şeride binmemeli."""
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 3.5)                       # servis keşfi ilk çağrıda yapılır
        v = p.t.al()
        s = v.get("servisler") or {}
        if s.get("yok") or not s.get("birimler"):
            print("    (systemd/servis yok — atlandı)")
            return
        p.ciz()
        p.kok.update()
        assert kartlar_modul.TIKLANABILIR, "servis satırları tıklanabilir değil"
        eylem, _kutu = kartlar_modul.TIKLANABILIR[0]
        assert eylem[0] == "log", f"beklenmeyen eylem: {eylem}"

        p.log_ac(eylem[1])
        p.ciz()
        p.kok.update()
        assert p.gorunum == "log", "günlük görünümü açılmadı"
        assert p.log_metin is not None

        S = p.S
        serit = 46 * S
        for oge in p.c.find_all():
            if p.c.type(oge) != "text":
                continue
            metin = p.c.itemcget(oge, "text")
            if metin in ("⟳ Yenile", str(p.log_birim)):
                ust = p.c.bbox(oge)[1]
                assert ust >= serit - 2, f"'{metin}' üst şeridin üstüne biniyor (y={ust})"
        # günlük satırları başlığın altında başlamalı
        merkezler = sorted((p.c.bbox(o)[1] + p.c.bbox(o)[3]) / 2
                           for o in p.c.find_all()
                           if p.c.type(o) == "text"
                           and p.c.itemcget(o, "text")[:1].isdigit())
        if merkezler:
            assert merkezler[0] >= p.LOG_UST * S - 2, \
                f"günlük satırları başlığın altına taşmıyor (ilk {merkezler[0]:.0f})"
        # panoya dönüş
        p.gorunum_degistir("pano")
        assert p.gorunum == "pano"
    finally:
        p.kapat()


def test_gunluk_karti_ve_dosya_goruntuleyici():
    """GÜNLÜKLER kartı dosya satırları tıklanabilir olmalı; süzgeç çalışmalı."""
    import tempfile
    p = _pano_olustur(kartlar=["cpu", "bellek", "servisler", "loglar"])
    if p is None:
        return
    yol = None
    try:
        _bekle(p, 1.2)
        assert _veri_bekle(p), "toplayıcı veri üretmedi"
        p.ciz()
        p.kok.update()
        v = p.t.al()
        d = v.get("loglar") or {}
        if not d.get("yok") and d.get("kaynaklar"):
            eylemler = [e[0] for e in kartlar_modul.TIKLANABILIR]
            assert ("log_dosya", d["kaynaklar"][0]["yol"]) in eylemler, eylemler

        # geçici bir günlük dosyasını görüntüleyicide aç
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False,
                                         encoding="utf-8") as f:
            f.write("2026-10-08 21:31:00 bilgi: sunucu başladı\n")
            f.write("2026-10-08 21:31:01 production.ERROR: bağlantı kurulamadı\n")
            f.write("2026-10-08 21:31:02 PHP Warning: Undefined variable $x\n")
            yol = f.name
        p.log_ac_dosya(yol)
        _bekle(p, 0.6)                       # çizim döngüsü birkaç kare çizsin
        p.ciz()
        p.kok.update()
        assert p.gorunum == "log", "dosya günlüğü açılmadı"
        assert p.log_tip == "dosya"
        assert len(p._log_satirlar()) == 3, p._log_satirlar()
        assert p.log_ozet["hata"] == 1 and p.log_ozet["uyari"] == 1, p.log_ozet
        assert any(e[0][0] == "log_suz" for e in kartlar_modul.TIKLANABILIR), \
            f"süzgeç düğmesi yok: {[e[0] for e in kartlar_modul.TIKLANABILIR]}"

        p.log_suz = True
        satirlar = p._log_satirlar()
        assert len(satirlar) == 2, f"süzgeç süzmedi: {satirlar}"
        assert all(("ERROR" in s or "Warning" in s) for s in satirlar)
        p.log_suz = False
        assert len(p._log_satirlar()) == 3
        p.gorunum_degistir("pano")
    finally:
        if yol:
            os.unlink(yol)
        p.kapat()


def test_guncelleme_denetim_akisi():
    """«Güncellemeyi denetle» akışı: denetleniyor → sonuç görünür olmalı.

    Alt süreç sahte: denetimin kendisi değil, panonun durumu nasıl gösterdiği
    sınanır (kullanıcının şikâyeti: sonuç belli olmuyordu).
    """
    import tempfile

    import syspano.arayuz.pano as pano_mod
    from syspano import guncelleme

    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        try:
            p = _pano_olustur(kartlar=["cpu"], guncelleme_denetimi=False)
            if p is None:
                return
            gercek = pano_mod.subprocess.Popen
            pano_mod.subprocess.Popen = lambda *a, **k: None
            try:
                # 1) denetle: durum "denetleniyor" olmalı
                p._dugme_isle("guncelle_denetle")
                durum = p._ayar_durumu()["guncelleme"]
                assert "Denetleniyor" in durum["metin"], durum
                assert durum["renk"] == "mavi"
                assert p._denetim_bekliyor > 0, "denetim durumu işaretlenmedi"

                # 2) önbellek tazelendi → sonuç hem satırda hem bildirimde
                guncelleme._denetim_yaz({"zaman": time.time(), "yeni": False,
                                         "yerel": guncelleme.yerel_surum()})
                p._denetim_sonuc_bekle()
                assert p._denetim_bekliyor == 0, "denetim durumu temizlenmedi"
                durum = p._ayar_durumu()["guncelleme"]
                assert "Güncel" in durum["metin"] and durum["renk"] == "yesil"
                assert "Güncel" in p.bildiri, f"bildirim yok: {p.bildiri!r}"

                # 3) yeni sürüm: ⚙ noktası yanar, satır sarı olur
                guncelleme._denetim_yaz({"zaman": time.time(), "yeni": True,
                                         "depo_surum": "9.9.9"})
                p._guncelleme_var_guncelle()
                assert p._guncelleme_var is True, "⚙ uyarı noktası yanmadı"
                durum = p._ayar_durumu()["guncelleme"]
                assert "9.9.9" in durum["metin"] and durum["renk"] == "sari"

                # 4) zaman aşımı: önbellek tazelenmediyse kırmızı uyarı
                try:
                    os.remove(guncelleme.denetim_yolu())
                except OSError:
                    pass
                p._denetim_bekliyor = time.time() - 60
                p._denetim_sonuc_bekle()
                durum = p._ayar_durumu()["guncelleme"]
                assert "zaman aşımı" in durum["metin"] and durum["renk"] == "kirmizi"
            finally:
                pano_mod.subprocess.Popen = gercek
                p.kapat()
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_gunluk_goruntuleyici_journal_kaynagi():
    """journald kaynağı (MariaDB gibi) da aynı görüntüleyicide açılmalı."""
    from syspano.cihaz import loglar as loglar_mod
    p = _pano_olustur(kartlar=["cpu", "loglar"], guncelleme_denetimi=False)
    if p is None:
        return
    gercek = loglar_mod.gunluk_journal
    loglar_mod.gunluk_journal = lambda birim, satir=200: (
        "2026-10-08 21:00:00 mariadb[1]: hazır\n"
        "2026-10-08 21:01:00 mariadb[1]: ERROR: tablo bozuk\n", "journalctl")
    try:
        assert _veri_bekle(p), "toplayıcı veri üretmedi"
        p.log_ac_journal("mariadb.service", "MariaDB")
        assert p.gorunum == "log" and p.log_tip == "journal"
        assert len(p._log_satirlar()) == 2, p._log_satirlar()
        assert p.log_ozet["hata"] == 1, p.log_ozet
        metinler = _metinler(p, "MariaDB")
        assert "MariaDB" in metinler, "okunur ad başlıkta yok"
        assert any("mariadb.service" in m for m in metinler), "birim adı yok"
        assert any("son 60 dk" in m for m in metinler), \
            f"zaman penceresi başlıkta yok: {metinler}"
        p.gorunum_degistir("pano")
    finally:
        loglar_mod.gunluk_journal = gercek
        p.kapat()


def test_servis_dugmeleri_eyleme_gider():
    """BAŞLATMA düğmeleri servis modülüne gitmeli; devralmada bildirim çıkmalı."""
    from syspano import baslatma
    p = _pano_olustur(kartlar=["cpu"], guncelleme_denetimi=False)
    if p is None:
        return
    gercek = {ad: getattr(baslatma, ad) for ad in
              ("servis_kur", "servis_eylemi", "servis_durum")}
    cagrilar = []
    baslatma.servis_kur = lambda komut=None: (cagrilar.append("kur"),
                                              (True, "Servis kuruldu"))[1]
    baslatma.servis_eylemi = lambda eylem: (cagrilar.append(eylem),
                                            (True, f"{eylem} tamam"))[1]
    baslatma.servis_durum = lambda taze=False: {"etkin": True, "kurulu": True,
                                                "durum": "active", "pid": 42}
    try:
        p._dugme_isle("servis_kur")
        assert cagrilar == ["kur"], cagrilar
        assert "devrediliyor" in p.bildiri, p.bildiri
        p._dugme_isle("servis_yeniden")
        assert cagrilar == ["kur", "yeniden"], cagrilar
        p._dugme_isle("servis_durdur")
        assert cagrilar[-1] == "durdur" and "kapan" in p.bildiri, p.bildiri
        baslatma.servis_eylemi = lambda eylem: (False, "systemctl hatası")
        p._dugme_isle("servis_baslat")
        assert "hata" in p.bildiri, p.bildiri
    finally:
        for ad, fonk in gercek.items():
            setattr(baslatma, ad, fonk)
        p.kapat()


def test_servis_listesi_gorunumu():
    """'+N servis daha' → tüm servisler kaydırmalı listede; satır dokunuşu günlüğü açar."""
    p = _pano_olustur(kartlar=["cpu", "servisler"], guncelleme_denetimi=False)
    if p is None:
        return
    try:
        assert _veri_bekle(p), "toplayıcı veri üretmedi"
        p._servis_liste = [
            {"ad": "apache2.service", "etiket": "Apache", "durum": "active",
             "baslama": time.time() - 3600, "bellek": 12_000_000},
            {"ad": "nginx.service", "etiket": "nginx", "durum": "failed"},
            {"ad": "redis.service", "etiket": "Redis", "durum": "inactive"},
        ]
        p.gorunum_degistir("servisliste")
        _bekle(p, 0.4)
        p.ciz()
        p.kok.update()
        assert p.gorunum == "servisliste"
        eylemler = [e[0] for e in kartlar_modul.TIKLANABILIR]
        assert ("log", "apache2.service") in eylemler, eylemler
        metinler = _metinler(p, "SERVİSLER")
        assert any("SERVİSLER (3)" in m for m in metinler), metinler
        assert any("BOZUK" in m for m in metinler), metinler
        # satıra dokunmak günlüğü açar (log_ac çağrısı)
        p.log_ac("apache2.service")
        assert p.gorunum == "log" and p.log_tip == "birim"
        p.gorunum_degistir("servisliste")
        assert p._max_kaydir >= 0.0
        p.gorunum_degistir("pano")
    finally:
        p.kapat()


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
