"""Sistem bilgisi: ana makine adı, çekirdek, çalışma süresi, dağıtım, model."""

import os

from . import ortak
from .. import ortam


def _uptime():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0


def oku(d, ayar):
    if not d.sistem_arandi:
        d.sistem_bilgi = {
            "makine": ortam.makine_modeli(),
            "islemci": ortam.islemci_adi(),
            "dagitim": ortam.dagitim(),
        }
        d.sistem_arandi = True

    bilgi = dict(d.sistem_bilgi)
    bilgi.update({
        "ad": os.uname().nodename,
        "cekirdek": os.uname().release,
        "mimari": os.uname().machine,
        "uptime_sn": _uptime(),
        "oturum": ortam.oturum_tipi(),
        "masaustu": ortam.masaustu(),
        "kullanici": os.environ.get("USER", "?"),
    })
    return bilgi
