"""Kart çizimleri. Her fonksiyon verilen dikdörtgenin içine, eldeki veriye
göre uyum sağlayarak çizer (küçük kartlarda ayrıntı azalır)."""

import time

from ..cihaz.ortak import boyut_metni, sure_metni


def _baslik(ck, x, y, w, h, metin):
    ck.kart(x, y, w, h)
    if metin:
        ck.yazi(x + 12, y + 15, _kirp(ck, metin, 11, w - 24), 11, ck.renk["soluk"], True)


def _kirp(ck, metin, boyut, azami_gen):
    """Metni azami genişliğe sığdırır (sonda '…'). Tasarım birimi cinsinden."""
    s = str(metin)
    if azami_gen <= 4:
        return ""
    try:
        f = ck._yazi_tipi(boyut, False)[0]
        olcek = ck.S * ck._donusum[2]
        if f.measure(s) / olcek <= azami_gen:
            return s
        while s and f.measure(s + "…") / olcek > azami_gen:
            s = s[:-1]
        return (s + "…") if s else ""
    except Exception:
        return s


def _yok(ck, x, y, w, h, metin="veri yok"):
    ck.yazi(x + w / 2, y + h / 2, metin, 12, ck.renk["cok_soluk"], False, "center")


def _satir(ck, x, y, etiket, deger, drk=None, boy=11, gen=96, w=None):
    ck.yazi(x, y, etiket, boy, ck.renk["soluk"])
    if w is not None:
        deger = _kirp(ck, deger, boy, w - gen - 22)
    ck.yazi(x + gen, y, deger, boy, drk or ck.renk["yazi"])


def sonraki_metni(ham):
    """systemd'nin 'Thu 2026-10-08 20:07:12 +03' çıktısını okunur biçime çevirir."""
    import re
    m = re.search(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})", ham or "")
    if not m:
        return "—"
    gun = "-".join(m.groups()[:3])
    saat = m.group(4)
    if gun == time.strftime("%Y-%m-%d"):
        return f"bugün {saat}"
    if gun == time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400)):
        return f"yarın {saat}"
    return f"{m.group(3)}.{m.group(2)} {saat}"


def sicaklik_rengi(ck, c):
    return (ck.renk["kirmizi"] if c >= 90 else
            ck.renk["sari"] if c >= 75 else ck.renk["yesil"])


# ─── KPI kartları ────────────────────────────────────────────────────────────
def _kpi_duzen(y, h):
    """KPI kartı içindeki dikey konumları yüksekliğe göre hesaplar.

    Böylece çok alçak kartlarda (küçük ekran, çok satır) yazı ile çubuk
    birbirine girmez; yükseklik arttıkça daha çok satır/grafik sığar.
    """
    buyuk = max(13.0, min(32.0, h * 0.26))
    return {
        "yv": y + h * 0.38,                    # büyük değerin merkezi
        "buyuk": buyuk,
        "s1": y + h * 0.62,                    # 1. alt satır
        "s2": y + h * 0.73,                    # 2. alt satır
        "grafik": (y + h * 0.78, y + h - 20),  # grafik üst/alt
        "bar": y + h - 10,                     # çubuk üstü
        "bar_h": max(5.0, min(9.0, h * 0.05)),
        "cok_satir": h >= 150,
        "satir": h >= 80,
        "grafik_var": h >= 190,
    }


def cpu(ck, x, y, w, h, v, g):
    d = v.get("cpu") or {}
    _baslik(ck, x, y, w, h, "CPU")
    if d.get("yok"):
        return _yok(ck, x, y, w, h)
    z = _kpi_duzen(y, h)
    ck.yazi(x + 16, z["yv"], f"%{d.get('yuzde', 0):.0f}", z["buyuk"], ck.renk["mavi"], True)
    if z["satir"]:
        ck.yazi(x + 16, z["s1"], f"{d.get('ghz', 0):.2f} GHz · {d.get('cekirdek_sayisi', 0)} çekirdek",
                10.5, ck.renk["soluk"])
    if z["cok_satir"]:
        ck.yazi(x + 16, z["s2"], f"yük {' '.join(d.get('yuk', []))}", 10.5, ck.renk["soluk"])
    if z["grafik_var"]:
        ck.sparkline(x + 14, z["grafik"][0], w - 28, z["grafik"][1] - z["grafik"][0],
                     list(g["cpu"]), ck.renk["mavi"], 100)
    ck.bar(x + 14, z["bar"], w - 28, z["bar_h"], d.get("yuzde", 0), ck.renk["mavi"])


