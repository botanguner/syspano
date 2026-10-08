"""CPU: toplam ve çekirdek başına kullanım, frekans, yük, çekirdek sayısı."""

import glob
import os

from . import ortak


def _stat():
    toplam, cekirdekler = None, []
    try:
        with open("/proc/stat") as f:
            for satir in f:
                if not satir.startswith("cpu"):
                    break
                p = satir.split()
                d = [int(v) for v in p[1:]]
                kayit = (sum(d), d[3] + (d[4] if len(d) > 4 else 0))
                if p[0] == "cpu":
                    toplam = kayit
                else:
                    cekirdekler.append(kayit)
    except Exception:
        return None, []
    return toplam, cekirdekler


def frekanslar(cekirdek_sayisi):
    """Çekirdek başına MHz. cpufreq yoksa (bazı ARM kartları) devfreq denenir."""
    frek, kaynak = [], "cpufreq"
    for i in range(cekirdek_sayisi):
        f = ortak.oku(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq")
        if f:
            frek.append(int(f) / 1000.0)
    if not frek:
        kaynak = "devfreq"
        for yol in sorted(glob.glob("/sys/class/devfreq/*/cur_freq")):
            f = ortak.oku(yol)
            if f:
                frek.append(int(f) / 1e6)
    return frek, kaynak


def maks_frekans():
    m = ortak.oku_sayi("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
    return m / 1000.0 if m else 0.0


def oku(d, ayar):
    toplam, cekirdekler = _stat()
    if toplam is None:
        return {"yok": True}

    yuzde, cek_yuzde = 0.0, [0.0] * len(cekirdekler)
    if d.onceki_cpu:
        ot, ob = d.onceki_cpu[0]
        if toplam[0] - ot > 0:
            yuzde = 100.0 * (1 - (toplam[1] - ob) / (toplam[0] - ot))
        for i, (t, b) in enumerate(cekirdekler):
            if i < len(d.onceki_cpu[1]):
                ot2, ob2 = d.onceki_cpu[1][i]
                if t - ot2 > 0:
                    cek_yuzde[i] = 100.0 * (1 - (b - ob2) / (t - ot2))
    d.onceki_cpu = (toplam, cekirdekler)

    frek, kaynak = frekanslar(len(cekirdekler))
    if len(frek) == len(cekirdekler):
        cek_frek = frek
    elif len(frek) == 1:
        cek_frek = frek * len(cekirdekler)
    else:
        cek_frek = []

    return {
        "yuzde": max(0.0, min(100.0, yuzde)),
        "cekirdek": cek_yuzde,
        "ghz": (sum(frek) / len(frek) / 1000.0) if frek else 0.0,
        "maks_ghz": (max(frek) / 1000.0) if frek else maks_frekans() / 1000.0,
        "yuk": ortak.oku("/proc/loadavg", "? ? ?").split()[:3],
        "cekirdek_sayisi": len(cekirdekler),
        "cekirdek_ghz": cek_frek,
        "frekans_kaynagi": kaynak,
        "governor": ortak.oku("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "-"),
    }
