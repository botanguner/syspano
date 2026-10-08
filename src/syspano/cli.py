"""Komut satırı arayüzü: seçenekleri okur, ekranı seçer, panoyu başlatır."""

import argparse
import json
import os
import sys
import time

from . import __version__
from . import ayar as ayar_modul
from . import ekran as ekran_modul
from . import ortam
from .arayuz.yerlesim import KART_BILGI

ONIZLEME = """
SysPano — Linux sistem ve kaynak izleme panosu.

Ekran boyutuna, çözünürlüğe ve DPI'a göre kendini uyarlar; sıradan bir
monitörde, ikincil küçük bir ekranda ya da Raspberry Pi dokunmatik panelinde
çalışır. Tkinter kullanır: harici Python bağımlılığı yoktur.
"""


def _olustur_ayristirici():
    p = argparse.ArgumentParser(
        prog="syspano", description=ONIZLEME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Örnekler:\n"
               "  syspano                        hedef ekranı otomatik seç\n"
               "  syspano --ekran HDMI-A-1       ikincil ekranı kapla\n"
               "  syspano --pencere 800x480      küçük pencerede çalıştır\n"
               "  syspano --olcek 1.5            ölçeği elle ayarla\n"
               "  syspano --kartlar cpu,bellek,gpu\n"
               "  syspano --liste-ekranlar       ekranları listele\n")
    p.add_argument("-e", "--ekran", metavar="AD",
                   help="hedef ekran: auto | ana | tumu | çıkış adı (HDMI-A-1) | sıra no")
    p.add_argument("-m", "--mod", choices=["ekran", "pencere", "tam-ekran"],
                   help="görüntüleme modu (varsayılan: ekran)")
    p.add_argument("-p", "--pencere", metavar="WxH",
                   help="pencere modu (örn. 800x480)")
    p.add_argument("--tam-ekran", dest="tam_ekran", action="store_true",
                   help="hedef ekranı tam ekran kapla (--mod tam-ekran ile aynı)")
    p.add_argument("-o", "--olcek", type=float, metavar="F",
                   help="ölçek katsayısı (DPI otomatiğini ezer, 0.7–3.0)")
    p.add_argument("--tema", choices=["koyu", "acik"], help="renk teması")
    p.add_argument("--kartlar", metavar="LISTE",
                   help="gösterilecek kartlar (virgülle): " + ",".join(sorted(KART_BILGI)))
    p.add_argument("--kart-ekle", metavar="LISTE", help="listeye kart ekle")
    p.add_argument("--kart-cikar", metavar="LISTE", help="listeden kart çıkar")
    p.add_argument("--otomatik-kart", dest="otomatik_kart", action="store_true",
                   default=None, help="yer darsa kartları otomatik gizle (varsayılan)")
    p.add_argument("--kartlari-koru", dest="otomatik_kart", action="store_false",
                   help="kartları gizleme, gerekirse kaydır")
    p.add_argument("--terminal", dest="terminal", action="store_true", default=None,
                   help="gömülü terminali etkinleştir")
    p.add_argument("--terminal-yok", dest="terminal", action="store_false",
                   help="gömülü terminali kapat")
    p.add_argument("--buyutec", dest="buyutec", action="store_true", default=None,
                   help="büyüteci etkinleştir")
    p.add_argument("--buyutec-yok", dest="buyutec", action="store_false",
                   help="büyüteci kapat")
    p.add_argument("--tepsi", dest="tepsi", action="store_true", default=None,
                   help="tepsi simgesini etkinleştir (PySide6 gerekir)")
    p.add_argument("--tepsi-yok", dest="tepsi", action="store_false",
                   help="tepsi simgesini kapat")
    p.add_argument("--yonetilen", dest="yonetilen", action="store_true", default=None,
                   help="yöneticisiz pencere yerine normal pencere kullan")
    p.add_argument("--aralik", type=int, metavar="MS", help="güncelleme aralığı (ms)")
    p.add_argument("--ayarlar", action="store_true",
                   help="pano yerine ayar ekranıyla başla")
    p.add_argument("--demo", action="store_true",
                   help="uydurma verilerle çalıştır (ekran görüntüsü/demo için; "
                        "hiçbir sistem dosyası okunmaz)")
    p.add_argument("--test", nargs="?", const=10, type=int, metavar="SANIYE",
                   help="test modu: belirtilen süre sonra kapanır (varsayılan 10 sn)")
    p.add_argument("--liste-ekranlar", action="store_true",
                   help="bağlı ekranları listele ve çık")
    p.add_argument("--kartlari-listele", action="store_true",
                   help="kullanılabilir kartları listele ve çık")
    p.add_argument("--servisler", action="store_true",
                   help="izlenen systemd servislerini ve durumlarını listele ve çık")
    p.add_argument("--log", metavar="BIRIM",
                   help="bir servisin günlüğünü yazdır (ör. --log apache2)")
    p.add_argument("--log-kaynaklar", action="store_true",
                   help="bulunan günlük dosyalarını listele (Apache, PHP, Laravel…)")
    p.add_argument("--log-dosya", metavar="YOL",
                   help="bir günlük dosyasının sonunu yazdır (--log-satir ile satır sayısı)")
    p.add_argument("--log-hata", action="store_true",
                   help="--log/--log-dosya çıktısında yalnızca hata ve uyarı satırları")
    p.add_argument("--log-pencere", type=int, default=None, metavar="DK",
                   help="journald hata/uyarı sayımı için zaman penceresi (varsayılan 60 dk)")
    p.add_argument("--cek", nargs="?", const="", default=None, metavar="DOSYA",
                   help="ekran/panonun PNG kaydını al ve çık (varsayılan: ~/Pictures)")
    p.add_argument("--bekci", action="store_true",
                   help="pano bekçisi: panoyu yoksa başlatır, donmuşsa yeniden başlatır")
    p.add_argument("--bekci-aralik", type=float, default=None, metavar="SN",
                   help="bekçinin kontrol aralığı (varsayılan 20 sn)")
    p.add_argument("--bekci-esik", type=float, default=None, metavar="SN",
                   help="kalp atışı bu süre bayatlarsa pano donmuş sayılır (varsayılan 90 sn)")
    p.add_argument("--bekci-kuru", action="store_true",
                   help="bekçi yalnızca kararını yazsın, hiçbir şeyi başlatıp öldürmesin")
    p.add_argument("--log-satir", type=int, default=200, metavar="N",
                   help="--log ile gösterilecek satır sayısı (varsayılan 200)")
    p.add_argument("--guncelle", action="store_true",
                   help="depoyu güncelle (git pull) ve paketi yeniden kur")
    p.add_argument("--guncelle-denetle", action="store_true",
                   help="yeni sürüm var mı denetle ve çık")
    p.add_argument("--kurulum-bilgisi", action="store_true",
                   help="kurulum kaydını ve durum dosyalarını göster")
    p.add_argument("--yapilandir", action="store_true",
                   help="varsayılan yapılandırma dosyasını oluştur ve yolunu yaz")
    p.add_argument("--varsayilan-yapilandirma", action="store_true",
                   help="varsayılan yapılandırmayı ekrana yaz (dosyaya dokunmaz)")
    p.add_argument("-V", "--surum", action="version", version=f"SysPano {__version__}")
    return p