def bellek(ck, x, y, w, h, v, g):
    d = v.get("bellek") or {}
    _baslik(ck, x, y, w, h, "BELLEK")
    if d.get("yok"):
        return _yok(ck, x, y, w, h)
    z = _kpi_duzen(y, h)
    ck.yazi(x + 16, z["yv"], f"%{d.get('yuzde', 0):.0f}", z["buyuk"], ck.renk["mor"], True)
    if z["satir"]:
        ck.yazi(x + 16, z["s1"], f"{d.get('kullanilan', 0):.1f} / {d.get('toplam', 0):.1f} GiB",
                10.5, ck.renk["soluk"])
    if z["cok_satir"]:
        ck.yazi(x + 16, z["s2"],
                f"{d.get('takas_tur', 'takas')} {d.get('swap_k', 0):.1f} / {d.get('swap_t', 0):.1f} GiB",
                10.5, ck.renk["soluk"])
    if z["grafik_var"]:
        ck.sparkline(x + 14, z["grafik"][0], w - 28, z["grafik"][1] - z["grafik"][0],
                     list(g["bellek"]), ck.renk["mor"], 100)
    ck.bar(x + 14, z["bar"], w - 28, z["bar_h"], d.get("yuzde", 0), ck.renk["mor"])


def sicaklik(ck, x, y, w, h, v, g):
    d = v.get("sicaklik") or {}
    _baslik(ck, x, y, w, h, "SICAKLIK / FAN")
    if d.get("yok") or not d.get("sensor_var", True):
        return _yok(ck, x, y, w, h, "sensör bulunamadı")
    z = _kpi_duzen(y, h)
    pk = d.get("paket", 0)
    renk = sicaklik_rengi(ck, pk)
    ck.yazi(x + 16, z["yv"], f"{pk:.0f}°C", z["buyuk"], renk, True)
    yan = w >= 330 and h >= 110          # yan yana göstermek için yer var mı?
    if yan:
        yx = x + 16 + w * 0.44
        ck.yazi(yx, z["yv"] - 8, f"çekirdek {d.get('cekirdek_maks', 0):.0f}°C", 10.5, ck.renk["soluk"])
        ck.yazi(yx, z["yv"] + 9, f"fan {d.get('fan', 0):.0f} RPM", 10.5,
                ck.renk["yesil"] if d.get("fan") else ck.renk["soluk"])
    elif z["satir"]:
        ck.yazi(x + 16, z["s1"],
                f"çekirdek {d.get('cekirdek_maks', 0):.0f}°C · fan {d.get('fan', 0):.0f} RPM",
                10.5, ck.renk["soluk"])
    if z["cok_satir"] and not yan:
        ek = " · ".join(f"{a} {b:.0f}°" for a, b in (d.get("ekstra") or [])[:3] if b)
        ck.yazi(x + 16, z["s2"], ek or "—", 10.5, ck.renk["soluk"])
    elif z["cok_satir"] and yan:
        ek = " · ".join(f"{a} {b:.0f}°" for a, b in (d.get("ekstra") or [])[:3] if b)
        if ek:
            ck.yazi(x + 16, z["s1"], ek, 10.5, ck.renk["soluk"])
    if z["grafik_var"]:
        ck.sparkline(x + 14, z["grafik"][0], w - 28, z["grafik"][1] - z["grafik"][0],
                     list(g["sicaklik"]), ck.renk["sari"], 100)
    ck.bar(x + 14, z["bar"], w - 28, z["bar_h"], pk, renk)


