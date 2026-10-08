"""Süreçler: en çok CPU kullanan ilk N süreç (iki örnek arasındaki farktan)."""

import os

from . import ortak

SAYFA_BOYU = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def _ornek():
    """{pid: (ad, cpu_jiffies_toplam, rss_bayt)}"""
    sonuc = {}
    try:
        pidler = [p for p in os.listdir("/proc") if p.isdigit()]
    except Exception:
        return sonuc
    for pid in pidler:
        try:
            with open(f"/proc/{pid}/stat", "rb") as f:
                veri = f.read().decode("utf-8", "ignore")
        except Exception:
            continue
        # comm parantez içinde ve boşluk içerebilir; son ')' dan sonrasını al
        kapanis = veri.rfind(")")
        if kapanis < 0:
            continue
        ad = veri[veri.find("(") + 1:kapanis]
        alanlar = veri[kapanis + 2:].split()
        try:
            utime, stime = int(alanlar[11]), int(alanlar[12])
            rss = int(alanlar[21]) * SAYFA_BOYU
        except (IndexError, ValueError):
            continue
        sonuc[pid] = (ad, utime + stime, rss)
    return sonuc


def oku(d, ayar):
    yeni = _ornek()
    hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    sonuc = []
    if d.surec_onceki:
        dt = ortak.zaman() - d.surec_onceki[1]
        if dt > 0:
            for pid, (ad, jiffies, rss) in yeni.items():
                once = d.surec_onceki[0].get(pid)
                if not once:
                    continue
                fark = jiffies - once[1]
                if fark <= 0:
                    continue
                yuzde = 100.0 * (fark / hz) / dt
                sonuc.append((yuzde, ad, pid, rss))
    d.surec_onceki = (yeni, ortak.zaman())

    sonuc.sort(reverse=True)
    # aynı adı taşıyan süreçleri topla (ör. birçok python)
    return {"liste": [(round(y, 1), ad, bayt) for y, ad, _, bayt in sonuc[:10]],
            "toplam": len(yeni)}