def _pencere_olcusu(metin):
    try:
        g, y = metin.lower().replace("×", "x").split("x")
        return [max(200, int(g)), max(150, int(y))]
    except Exception:
        raise SystemExit(f"--pencere biçimi geçersiz: {metin} (örn. 800x480)")


# ─── güncelleme komutları ────────────────────────────────────────────────────
def _guncelle_calistir():
    from . import guncelleme
    kayit = guncelleme.kayit_oku()
    if not kayit:
        print("Kurulum kaydı bulunamadı "
              f"({guncelleme.kayit_yolu()}).\n"
              "Elle güncelleme:\n"
              "  Depo klonu varsa : cd <depo> && git pull && ./install.sh\n"
              "  pip ile kurulduysa: python3 -m pip install --user --upgrade "
              "<depo>")
        return 1
    print(f"Güncelleniyor… (kaynak: {kayit.get('kaynak')}, yöntem: {kayit.get('yontem')})")
    # Durumu dosyaya yaz: pano bunu okuyup "sürüyor / bitti / başarısız" gösterir.
    guncelleme.surec_yaz(guncelleme.GUNCELLEME_ASAMASI, baslangic=time.time(),
                         mesaj="başlatıldı")
    try:
        sonuc = guncelleme.guncelle()
    except Exception as hata:                       # beklenmedik hata
        guncelleme.surec_yaz(guncelleme.GUNCELLEME_ASAMASI, sonuc=1,
                             mesaj=f"{type(hata).__name__}: {hata}")
        print(f"  ✗ güncelleme başarısız: {hata}")
        return 1
    for ok, mesaj in sonuc["adimlar"]:
        print(("  ✓ " if ok else "  ✗ ") + mesaj)
    if sonuc["ok"]:
        try:
            guncelleme.surec_yaz(guncelleme.GUNCELLEME_ASAMASI, sonuc=0,
                                 surum=guncelleme.kurulu_surum(),
                                 mesaj="tamam")
        except Exception:
            pass
        print(f"\nYeniden başlatın: {guncelleme.yeniden_baslat_yolu()}")
        return 0
    hatalar = [m for ok, m in sonuc["adimlar"] if not ok]
    try:
        guncelleme.surec_yaz(guncelleme.GUNCELLEME_ASAMASI, sonuc=1,
                             mesaj=(hatalar[-1][:160] if hatalar else "bilinmeyen hata"))
    except Exception:
        pass
    return 1


