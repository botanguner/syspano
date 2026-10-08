"""Komut satırı arayüzü: seçenekleri okur, ekranı seçer, panoyu başlatır."""

import argparse
import json
import os
import sys

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
    p.add_argument("--test", nargs="?", const=10, type=int, metavar="SANIYE",
                   help="test modu: belirtilen süre sonra kapanır (varsayılan 10 sn)")
    p.add_argument("--liste-ekranlar", action="store_true",
                   help="bağlı ekranları listele ve çık")
    p.add_argument("--kartlari-listele", action="store_true",
                   help="kullanılabilir kartları listele ve çık")
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


def _liste(metin):
    return [k.strip() for k in (metin or "").replace(";", ",").split(",") if k.strip()]


def main(argv=None):
    args = _olustur_ayristirici().parse_args(argv)

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
    if args.kart_ekle:
        for k in _liste(args.kart_ekle):
            if k in KART_BILGI and k not in ayarlar["kartlar"]:
                ayarlar["kartlar"].append(k)
    if args.kart_cikar:
        ayarlar["kartlar"] = [k for k in ayarlar["kartlar"] if k not in _liste(args.kart_cikar)]

    if args.pencere:
        ayarlar["pencere"] = _pencere_olcusu(args.pencere)
        ayarlar["mod"] = "pencere"
    elif args.tam_ekran:
        ayarlar["mod"] = "tam-ekran"
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
    pano = Pano(ayarlar, cikis=cikis, mod=mod)

    print(f"SysPano {__version__}\n"
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