def pil(ck, x, y, w, h, v, g):
    d = v.get("pil") or {}
    _baslik(ck, x, y, w, h, "PİL")
    if d.get("yok"):
        return _yok(ck, x, y, w, h, "pil yok (masaüstü?)")
    z = _kpi_duzen(y, h)
    py = d.get("yuzde", 0)
    renk = ck.renk["yesil"] if d.get("ac") else ck.renk["sari"]
    ck.yazi(x + 16, z["yv"], f"%{py:.0f}", z["buyuk"], renk, True)
    durum = {"Charging": "şarj oluyor", "Discharging": "boşalıyor", "Full": "dolu",
             "Not charging": "dolu (fişte)"}.get(d.get("durum"), d.get("durum", "?"))
    if z["satir"]:
        ck.yazi(x + 16, z["s1"], f"{durum} · {'fişte' if d.get('ac') else 'pilde'}",
                10.5, ck.renk["soluk"])
    if z["cok_satir"]:
        kalan = d.get("kalan_dk", 0)
        ck.yazi(x + 16, z["s2"],
                (f"kalan ~{int(kalan) // 60}sa {int(kalan) % 60}dk" if kalan
                 else f"sağlık %{d.get('saglik', 0):.0f} · {d.get('guc', 0):.1f} W"),
                10.5, ck.renk["soluk"])
    if z["grafik_var"]:
        ck.sparkline(x + 14, z["grafik"][0], w - 28, z["grafik"][1] - z["grafik"][0],
                     list(g["pil"]), renk, 100)
    ck.bar(x + 14, z["bar"], w - 28, z["bar_h"], py, renk)


# ─── çekirdekler ─────────────────────────────────────────────────────────────
def cekirdek(ck, x, y, w, h, v, g):
    d = v.get("cpu") or {}
    _baslik(ck, x, y, w, h, "ÇEKİRDEK KULLANIMI")
    cek = d.get("cekirdek") or []
    if not cek:
        return _yok(ck, x, y, w, h)
    n = len(cek)
    ic = w - 28
    bos = 6
    bw = (ic - (n - 1) * bos) / n
    ust = y + 36
    alt = y + h - 30
    yuk = max(10, alt - ust)
    cg = d.get("cekirdek_ghz") or []
    etiketli = bw >= 26
    for i, yz in enumerate(cek):
        bx = x + 14 + i * (bw + bos)
        ck.bar(bx, ust, bw, yuk, yz, ck.renk["mavi"] if yz < 80 else ck.renk["kirmizi"],
               ck.renk["icerik"])
        if etiketli:
            ck.yazi(bx + bw / 2, alt + 12, f"{i}", 9, ck.renk["cok_soluk"], cap="center")
            if i < len(cg) and bw >= 40:
                ck.yazi(bx + bw / 2, alt + 24, f"{cg[i] / 1000:.1f}G", 8,
                        ck.renk["cok_soluk"], cap="center")


# ─── geçmiş ──────────────────────────────────────────────────────────────────
def gecmis(ck, x, y, w, h, v, g):
    _baslik(ck, x, y, w, h, "GEÇMİŞ (son 4 dakika)")
    # Açıklama satırı (CPU/BELLEK/SICAKLIK) yalnızca yer varsa çizilir; eğriler
    # her zaman çizilir. Aksi hâlde küçük kartta (ör. Raspberry Pi'de 1 sütunlu
    # düzende) kart tamamen boş kalıyordu.
    aciklama = 22 if h >= 96 else 0
    ust = y + 28
    alt = y + h - 6 - aciklama
    if alt - ust < 12:
        return _yok(ck, x, y, w, h, "yer yok")
    for anahtar, renk in (("cpu", ck.renk["mavi"]), ("bellek", ck.renk["mor"]),
                          ("sicaklik", ck.renk["sari"])):
        ck.sparkline(x + 14, ust, w - 28, alt - ust, list(g[anahtar]), renk, 100, dolgu=False)
    if not aciklama:
        return
    for i, (etiket, renk) in enumerate((("CPU", ck.renk["mavi"]),
                                        ("BELLEK", ck.renk["mor"]),
                                        ("SICAKLIK", ck.renk["sari"]))):
        ex = x + 18 + i * (w / 3.4)
        if ex + 30 + len(etiket) * 7 > x + w - 6:
            break
        ck.dik(ex, y + h - 20, ex + 16, y + h - 16, renk)
        ck.yazi(ex + 22, y + h - 18, etiket, 10, ck.renk["soluk"])