def _denetle_calistir():
    from . import guncelleme
    kayit = guncelleme.kayit_oku()
    print(f"çalışan kod : {__version__}")
    print(f"kurulu paket: {guncelleme.kurulu_surum()}")
    if guncelleme.yeniden_baslat_gerekli():
        print("              ↳ bellekteki kod eski — yeniden başlatın: "
              + guncelleme.yeniden_baslat_yolu())
    if kayit:
        print(f"kurulum     : {kayit.get('yontem')} → {kayit.get('kaynak')}")
    else:
        print("kurulum     : kayıt yok (install.sh yazmamış)")
    sonuc = guncelleme.denetle()
    metin, _renk = guncelleme.durum_metni(denetim=sonuc)
    print(f"durum       : {metin}")
    if sonuc.get("hata"):
        return 1
    if sonuc.get("yeni"):
        if sonuc.get("mesaj"):
            print(f"              son: {sonuc['mesaj']}")
        print("              güncellemek için: syspano --guncelle")
    return 0


def _kurulum_bilgisi():
    from . import guncelleme
    kayit = guncelleme.kayit_oku()
    print(f"sürüm       : {guncelleme.yerel_surum()}")
    print(f"python      : {sys.executable}")
    if kayit:
        for anahtar, deger in kayit.items():
            print(f"{anahtar:<11} : {deger}")
    else:
        print("kurulum kaydı yok")
    print(f"kayıt yolu  : {guncelleme.kayit_yolu()}")
    print(f"denetim     : {guncelleme.denetim_yolu()} — {guncelleme.metin_ozet()}")
    return 0


def _liste(metin):
    return [k.strip() for k in (metin or "").replace(";", ",").split(",") if k.strip()]


# ─── servis komutları ────────────────────────────────────────────────────────
def _birim_adi(metin):
    """'apache2' → 'apache2.service' (zaten birim adıysa dokunmaz)."""
    metin = (metin or "").strip()
    return metin if "." in metin else metin + ".service"


def _servisleri_listele():
    from .cihaz import servisler as S
    if not S.systemd_var():
        print("systemd bulunamadı — bu sistemde servis izleme kapalı.")
        return 1
    ayar = ayar_modul.oku()
    kayitlar = S._durum_oku(S._kesif(ayar))
    if not kayitlar:
        print("izlenecek servis bulunamadı.")
        return 0
    sira = {"failed": 0, "activating": 1, "active": 2, "reloading": 2}
    kayitlar.sort(key=lambda k: (sira.get(k["durum"], 3), k["etiket"]))
    print(f"{'servis':<18} {'durum':<10} {'alt durum':<12} {'bellek':>9}  birim")
    print("-" * 72)
    for k in kayitlar:
        bellek = f"{k['bellek'] / 1048576:.0f} MB" if k["bellek"] else "—"
        print(f"{k['etiket']:<18} {k['durum']:<10} {k['alt']:<12} {bellek:>9}  {k['ad']}")
    print(f"\n{len(kayitlar)} servis · günlük için: syspano --log {kayitlar[0]['ad']}")
    return 0


