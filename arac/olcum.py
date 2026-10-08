"""SysPano kaynak profili: hangi toplayıcı ve çizim adımı ne kadar sürüyor?

Kullanım:
    PYTHONPATH=src python3 arac/olcum.py            # toplayıcılar (X gerekmez)
    PYTHONPATH=src python3 arac/olcum.py --cizim    # çizim karesi de (X gerekir)

Çıktı: her modül için ortalama/tepede süre (ms) ve çizim karesi başına süre.
Pi gibi yavaş cihazlarda darboğazı bulmak için.
"""

import argparse
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from syspano.cihaz import TOPLAYICILAR          # noqa: E402
from syspano.toplayici import Toplayici         # noqa: E402


def olc_toplayicilar(tekrar=12):
    t = Toplayici({"guncelleme_ms": 1000})
    print("── toplayıcı modülleri " + "─" * 40)
    print(f"{'modül':<10} {'ort (ms)':>9} {'tepe (ms)':>10} {'toplam %':>9}")
    sonuclar = {}
    # ilk tur ısınma (hwmon taraması, /proc okuma)
    for ad, mod in TOPLAYICILAR:
        try:
            mod.oku(t, t.ayar)
        except Exception:
            pass
    toplam_sure = 0.0
    for ad, mod in TOPLAYICILAR:
        sureler = []
        for _ in range(tekrar):
            bas = time.perf_counter()
            try:
                mod.oku(t, t.ayar)
            except Exception:
                pass
            sureler.append((time.perf_counter() - bas) * 1000)
        ort = statistics.mean(sureler)
        sonuclar[ad] = ort
        toplam_sure += ort
        print(f"{ad:<10} {ort:9.2f} {max(sureler):10.2f}")
    for ad, ort in sonuclar.items():
        print(f"{ad:<10} pay: %{100 * ort / toplam_sure:.0f}" if toplam_sure else "")
    print(f"{'TOPLAM':<10} {toplam_sure:9.2f} ms  (1 sn aralıkta → %{toplam_sure / 10:.0f} çekirdek)")
    return toplam_sure


def olc_cizim(tekrar=15, pencere=(900, 560)):
    import tkinter as tk
    from syspano.arayuz.pano import Pano
    try:
        tk.Tk().destroy()
    except Exception as hata:
        print(f"çizim ölçümü atlandı (görüntü yok: {hata})")
        return
    p = Pano({"pencere": list(pencere), "guncelleme_ms": 1000, "tepsi": False,
              "test_suresi": None}, cikis=None, mod="pencere")
    p.kok.withdraw()
    son = time.monotonic() + 2
    while time.monotonic() < son:
        p.kok.update()
        time.sleep(0.05)

    print("\n── çizim " + "─" * 48)
    for gorunum in ("pano", "ayar"):
        p.gorunum = gorunum
        p.ciz()
        p.kok.update()
        sureler = []
        for _ in range(tekrar):
            bas = time.perf_counter()
            p.ciz()
            p.kok.update()
            sureler.append((time.perf_counter() - bas) * 1000)
        ort = statistics.mean(sureler)
        print(f"{gorunum:<8} ort {ort:7.2f} ms   tepe {max(sureler):7.2f} ms"
              f"   öğe {len(p.c.find_all())}")
        p.c.delete("all")

    # kaydırma maliyeti (içerik taşıma)
    p.gorunum = "ayar"
    p.ciz()
    bas = time.perf_counter()
    for i in range(60):
        p.c.move("icerik", 0, -2)
    tasi = (time.perf_counter() - bas) * 1000 / 60
    print(f"{'kaydırma':<8} taşıma {tasi:6.3f} ms/hareket (60 hareket ort.)")
    p.kapat()


def olc_gercekci(sure=20):
    """Üretim temposu: her saniye bir `topla()`. Seyreltilen sensörler böyle görünür."""
    t = Toplayici({"guncelleme_ms": 1000})
    print(f"── üretim temposu ({sure} sn, 1 sn aralık) " + "─" * 20)
    # ısınma
    t.topla()
    toplam = 0.0
    en_uzun = 0.0
    adet_sure = {ad: 0.0 for ad, _ in TOPLAYICILAR}
    for _ in range(sure):
        time.sleep(1.0)
        bas = time.perf_counter()
        veri = {}
        for ad, mod in TOPLAYICILAR:
            b2 = time.perf_counter()
            try:
                veri[ad] = mod.oku(t, t.ayar)
            except Exception:
                veri[ad] = {}
            adet_sure[ad] += (time.perf_counter() - b2) * 1000
        sure_ms = (time.perf_counter() - bas) * 1000
        toplam += sure_ms
        en_uzun = max(en_uzun, sure_ms)
    print(f"{'modül':<10} {'ort (ms/sn)':>12}")
    for ad, s in sorted(adet_sure.items(), key=lambda kv: -kv[1]):
        print(f"{ad:<10} {s / sure:12.3f}")
    print(f"{'TOPLAM':<10} {toplam / sure:12.3f} ms/sn"
          f"  → tek çekirdeğin %{toplam / sure / 10:.1f}'i"
          f"   (en uzun kare {en_uzun:.1f} ms)")


def main():
    ap = argparse.ArgumentParser(description="SysPano kaynak profili")
    ap.add_argument("--cizim", action="store_true", help="çizim karesini de ölç")
    ap.add_argument("--hizli", action="store_true",
                    help="modülleri art arda ölç (üretim temposu yerine)")
    ap.add_argument("--tekrar", type=int, default=12)
    a = ap.parse_args()
    if a.hizli:
        olc_toplayicilar(a.tekrar)
    else:
        olc_gercekci(a.tekrar if a.tekrar != 12 else 20)
    if a.cizim:
        olc_cizim(15)


if __name__ == "__main__":
    main()
