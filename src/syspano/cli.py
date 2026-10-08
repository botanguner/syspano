"""Komut satırı arayüzü: seçenekleri okur, yapılandırmayla birleştirir, panoyu açar."""

import argparse
import os
import shutil
import subprocess
import sys

from . import __version__, UYGULAMA_ADI, ayar as ayar_mod, ekran, ortam
from .arayuz.yerlesim import KART_BILGI


def _pencere_boyutu(metin):
    try:
        g, y = metin.lower().split("x")
        return [int(g), int(y)]
    except Exception:
        raise argparse.ArgumentTypeError("boyut GxY biçiminde olmalı (örn. 1280x720)")


def argumanlar(argv=None):
    p = argparse.ArgumentParser(
        prog="syspano",
        description=f"{UYGULAMA_ADI} — Linux sistem ve kaynak izleme panosu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Örnekler:\n"
               "  syspano --liste-ekranlar\n"
               "  syspano --ekran HDMI-A-1              (ikincil ekranı kapla)\n"
               "  syspano --mod pencere --pencere 1280x720\n"
               "  syspano --ekran ana --olcek 1.6        (yazıları büyüt)\n")
    p.add_argument("--ekran", "-e", metavar="AD",
                   help="hedef ekran: auto|ana|tumu|çıkış adı|sıra no (varsayılan: auto)")
    p.add_argument("--mod", "-m", choices=["ekran", "pencere", "tam-ekran"],
                   help="yerleşim modu (varsayılan: ekran)")
    p.add_argument("--pencere", "-p", type=_pencere_boyutu, metavar="GxY",
                   help="pencere modu için boyut, örn. 1280x720")
    p.add_argument("--olcek", "-o", type=float, metavar="K",
                   help="ölçek katsayısı (1.0 varsayılan; yazıları büyütmek için artırın)")
    p.add_argument("--tema", choices=["koyu", "acik"], help="renk teması")
    p.add_argument("--kartlar", metavar="LİSTE",
                   help="gösterilecek kartlar, virgülle (örn. cpu,bellek,gpu)")
    p.add_argument("--kart-ekle", metavar="LİSTE", help="kart ekle")
    p.add_argument("--kart-cikar", metavar="LİSTE", help="kart çıkar")
    p.add_argument("--otomatik-kart", dest="otomatik_kart", action="store_true",
                   default=None, help="yer yetmezse kartları otomatik gizle (varsayılan)")
    p.add_argument("--kartlari-koru", dest="otomatik_kart", action="store_false",
                   help="tüm kartları koru, gerekirse kaydır")
    p.add_argument("--buyutec", dest="buyutec", action="store_true", default=None,
                   help="büyüteci aç (varsayılan)")
    p.add_argument("--buyutec-yok", dest="buyutec", action="store_false",
                   help="büyüteci kapat")
    p.add_argument("--terminal", dest="terminal", action="store_true", default=None,
                   help="gömülü terminal sekmesini aç (varsayılan)")
    p.add_argument("--terminal-yok", dest="terminal", action="store_false",
                   help="terminal sekmesini kapat")
    p.add_argument("--tepsi", dest="tepsi", action="store_true", default=None,
                   help="sistem tepsisi simgesini başlat")
    p.add_argument("--tepsi-yok", dest="tepsi", action="store_false",
                   help="tepsi simgesini başlatma")
    p.add_argument("--yonetilen", dest="yonetilen_pencere", action="store_true",
                   default=None, help="pencereyi yöneticiye bırak (varsayılan: KWin'de evet)")
    p.add_argument("--aralik", type=int, metavar="MS", help="güncelleme aralığı (ms)")
    p.add_argument("--test", action="store_true", help="9 saniye sonra kapan")
    p.add_argument("--liste-ekranlar", action="store_true",
                   help="ekranları listele ve çık")
    p.add_argument("--kartlari-listele", action="store_true",
                   help="kullanılabilir kartları listele ve çık")
    p.add_argument("--yapilandir", action="store_true",
                   help="verilen seçenekleri yapılandırma dosyasına yaz ve çık")
    p.add_argument("--varsayilan-yapilandirma", action="store_true",
                   help="varsayılan yapılandırma dosyasını oluştur ve çık")
    p.add_argument("--surum", "-V", action="version",
                   version=f"{UYGULAMA_ADI} {__version__}")
    return p.parse_args(argv)


def _liste(metin):
    return [x.strip() for x in (metin or "").split(",") if x.strip()]