def _bekci_calistir(aralik=None, esik=None, kuru=False):
    from . import bekci
    print(f"SysPano bekçisi · aralık {aralik or bekci.VARSAYILAN_ARALIK:.0f} sn · "
          f"eşik {esik or bekci.VARSAYILAN_ESIK:.0f} sn · "
          f"günlük {bekci.gunluk_yolu()}", flush=True)
    if kuru:
        return 0 if bekci.dongu(aralik, esik, kuru=True, tur_sayisi=1) in (
            "bekle", "baslat", "oldur") else 1
    try:
        bekci.dongu(aralik, esik)
    except KeyboardInterrupt:
        return 0
    return 0


def _cek_calistir(yol=None):
    from . import goruntu
    ok, mesaj = goruntu.cek(yol or None)
    print(("✓ " if ok else "✗ ") + mesaj)
    return 0 if ok else 1


def _log_yazdir(birim, satir, yalniz_hata=False, pencere=None):
    from .cihaz import loglar as L
    from .cihaz import servisler as S
    if not S.systemd_var():
        print("systemd bulunamadı.", file=sys.stderr)
        return 1
    ad = _birim_adi(birim)
    ayar = ayar_modul.oku()
    pencere = int(pencere if pencere is not None else
                  ayar.get("log_pencere_dk") or L.VARSAYILAN_PENCERE_DK)
    metin, kaynak = S.gunluk(ad, max(1, satir), ayar)
    p = L.ozet_journal(ad, pencere)
    print(f"# {ad} · kaynak: {kaynak} · son {pencere} dk: {p['hata']} hata · "
          f"{p['uyari']} uyarı · (gösterilen {min(satir, len(metin.splitlines()))} satır)")
    print(L.suz(metin, yalniz_hata))
    return 0


def _log_dosya_yazdir(yol, satir, yalniz_hata=False):
    from .cihaz import loglar as L
    metin, kaynak = L.gunluk(yol, max(1, satir))
    ozet = L.ozet(metin)
    print(f"# {os.path.expanduser(yol)} · kaynak: {kaynak} · "
          f"{ozet['hata']} hata · {ozet['uyari']} uyarı")
    print(L.suz(metin, yalniz_hata))
    return 0


def _log_kaynaklari_listele(satir=200, pencere=None):
    """Bulunan günlük kaynaklarını, **son `pencere` dakikadaki** hata/uyarı sayısıyla
    listeler (journal kaynakları); dosya kaynaklarında son satırlara bakılır."""
    import time

    from .cihaz import loglar as L
    from .cihaz.ortak import kuyruk

    ayar = ayar_modul.oku()
    pencere = int(pencere if pencere is not None else
                  ayar.get("log_pencere_dk") or L.VARSAYILAN_PENCERE_DK)
    kaynaklar = L.bul(L.desenler(ayar), ayar=ayar)
    if not kaynaklar:
        print("günlük kaynağı bulunamadı.")
        print("Kendi dosyalarınızı ekleyin (~/.config/syspano/config.json):")
        print('  "log_dosyalari": ["~/projelerim/*/storage/logs/*.log", "journal:benim-servisim"]')
        return 0

    print(f"{'günlük':<22} {'son yazılma':<12} {'boyut':>8} "
          f"{'hata':>5} {'uyarı':>6}  yol / birim")
    print(f"{'':<22} {'':<12} {'':>8} {'(son ' + str(pencere) + ' dk)':>5}")
    print("-" * 100)
    simdi = time.time()
    for k in kaynaklar:
        if k.get("tur") == "journal":
            ozet = L.ozet_journal(k["birim"], pencere)
            print(f"{k['etiket']:<22} {'journal':<12} {'—':>8} "
                  f"{ozet['hata']:>5} {ozet['uyari']:>6}  {k['birim']}")
            continue
        if not k["okunabilir"]:
            print(f"{k['etiket']:<22} {'izin yok':<12} {'—':>8} {'—':>5} {'—':>6}  {k['yol']}")
            continue
        ozet = L.ozet(kuyruk(k["yol"], max(1, satir)))
        yas = _yas_metni(simdi - k["son"]) if k["son"] else "—"
        print(f"{k['etiket']:<22} {yas:<12} {_boyut(k['boyut']):>8} "
              f"{ozet['hata']:>5} {ozet['uyari']:>6}  {k['yol']}")
    print(f"\n{len(kaynaklar)} günlük · içeriği için: syspano --log-dosya YOL "
          f"(journal kaynakları için: syspano --log BIRIM)")
    return 0


