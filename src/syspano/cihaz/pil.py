"""Pil ve güç kaynağı. Pil yoksa (masaüstü, Raspberry Pi) kart gizlenir."""

import os

from . import ortak

_PS = "/sys/class/power_supply"


def _tip(ad):
    return ortak.oku(f"{_PS}/{ad}/type", "") or ""


def pil_bul():
    """Pil düğümünün adı (BAT0, BAT1, CMB0, ...) ya da None."""
    try:
        adlar = sorted(os.listdir(_PS))
    except Exception:
        return None
    # önce type=Battery
    for ad in adlar:
        if _tip(ad).lower() == "battery":
            return ad
    for ad in adlar:
        if ad.startswith(("BAT", "battery", "CMB")):
            return ad
    return None


def ac_bul():
    try:
        for ad in sorted(os.listdir(_PS)):
            if _tip(ad).lower() in ("mains", "ups"):
                return ad
    except Exception:
        pass
    return None


def oku(d, ayar):
    if d.pil_dugum is None and not d.pil_arandi:
        d.pil_dugum = pil_bul()
        d.ac_dugum = ac_bul()
        d.pil_arandi = True
    b = f"{_PS}/{d.pil_dugum}" if d.pil_dugum else None
    if not b or not os.path.isdir(b):
        return {"yok": True}

    # enerji (Wh) ya da yük (Ah × V)
    def _enerji(ad):
        deger = ortak.oku_sayi(f"{b}/{ad}", -1)
        if deger >= 0:
            return deger / 1e6
        return None

    enerji = _enerji("energy_now")
    tam = _enerji("energy_full")
    tasarim = _enerji("energy_full_design")
    guc = _enerji("power_now")

    if enerji is None:                       # charge_* (Ah) biçimi
        gerilim = ortak.oku_sayi(f"{b}/voltage_now", 0) / 1e6
        def _yuk(ad):
            v = ortak.oku_sayi(f"{b}/{ad}", -1)
            return (v / 1e6) * gerilim if v >= 0 else None
        enerji, tam, tasarim, guc = _yuk("charge_now"), _yuk("charge_full"), \
            _yuk("charge_full_design"), _yuk("current_now")

    durum = ortak.oku(f"{b}/status", "?")
    yuzde = ortak.oku_sayi(f"{b}/capacity", -1)
    if yuzde < 0 and tam:
        yuzde = 100.0 * (enerji or 0) / tam

    kalan = 0.0
    if guc and guc > 0.05 and durum == "Discharging" and enerji:
        kalan = (enerji / guc) * 60.0

    ac = False
    if d.ac_dugum:
        ac = ortak.oku(f"{_PS}/{d.ac_dugum}/online") == "1"

    return {
        "yuzde": yuzde,
        "durum": durum,
        "ac": ac,
        "guc": guc or 0.0,
        "saglik": (100.0 * tam / tasarim) if (tam and tasarim) else 0.0,
        "kalan_dk": kalan,
        "enerji": enerji or 0.0,
        "tam": tam or 0.0,
        "dugum": d.pil_dugum,
    }