# ─── GPU ─────────────────────────────────────────────────────────────────────
def gpu(ck, x, y, w, h, v, g):
    d = v.get("gpu") or {}
    _baslik(ck, x, y, w, h, "GPU")
    kartlar = d.get("kartlar") or []
    nv = d.get("nvidia")
    if d.get("yok") or (not kartlar and not nv):
        return _yok(ck, x, y, w, h, "GPU bulunamadı")

    alt = y + h - 8
    yy = y + 34
    gosterilecek = kartlar[:1 if h < 200 else 2]
    for k in gosterilecek:
        # Çok kısa kartta bile en azından model yazılsın (boş kart kalmasın)
        if yy + 14 > alt:
            break
        kullanim = k.get("kullanim")
        renk = ck.renk["yesil"] if (kullanim or 0) < 70 else ck.renk["sari"]
        ck.yazi(x + 16, yy, k.get("model", k.get("ad", "GPU"))[:22], 10.5, ck.renk["soluk"])
        yy += 18
        if yy + 14 > alt:
            break
        ck.yazi(x + 16, yy, (f"%{kullanim:.0f}" if kullanim is not None else "—"),
                17, renk, True)
        ayrinti = []
        if k.get("mhz"):
            ayrinti.append(f"{k['mhz']:.0f} MHz")
        if k.get("sicaklik"):
            ayrinti.append(f"{k['sicaklik']:.0f}°C")
        ck.yazi(x + 78, yy, " · ".join(ayrinti) or k.get("surucu", ""), 10.5, ck.renk["soluk"])
        yy += 26

    if nv and yy + 26 <= alt:
        durum = nv.get("durum") or "?"
        ck.yazi(x + 16, yy, (nv.get("model") or "NVIDIA")[:22], 10.5, ck.renk["soluk"])
        ck.yazi(x + w - 16, yy, durum, 10.5,
                {"kullanılıyor": ck.renk["yesil"], "yeni kullanıldı": ck.renk["sari"],
                 "boşta": ck.renk["soluk"]}.get(durum, ck.renk["kirmizi"]), True, "e")
        yy += 18
        yz = nv.get("yuzde") or 0.0
        ck.yazi(x + 16, yy, f"%{yz:.0f}", 17,
                ck.renk["yesil"] if yz >= 1 else ck.renk["soluk"], True)
        ck.yazi(x + 78, yy, f"{nv.get('sicaklik', 0):.0f}°C "
               f"{nv.get('vram', 0):.0f}/{nv.get('vram_toplam', 0):.0f} MiB "
               f"{nv.get('pstate', '?')}", 10.5, ck.renk["soluk"])
        yy += 24
        if yy + 14 <= alt:
            kul = nv.get("surecler") or []
            if kul:
                satir = f"{kul[0][0]} · {kul[0][1]:.0f} MiB" + (f" +{len(kul) - 1}" if len(kul) > 1 else "")
            elif nv.get("tepe", 0) >= 5:
                satir = f"son 30 sn tepe %{nv['tepe']:.0f}"
            elif nv.get("son_kullanim") is not None:
                satir = f"son kullanım {sure_metni(nv['son_kullanim'])}"
            else:
                satir = "kullanan süreç yok"
            ck.yazi(x + 16, yy, satir[:34], 9.5, ck.renk["cok_soluk"])
            yy += 16

    # grafik (yer varsa)
    if alt - yy > 40:
        ck.sparkline(x + 14, yy, w - 28, min(44, alt - yy - 4),
                     list(g["dgpu"] or g["gpu"]), ck.renk["mor"], 100)