def _yas_metni(sn):
    from .cihaz.ortak import sure_metni
    return sure_metni(sn)


def _boyut(bayt):
    b = float(bayt or 0)
    for birim in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.0f}{birim}"
        b /= 1024
    return f"{b:.0f}TB"


def _kart_uygula(ayarlar, ekle=None, cikar=None):
    """`--kart-ekle`/`--kart-cikar` için yeni kart listesi (değişiklik yoksa None).

    Liste **yerleşim sırasına** dizilir (ayar ekranının yaptığı gibi). Bilinmeyen
    kart adları yok sayılır.
    """
    kartlar = [k for k in (ayarlar.get("kartlar") or list(KART_BILGI)) if k in KART_BILGI]
    for k in _liste(ekle or ""):
        if k in KART_BILGI and k not in kartlar:
            kartlar.append(k)
    for k in _liste(cikar or ""):
        if k in kartlar:
            kartlar.remove(k)
    kartlar = [k for k in KART_BILGI if k in set(kartlar)]
    if not kartlar or kartlar == list(ayarlar.get("kartlar") or []):
        return None
    return kartlar


def _kartlari_kaydet(kartlar):
    """Kart listesini yapılandırmaya yazar (kalıcı): yazılan yol."""
    return ayar_modul.guncelle({"kartlar": kartlar})


