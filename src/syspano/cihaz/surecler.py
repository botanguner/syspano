"""Süreçler: en çok CPU kullanan ilk N süreç.

**Performans:** `/proc/<pid>/stat` taraması pahalıdır (yüzlerce dosya), bu
yüzden en fazla `ARALIK` saniyede bir yapılır; arada son sonuç döndürülür.
Yüzdeler bu aralık üzerinden hesaplandığı için hem daha ucuz hem daha az
dalgalı olur.
"""

import os

from . import ortak

ARALIK = 3.0        # saniye; daha sık taramaya gerek yok

try:
    SAYFA_BOYU = os.sysconf("SC_PAGE_SIZE")
except Exception:
    SAYFA_BOYU = 4096
try:
    JIFFY = os.sysconf("SC_CLK_TCK")
except Exception:
    JIFFY = 100


def _ornek():
    """{pid: (ad, cpu_jiffies_toplam, rss_bayt)} — /proc bir kez taranır."""
    sonuc = {}
    try:
        girdiler = list(os.scandir("/proc"))
    except Exception:
        return sonuc
    for girdi in girdiler:
        ad_pid = girdi.name
        if not ad_pid.isdigit():
            continue
        try:
            with open(f"/proc/{ad_pid}/stat", "rb") as f:
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
        sonuc[ad_pid] = (ad, utime + stime, rss)
    return sonuc


def oku(d, ayar):
    simdi = ortak.zaman()
    if d.surec_sonuc and simdi - d.surec_son < ARALIK:
        return d.surec_sonuc

    yeni = _ornek()
    sonuc = []
    dt = 0.0
    if d.surec_onceki:
        dt = simdi - d.surec_onceki[1]
        if dt > 0:
            for pid, (ad, jiffies, rss) in yeni.items():
                once = d.surec_onceki[0].get(pid)
                if not once:
                    continue
                fark = jiffies - once[1]
                if fark <= 0:
                    continue
                sonuc.append((100.0 * (fark / JIFFY) / dt, ad, pid, rss))
    d.surec_onceki = (yeni, simdi)
    sonuc.sort(reverse=True)

    d.surec_sonuc = {
        "liste": [(round(y, 1), ad, bayt) for y, ad, _, bayt in sonuc[:10]],
        "toplam": len(yeni),
        "olcum_sn": round(dt, 2),
    }
    d.surec_son = simdi
    return d.surec_sonuc