# ─── disk / ağ ───────────────────────────────────────────────────────────────
def disk_ag(ck, x, y, w, h, v, g):
    d = v.get("disk") or {}
    a = v.get("ag") or {}
    bel = v.get("bellek") or {}
    _baslik(ck, x, y, w, h, "DİSK / AĞ")
    if d.get("yok") and a.get("yok"):
        return _yok(ck, x, y, w, h)

    alt = y + h - 6
    yy = y + 34
    ck.yazi(x + 16, yy, d.get("model", d.get("aygit", "disk"))[:24], 10, ck.renk["soluk"])
    yy += 20
    if yy + 16 > alt:
        return
    ck.yazi(x + 16, yy, f"{d.get('okuma', 0):.1f} / {d.get('yazma', 0):.1f} MB/sn",
            13.5, ck.renk["yazi"], True)
    yy += 20
    if yy + 30 <= alt:
        ck.bar(x + 16, yy, w - 32, 6, d.get("dolu", 0), ck.renk["mavi"])
        ck.yazi(x + 16, yy + 15, f"dolu %{d.get('dolu', 0):.0f} · boş {d.get('bos_gb', 0):.0f} GB",
                10, ck.renk["soluk"])
        yy += 32
    if yy + 34 <= alt and not a.get("yok"):
        ikon = "wifi" if a.get("tur") == "wifi" else "eth"
        ck.yazi(x + 16, yy, f"ağ {a.get('arayuz', '-')} ({ikon}) {a.get('ip', '-')}",
                10, ck.renk["soluk"])
        yy += 17
        if yy + 16 <= alt:
            ck.yazi(x + 16, yy, f"↓ {a.get('inen', 0):.0f} KB/sn", 11.5, ck.renk["yesil"], True)
            ck.yazi(x + 16 + (w - 32) / 2, yy, f"↑ {a.get('giden', 0):.0f} KB/sn",
                    11.5, ck.renk["sari"], True)
            yy += 18
    if yy + 12 <= alt:
        ck.bar(x + 16, alt - 8, w - 32, 5, bel.get("yuzde", 0), ck.renk["mor"])


