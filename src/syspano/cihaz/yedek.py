"""Yedek durumu (isteğe bağlı).

Varsayılan olarak gdrive-yedek projesinin durum dosyasını okur; yoksa kart
gizlenir. Yolu yapılandırmadan değiştirilebilir:

    "yedek_durum_yolu": "~/.local/state/gdrive-yedek/durum.json",
    "yedek_zamanlayici": "yedek.timer"
"""

import json
import os
import subprocess

from . import ortak

VARSAYILAN_YOL = "~/.local/state/gdrive-yedek/durum.json"
VARSAYILAN_ZAMANLAYICI = "yedek.timer"


def _sonraki_calisma(timer):
    """systemd kullanıcı zamanlayıcısının sıradaki çalışma zamanı (epoch)."""
    if not timer:
        return ""
    try:
        c = subprocess.run(
            ["systemctl", "--user", "show", timer,
             "-p", "NextElapseUSecRealtime", "--value"],
            capture_output=True, text=True, timeout=3)
        metin = c.stdout.strip()
        if metin and metin not in ("0", "n/a", "infinity"):
            return metin
    except Exception:
        pass
    return ""


def oku(d, ayar):
    yol = os.path.expanduser(ayar.get("yedek_durum_yolu") or VARSAYILAN_YOL)
    zamanlayici = ayar.get("yedek_zamanlayici", VARSAYILAN_ZAMANLAYICI)

    if not os.path.exists(yol):
        return {"yok": True}

    try:
        with open(yol) as f:
            veri = json.load(f)
    except Exception:
        return {"yok": True}

    simdi = ortak.zaman()
    if simdi - d.yedek_zaman >= 60.0:
        d.yedek_zaman = simdi
        d.yedek_sonraki = _sonraki_calisma(zamanlayici)

    veri = dict(veri)
    veri["sonraki"] = d.yedek_sonraki
    veri["yok"] = False
    return veri
