"""Bellek: RAM kullanımı ve takas (zram dahil)."""

import glob
import os

from . import ortak


def oku(d, ayar):
    m = {}
    try:
        with open("/proc/meminfo") as f:
            for satir in f:
                p = satir.split(":")
                if len(p) == 2:
                    m[p[0]] = float(p[1].strip().split()[0]) / 1048576.0   # MiB -> GiB
    except Exception:
        return {"yok": True}

    toplam = m.get("MemTotal", 0)
    kullanilan = toplam - m.get("MemAvailable", 0)

    # zram kullanılıyor mu? (takas diski yerine sıkıştırılmış RAM)
    zram = False
    try:
        zram = bool(glob.glob("/sys/block/zram*"))
    except Exception:
        pass

    return {
        "toplam": toplam,
        "kullanilan": kullanilan,
        "yuzde": 100.0 * kullanilan / toplam if toplam else 0,
        "swap_t": m.get("SwapTotal", 0),
        "swap_k": m.get("SwapTotal", 0) - m.get("SwapFree", 0),
        "takas_tur": "zram" if zram else "takas",
        "onbellek": m.get("Cached", 0),
        "bos": m.get("MemAvailable", 0),
    }
