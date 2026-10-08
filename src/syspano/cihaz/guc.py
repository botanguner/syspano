"""Güç limitleri / CPU ayarları.

Intel RAPL (PL1/PL2), AMD RAPL, ARM/Raspberry Pi ve diğerleri için elden
geldiğince bilgi toplar. Hiçbiri yoksa yalnızca governor gösterilir.
"""

import glob
import os
import re

from . import ortak


def _rapl(ad="intel-rapl:0"):
    temel = f"/sys/class/powercap/{ad}"
    if not os.path.isdir(temel):
        return None
    pl1 = ortak.oku_sayi(f"{temel}/constraint_0_power_limit_uw", 0) / 1e6
    pl2 = ortak.oku_sayi(f"{temel}/constraint_1_power_limit_uw", 0) / 1e6
    return {"pl1": round(pl1), "pl2": round(pl2), "tur": "RAPL"}


def _amd_rapl():
    for yol in sorted(glob.glob("/sys/class/powercap/*-rapl:0/constraint_0_power_limit_uw")):
        pl1 = ortak.oku_sayi(yol, 0) / 1e6
        pl2 = ortak.oku_sayi(yol.replace("0_power", "1_power"), 0) / 1e6
        return {"pl1": round(pl1), "pl2": round(pl2), "tur": "RAPL"}
    return None


def oku(d, ayar):
    sonuc = {"tur": "yok", "pl1": 0, "pl2": 0}

    r = _rapl()
    if not r:
        try:
            adlar = [a for a in os.listdir("/sys/class/powercap") if "rapl" in a]
        except Exception:
            adlar = []
        for a in sorted(adlar):
            if a.endswith(":0"):
                r = _rapl(a)
                break
    if r:
        sonuc = r
    else:
        r = _amd_rapl()
        if r:
            sonuc = r

    # Raspberry Pi / genel: güç profili ya da governor
    for yol in ("/sys/firmware/acpi/platform_profile",
                "/sys/class/power_supply/platform_profile"):
        deger = ortak.oku(yol)
        if deger:
            sonuc["profil"] = deger
            break
    sonuc["governor"] = ortak.oku(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "-")
    return sonuc