# ─── süreçler ────────────────────────────────────────────────────────────────
def surecler(ck, x, y, w, h, v, g):
    d = v.get("surecler") or {}
    _baslik(ck, x, y, w, h, "EN ÇOK CPU KULLANAN SÜREÇLER")
    liste = d.get("liste") or []
    if not liste:
        return _yok(ck, x, y, w, h, "ölçülüyor…")
    satirlar = max(1, int((h - 40) // 20))
    for i, (yz, ad, rss) in enumerate(liste[:satirlar]):
        yy = y + 40 + i * 20
        ck.yazi(x + 16, yy, ad[:22], 11, ck.renk["yazi"])
        ck.yazi(x + w - 16, yy, f"%{yz:.1f}",
                11, ck.renk["kirmizi"] if yz > 50 else ck.renk["soluk"], cap="e")
        ck.bar(x + 16, yy + 9, w - 32, 3, min(100.0, yz),
               ck.renk["mavi"] if yz < 50 else ck.renk["kirmizi"])


# ─── yedek ───────────────────────────────────────────────────────────────────
def yedek(ck, x, y, w, h, v, g):
    d = v.get("yedek") or {}
    _baslik(ck, x, y, w, h, "YEDEK")
    if d.get("yok"):
        return _yok(ck, x, y, w, h, "kurulmadı")

    yd = d.get("durum", "yok")
    ybas = float(d.get("baslangic") or 0)
    ybit = float(d.get("bitis") or 0)
    now = time.time()
    gecen = (now - ybas) if ybas else 0.0
    yas = (now - ybit) if ybit else 0.0
    ybaslik, yrenk = {
        "calisiyor": ("ÇALIŞIYOR", ck.renk["mavi"]),
        "basarili": ("GÜNCEL", ck.renk["yesil"]),
        "hata": ("HATA", ck.renk["kirmizi"]),
    }.get(yd, ("BİLİNMİYOR", ck.renk["soluk"]))

    alt = y + h - 6
    yy = y + 30
    ck.yazi(x + 16, yy, ybaslik, max(14.0, min(22.0, h * 0.22)), yrenk, True)
    yy += max(16.0, min(24.0, h * 0.24))
    if yy + 10 <= alt:
        ck.bar(x + 16, yy, w - 32, 6,
               max(0.0, min(100.0, 100.0 * (1 - yas / 86400))), yrenk)
        yy += 22

    tum = [("son yedek", sure_metni(yas) if yas else "—"),
           ("Drive'da", f"{int(d.get('toplam_dosya') or 0)} dosya"),
           ("boyut", boyut_metni(d.get("toplam_bayt"))),
           ("sıradaki", sonraki_metni(d.get("sonraki")))]
    if yd == "calisiyor":
        tum.append(("sürüyor", f"{int(gecen) // 60} dk · {int(d.get('yuklenen') or 0)} dosya"))
    elif yd == "hata":
        tum.append(("hata", (d.get("hata") or "bilinmeyen")[:26]))
    else:
        ysure = int(d.get("sure_sn") or 0)
        tum.append(("son süre", f"{ysure // 60} dk {ysure % 60} sn"))

    for et, dg in tum:
        if yy > alt:
            break
        _satir(ck, x + 16, yy, et, dg, ck.renk["kirmizi"] if et == "hata" else None,
               10.5, 74, w - 32)
        yy += 18


# ─── servisler (systemd) ─────────────────────────────────────────────────────
#  Sunucu makinelerde Apache/MySQL/nginx gibi servislerin durumu. Satırlar
#  tıklanabilir: dokununca o servisin günlüğü açılır. Pano, satır
#  dikdörtgenlerini bu listeden okur (her karede yeniden doldurulur).
TIKLANABILIR = []          # [(eylem, (x, y, w, h)), ...]


def servis_rengi(ck, durum):
    return {"active": ck.renk["yesil"], "reloading": ck.renk["sari"],
            "activating": ck.renk["sari"], "deactivating": ck.renk["sari"],
            "failed": ck.renk["kirmizi"]}.get(durum, ck.renk["cok_soluk"])


def sure_kisa(sn):
    """Saniyeyi kısa biçime çevirir: '12dk', '31sa', '3g'."""
    sn = max(0, int(sn))
    if sn < 3600:
        return f"{sn // 60}dk"
    if sn < 86400:
        return f"{sn // 3600}sa"
    return f"{sn // 86400}g"


def bellek_kisa(bayt):
    if not bayt:
        return ""
    return (f"{bayt / 1024:.0f} KB" if bayt < 1048576 else f"{bayt / 1048576:.0f} MB")


def yas_kisa(sn):
    """'şimdi', '12dk', '3sa', '2g' — günlüğün son yazılma yaşı."""
    sn = max(0, int(sn))
    if sn < 90:
        return "şimdi"
    if sn < 3600:
        return f"{sn // 60}dk"
    if sn < 86400:
        return f"{sn // 3600}sa"
    return f"{sn // 86400}g"


def boyut_kisa(bayt):
    """'512B', '12KB', '1.2MB', '3.4GB'."""
    b = float(bayt or 0)
    if b < 1024:
        return f"{b:.0f}B"
    for birim in ("KB", "MB", "GB"):
        b /= 1024
        if b < 1024:
            return f"{b:.0f}{birim}" if b >= 10 else f"{b:.1f}{birim}"
    return f"{b:.0f}TB"


def _servis_sirala(birimler):
    """Önce bozuklar, sonra çalışanlar, sonra durmuşlar gelsin."""
    sira = {"failed": 0, "activating": 1, "active": 2, "reloading": 2,
            "deactivating": 3, "inactive": 4}
    return sorted(birimler, key=lambda b: (sira.get(b.get("durum"), 5),
                                           b.get("etiket", "")))


def kalan_sayi(birimler, sigar):
    """Sığmayan öğe sayısı (yardımcı)."""
    return max(0, len(birimler) - sigar)


def _liste_yerlesimi(ust, alt, adet):
    """Liste kartları için (satır yüksekliği, sığan satır sayısı).

    Liste taşıyorsa altta **"+N daha"** satırına yer ayrılır: aksi hâlde o yazı
    son satırın üstüne biniyordu (Raspberry Pi 800×480 panelinde görüldü:
    "Bluetooth" satırı ile "+7 servis daha" iç içe geçiyordu).
    """
    def hesapla(yer):
        satir_h = max(24.0, min(40.0, yer / max(3, min(6, adet))))
        return satir_h, max(1, int(yer // satir_h))

    yer = max(20.0, alt - ust)
    satir_h, sigar = hesapla(yer)
    if adet > sigar:                      # "+N daha" yazılacak → yer ayır
        satir_h, sigar = hesapla(max(20.0, yer - 18.0))
    return satir_h, sigar


def servisler(ck, x, y, w, h, v, g):
    d = v.get("servisler") or {}
    _baslik(ck, x, y, w, h, "SERVİSLER")
    if d.get("yok"):
        return _yok(ck, x, y, w, h, "systemd bulunamadı")
    birimler = _servis_sirala(d.get("birimler") or [])
    if not birimler:
        return _yok(ck, x, y, w, h, "servis bulunamadı")

    ust, alt = y + 34, y + h - 6
    satir_h, sigar = _liste_yerlesimi(ust, alt, len(birimler))
    simdi = time.time()

    for i, s in enumerate(birimler[:sigar]):
        sy = ust + i * satir_h
        cy = sy + satir_h / 2
        durum = s.get("durum")
        ck.oval(x + 15, cy - 5, x + 25, cy + 5, servis_rengi(ck, durum))
        ck.yazi(x + 34, cy, _kirp(ck, s.get("etiket", "?"), 11, w - 34 - 92),
                11, ck.renk["yazi"])
        if durum == "active":
            parcalar = []
            if s.get("baslama"):
                parcalar.append(sure_kisa(simdi - s["baslama"]))
            bellek = bellek_kisa(s.get("bellek"))
            if bellek:
                parcalar.append(bellek)
            ayrinti, arenk = " · ".join(parcalar) or (s.get("alt") or ""), ck.renk["soluk"]
        elif durum == "failed":
            ayrinti, arenk = "BOZUK", ck.renk["kirmizi"]
        else:
            ayrinti, arenk = "kapalı", ck.renk["cok_soluk"]
        ck.yazi(x + w - 12, cy, ayrinti, 10.5, arenk, durum == "failed", "e")
        TIKLANABILIR.append((("log", s.get("ad")), (x + 2, sy, w - 4, satir_h)))

    # Kartta yer yetmeyen servisler için: alt satıra dokunmak **tam listeyi** açar
    if len(birimler) > sigar and y + h - 12 >= ust + sigar * satir_h + 10:
        sy = y + h - 20
        ck.yazi(x + 34, y + h - 12,
                _kirp(ck, f"⋯ {len(birimler) - sigar} servis daha — tümünü gör",
                      10, w - 46), 10, ck.renk["mavi"])
        TIKLANABILIR.append((("servis_listesi", None), (x + 2, sy, w - 4, 20)))


# ─── günlükler (geliştirici log dosyaları) ───────────────────────────────────
# Grup → nokta rengi (tema anahtarı)
GUNLUK_RENGI = {"php": "mor", "uygulama": "turkuaz", "apache": "sari",
                "nginx": "yesil", "veritabani": "mavi", "sunucu": "cok_soluk",
                "ozel": "mavi"}


def loglar(ck, x, y, w, h, v, g):
    d = v.get("loglar") or {}
    _baslik(ck, x, y, w, h, "GÜNLÜKLER")
    kaynaklar = d.get("kaynaklar") or []
    if d.get("yok") or not kaynaklar:
        return _yok(ck, x, y, w, h, "günlük dosyası bulunamadı")

    ust, alt = y + 34, y + h - 6
    satir_h, sigar = _liste_yerlesimi(ust, alt, len(kaynaklar))
    simdi = time.time()

    for i, k in enumerate(kaynaklar[:sigar]):
        sy = ust + i * satir_h
        cy = sy + satir_h / 2
        ck.oval(x + 15, cy - 5, x + 25, cy + 5,
                ck.renk[GUNLUK_RENGI.get(k.get("grup"), "soluk")])
        ck.yazi(x + 34, cy, _kirp(ck, k.get("etiket", "?"), 11, w - 34 - 118),
                11, ck.renk["yazi"])
        if k.get("tur") == "journal":
            # dosya değil: journald'a yazan servis (boyut/yaş yok)
            ayrinti, arenk = "journal", ck.renk["turkuaz"]
        elif not k.get("okunabilir"):
            ayrinti, arenk = "izin yok", ck.renk["kirmizi"]
        else:
            ayrinti = f"{yas_kisa(simdi - (k.get('son') or simdi))} · {boyut_kisa(k.get('boyut'))}"
            arenk = ck.renk["yesil"] if simdi - (k.get("son") or 0) < 90 else ck.renk["soluk"]
        ck.yazi(x + w - 12, cy, ayrinti, 10.5, arenk, False, "e")
        if k.get("tur") == "journal":
            eylem = ("log_journal", k.get("birim"))
        else:
            eylem = ("log_dosya", k.get("yol"))
        TIKLANABILIR.append((eylem, (x + 2, sy, w - 4, satir_h)))

    if len(kaynaklar) > sigar and y + h - 12 >= ust + sigar * satir_h + 10:
        ck.yazi(x + 34, y + h - 12, f"+{len(kaynaklar) - sigar} günlük daha", 10,
                ck.renk["cok_soluk"])


# ─── Pi sağlığı (throttle / düşük voltaj) ────────────────────────────────────
def pisaglik(ck, x, y, w, h, v, g):
    d = v.get("pisaglik") or {}
    _baslik(ck, x, y, w, h, "Pİ SAĞLIĞI")
    if d.get("yok"):
        return _yok(ck, x, y, w, h, "vcgencmd yok")
    alt = y + h - 8
    yy = y + 40

    if d.get("simdi_var"):
        ana = "⚠ " + ", ".join(e for _a, e in d["simdi"]).upper()
        renk = ck.renk["kirmizi"]
    elif d.get("gecmis_var"):
        ana, renk = "✓ Şu an normal", ck.renk["yesil"]
    else:
        ana, renk = "✓ Normal", ck.renk["yesil"]
    if yy <= alt:
        ck.yazi(x + 16, yy, _kirp(ck, ana, 15, w - 32), 15, renk, True)
        yy += 24

    ayrinti = []
    if d.get("gerilim"):
        ayrinti.append(f"{d['gerilim']:.2f} V")
    if d.get("ghz"):
        ayrinti.append(f"{d['ghz']:.2f} GHz")
    if d.get("ham"):
        ayrinti.append(d["ham"])
    if ayrinti and yy + 14 <= alt:
        ck.yazi(x + 16, yy, " · ".join(ayrinti), 10.5, ck.renk["soluk"])
        yy += 18

    if d.get("gecmis_var") and yy + 14 <= alt:
        gecmis = ", ".join(e for _a, e in d["gecmis"])
        ck.yazi(x + 16, yy, _kirp(ck, f"geçmişte: {gecmis}", 10.5, w - 32),
                10.5, ck.renk["sari"])


# ─── sistem ──────────────────────────────────────────────────────────────────
def sistem(ck, x, y, w, h, v, g):
    d = v.get("sistem") or {}
    _baslik(ck, x, y, w, h, "SİSTEM")
    ust = int(d.get("uptime_sn") or 0)
    satirlar = [
        ("ad", d.get("ad", "-")),
        ("dağıtım", d.get("dagitim", "-")),
        ("çekirdek", (d.get("cekirdek") or "-")[:22]),
        ("mimari", d.get("mimari", "-")),
        ("çalışma", f"{ust // 86400}g {(ust % 86400) // 3600}sa {(ust % 3600) // 60}dk"),
        ("oturum", f"{d.get('oturum', '-')} · {d.get('masaustu', '-') or '-'}"),
    ]
    makine = d.get("makine") or d.get("islemci") or ""
    yy = y + 40
    for et, dg in satirlar:
        if yy > y + h - 14:
            break
        _satir(ck, x + 16, yy, et, dg, None, 11, 84, w - 32)
        yy += 20
    if makine and yy <= y + h - 14:
        ck.yazi(x + 16, yy, _kirp(ck, makine, 10, w - 32), 10, ck.renk["cok_soluk"])


CIZIM = {
    "cpu": cpu, "bellek": bellek, "sicaklik": sicaklik, "pil": pil,
    "cekirdek": cekirdek, "gecmis": gecmis, "gpu": gpu, "disk_ag": disk_ag,
    "surecler": surecler, "servisler": servisler, "loglar": loglar,
    "pisaglik": pisaglik, "yedek": yedek, "sistem": sistem,
}