def yapilandirmayi_birlestir(a, y):
    """Komut satırı seçeneklerini yapılandırmanın üzerine yazar."""
    if a.ekran is not None:
        y["ekran"] = a.ekran
    if a.mod is not None:
        y["mod"] = a.mod
    if a.pencere is not None:
        y["pencere"] = a.pencere
        if a.mod is None:
            y["mod"] = "pencere"
    if a.olcek is not None:
        y["olcek"] = a.olcek
    if a.tema is not None:
        y["tema"] = a.tema
    if a.kartlar is not None:
        y["kartlar"] = [k for k in _liste(a.kartlar) if k in KART_BILGI]
    if a.kart_ekle:
        y["kartlar"] = list(dict.fromkeys(list(y.get("kartlar") or []) + _liste(a.kart_ekle)))
    if a.kart_cikar:
        cikar = set(_liste(a.kart_cikar))
        y["kartlar"] = [k for k in (y.get("kartlar") or []) if k not in cikar]
    if a.otomatik_kart is not None:
        y["otomatik_kart"] = a.otomatik_kart
    if a.buyutec is not None:
        y["buyutec"] = a.buyutec
    if a.terminal is not None:
        y["terminal"] = a.terminal
    if a.tepsi is not None:
        y["tepsi"] = a.tepsi
    if a.yonetilen_pencere is not None:
        y["yonetilen_pencere"] = a.yonetilen_pencere
    if a.aralik is not None:
        y["guncelleme_ms"] = max(250, a.aralik)
    # doğrulama
    y["kartlar"] = [k for k in (y.get("kartlar") or []) if k in KART_BILGI]
    return y


def _tepsi_baslat():
    """Tepsi simgesini arka planda başlatır (PySide6 varsa)."""
    try:
        import PySide6  # noqa: F401
    except Exception:
        print("Not: PySide6 kurulu değil, tepsi simgesi atlandı "
              "(isteğe bağlı: pip install PySide6).", file=sys.stderr)
        return
    try:
        subprocess.Popen(
            [sys.executable, "-m", "syspano.tepsi"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except Exception as hata:
        print(f"Uyarı: tepsi simgesi başlatılamadı ({hata}).", file=sys.stderr)


def main(argv=None):
    a = argumanlar(argv)
    y = ayar_mod.oku()

    if a.liste_ekranlar:
        print(ekran.liste_metni())
        print(f"\nSanal ekran: {ekran.sanal_ekran()}")
        return 0

    if a.kartlari_listele:
        for k, bilgi in KART_BILGI.items():
            print(f"  {k:<10} {bilgi['baslik']}")
        return 0

    if a.varsayilan_yapilandirma:
        yol = ayar_mod.yaz(ayar_mod.VARSAYILAN)
        print(f"Varsayılan yapılandırma yazıldı: {yol}")
        return 0

    if a.yapilandir:
        y = yapilandirmayi_birlestir(a, y)
        yol = ayar_mod.yaz(y)
        print(f"Yapılandırma güncellendi: {yol}")
        return 0

    y = yapilandirmayi_birlestir(a, y)

    if not ortam.xwayland_var():
        print("Hata: DISPLAY tanımlı değil. Pano bir grafik oturumunda çalışmalı.\n"
              "Wayland kullanıyorsanız Xwayland paketinin kurulu olduğundan emin olun.",
              file=sys.stderr)
        return 2

    from .arayuz.pano import Pano

    cikis = ekran.ekran_sec(y.get("ekran", "auto"))
    if cikis:
        print(f"Hedef ekran: {cikis.ad} {cikis.g}x{cikis.yuk}+{cikis.x}+{cikis.y} "
              f"({cikis.dpi:.0f} dpi)")
    else:
        print(f"Hedef: tüm masaüstü {ekran.sanal_ekran()}")

    pano = Pano(y, cikis=cikis, mod=y.get("mod"), test=a.test)
    print(f"Ölçek {pano.S:.2f} · tasarım {pano.TG}x{pano.TY} · sütun "
          f"{pano.plan['sutun']} · ölçüm aralığı {y.get('guncelleme_ms')} ms")
    if pano.gizli_kartlar:
        print(f"Yer yetmediği için gizlenen kartlar: {', '.join(pano.gizli_kartlar)}")
    if pano._kaydirilir():
        print("İçerik ekrana sığmadı: fare tekerleği veya sürükleyerek kaydırın.")

    if y.get("tepsi") and not a.test:
        _tepsi_baslat()

    try:
        pano.calistir()
    except KeyboardInterrupt:
        pano.kapat()
    return 0