def main(argv=None):
    args = _olustur_ayristirici().parse_args(argv)

    # ── görüntü gerektirmeyen komutlar (SSH'de de çalışır) ──
    if args.guncelle:
        return _guncelle_calistir()

    if args.guncelle_denetle:
        return _denetle_calistir()

    if args.kurulum_bilgisi:
        return _kurulum_bilgisi()

    if args.servisler:
        return _servisleri_listele()

    if args.bekci or args.bekci_kuru:
        return _bekci_calistir(args.bekci_aralik, args.bekci_esik, args.bekci_kuru)

    if args.cek is not None:
        return _cek_calistir(args.cek)

    if args.log_kaynaklar:
        return _log_kaynaklari_listele(args.log_satir, args.log_pencere)

    if args.log_dosya:
        return _log_dosya_yazdir(args.log_dosya, args.log_satir, args.log_hata)

    if args.log:
        return _log_yazdir(args.log, args.log_satir, args.log_hata, args.log_pencere)

    if args.liste_ekranlar:
        print(ekran_modul.liste_metni())
        return 0

    if args.kartlari_listele:
        print("Kullanılabilir kartlar:")
        for ad in sorted(KART_BILGI, key=lambda k: KART_BILGI[k]["oncelik"], reverse=True):
            b = KART_BILGI[ad]
            print(f"  {ad:<9} {b['baslik']:<24} (sütun {b['sutun']}, öncelik {b['oncelik']})")
        return 0

    if args.varsayilan_yapilandirma:
        print(json.dumps(ayar_modul.VARSAYILAN, indent=2, ensure_ascii=False))
        return 0

    ayarlar = ayar_modul.oku()

    if args.yapilandir:
        yol = ayar_modul.yaz(ayarlar)
        print(f"Yapılandırma yazıldı: {yol}")
        print(ekran_modul.liste_metni())
        return 0

    # ── komut satırı seçenekleri yapılandırmayı geçersiz kılar ──
    if args.ekran:
        ayarlar["ekran"] = args.ekran
    if args.mod:
        ayarlar["mod"] = args.mod
    if args.tema:
        ayarlar["tema"] = args.tema
    if args.olcek:
        ayarlar["olcek"] = args.olcek
    if args.terminal is not None:
        ayarlar["terminal"] = args.terminal
    if args.buyutec is not None:
        ayarlar["buyutec"] = args.buyutec
    if args.tepsi is not None:
        ayarlar["tepsi"] = args.tepsi
    if args.yonetilen is not None:
        ayarlar["yonetilen_pencere"] = args.yonetilen
    if args.otomatik_kart is not None:
        ayarlar["otomatik_kart"] = args.otomatik_kart
    if args.aralik:
        ayarlar["guncelleme_ms"] = max(200, args.aralik)

    if args.kartlar:
        istenen = [k for k in _liste(args.kartlar) if k in KART_BILGI]
        if istenen:
            ayarlar["kartlar"] = istenen
    if args.kart_ekle or args.kart_cikar:
        # Bunlar **kalıcıdır**: kullanıcı listeyi değiştirmek istiyor
        # (`--kartlar` ise yalnızca o çalıştırma için geçerlidir).
        yeni = _kart_uygula(ayarlar, args.kart_ekle, args.kart_cikar)
        if yeni:
            ayarlar["kartlar"] = yeni
            try:
                _kartlari_kaydet(yeni)
                print("Kart listesi kaydedildi: " + ", ".join(yeni))
            except Exception as hata:
                print(f"Uyarı: kart listesi kaydedilemedi: {hata}", file=sys.stderr)

    if args.pencere:
        ayarlar["pencere"] = _pencere_olcusu(args.pencere)
        ayarlar["mod"] = "pencere"
    elif args.tam_ekran:
        ayarlar["mod"] = "tam-ekran"
    if args.ayarlar:
        ayarlar["baslangic_gorunumu"] = "ayar"
    if args.test:
        ayarlar["test_suresi"] = args.test

    # ── ortam denetimi ──
    if not ortam.xwayland_var():
        print("HATA: X görüntüsü bulunamadı (DISPLAY tanımsız).\n"
              "Tkinter, X11/Xwayland gerektirir. Saf Wayland oturumunda:\n"
              "  • Xwayland'i kurun (çoğu dağıtımda 'xorg-xwayland' / 'xwayland')\n"
              "  • ya da bir X11 oturumunda açın.\n"
              f"Saptanan oturum: {ortam.oturum_tipi()}", file=sys.stderr)
        return 2

    cikislar = ekran_modul.cikislari_bul()
    secim = ayarlar.get("ekran", "auto")
    cikis = ekran_modul.ekran_sec(secim, cikislar)
    if cikis is None and secim not in ("tumu", "all", "hepsi") and cikislar:
        print(f"Uyarı: '{secim}' bulunamadı, tüm ekran kullanılıyor. "
              f"Mevcut: {', '.join(c.ad for c in cikislar)}", file=sys.stderr)

    if not cikislar:
        print("Uyarı: ekran bilgisi okunamadı (xrandr yok). Tüm ekran kullanılıyor.",
              file=sys.stderr)

    mod = ayarlar.get("mod", "ekran")
    if args.pencere:
        mod = "pencere"

    from .arayuz.pano import Pano
    pano = Pano(ayarlar, cikis=cikis, mod=mod, cikislar=cikislar, demo=args.demo)

    print(f"SysPano {__version__}"
          + ("  [DEMO — uydurma veriler]\n" if args.demo else "\n") +
          f"  ekran   : {cikis.ad if cikis else 'tüm ekran'} "
          f"({pano.w}x{pano.h}+{pano.x}+{pano.y})\n"
          f"  ölçek   : {pano.S:.2f}  → tasarım {pano.tasarim_g}x{pano.tasarim_y}\n"
          f"  büyüteç : {'açık' if pano.buyutec else 'kapalı'} ({pano.buyutec_neden})\n"
          f"  masaüstü: {ortam.masaustu() or '?'} / {ortam.oturum_tipi()} / "
          f"{ortam.dagitim()}", flush=True)

    if ayarlar.get("tepsi", True) and mod != "pencere":
        _tepsi_baslat()

    pano.calistir()
    return 0


def _tepsi_baslat():
    """Tepsi simgesini ayrı bir süreç olarak başlatır (PySide6 varsa)."""
    import subprocess
    if os.environ.get("SYSPANO_TEPSI_CALISIYOR"):
        return
    try:
        import PySide6  # noqa: F401
    except Exception:
        return
    try:
        env = dict(os.environ, SYSPANO_TEPSI_CALISIYOR="1")
        subprocess.Popen([sys.executable, "-m", "syspano.tepsi"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception:
        pass
