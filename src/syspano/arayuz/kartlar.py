"""Kart çizimleri. Her fonksiyon verilen dikdörtgenin içine, eldeki veriye
göre uyum sağlayarak çizer (küçük kartlarda ayrıntı azalır)."""

import time

from ..cihaz.ortak import boyut_metni, sure_metni


def _baslik(ck, x, y, w, h, metin):
    ck.kart(x, y, w, h)
    if metin:
        ck.yazi(x + 12, y + 15, metin, 11, ck.renk["soluk"], True)


def _yok(ck, x, y, w, h, metin="veri yok"):
    ck.yazi(x + w / 2, y + h / 2, metin, 12, ck.renk["cok_soluk"], False, "center")


def _satir(ck, x, y, etiket, deger, drk=None, boy=11, gen=96):
    ck.yazi(x, y, etiket, boy, ck.renk["soluk"])
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
def cpu(ck, x, y, w, h, v, g):
    d = v.get("cpu") or {}
    _baslik(ck, x, y, w, h, "CPU")
    if d.get("yok"):
        return _yok(ck, x, y, w, h)
    kucuk = h < 150
    yv, boy = (y + 44, 22) if kucuk else (y + 56, 30)
    ck.yazi(x + 16, yv, f"%{d.get('yuzde', 0):.0f}", boy, ck.renk["mavi"], True)
    ck.yazi(x + 16, yv + 24, f"{d.get('ghz', 0):.2f} GHz · {d.get('cekirdek_sayisi', 0)} çekirdek",
            11, ck.renk["soluk"])
    if not kucuk:
        ck.yazi(x + 16, yv + 42, f"yük {' '.join(d.get('yuk', []))}", 11, ck.renk["soluk"])
    alt = y + h - 22
    if h >= 175:
        ck.sparkline(x + 14, yv + 58, w - 28, alt - (yv + 66), list(g["cpu"]),
                     ck.renk["mavi"], 100)
    ck.bar(x + 14, alt, w - 28, 8, d.get("yuzde", 0), ck.renk["mavi"])


def bellek(ck, x, y, w, h, v, g):
    d = v.get("bellek") or {}
    _baslik(ck, x, y, w, h, "BELLEK")
    if d.get("yok"):
        return _yok(ck, x, y, w, h)
    kucuk = h < 150
    yv, boy = (y + 44, 22) if kucuk else (y + 56, 30)
    ck.yazi(x + 16, yv, f"%{d.get('yuzde', 0):.0f}", boy, ck.renk["mor"], True)
    ck.yazi(x + 16, yv + 24, f"{d.get('kullanilan', 0):.1f} / {d.get('toplam', 0):.1f} GiB",
            11, ck.renk["soluk"])
    if not kucuk:
        ck.yazi(x + 16, yv + 42,
                f"{d.get('takas_tur', 'takas')} {d.get('swap_k', 0):.1f} / {d.get('swap_t', 0):.1f} GiB",
                11, ck.renk["soluk"])
    alt = y + h - 22
    if h >= 175:
        ck.sparkline(x + 14, yv + 58, w - 28, alt - (yv + 66), list(g["bellek"]),
                     ck.renk["mor"], 100)
    ck.bar(x + 14, alt, w - 28, 8, d.get("yuzde", 0), ck.renk["mor"])


def sicaklik(ck, x, y, w, h, v, g):
    d = v.get("sicaklik") or {}
    _baslik(ck, x, y, w, h, "SICAKLIK / FAN")
    if d.get("yok") or not d.get("sensor_var", True):
        return _yok(ck, x, y, w, h, "sensör bulunamadı")
    kucuk = h < 150
    pk = d.get("paket", 0)
    yv, boy = (y + 44, 22) if kucuk else (y + 56, 30)
    ck.yazi(x + 16, yv, f"{pk:.0f}°C", boy, sicaklik_rengi(ck, pk), True)
    ck.yazi(x + 16 + (92 if not kucuk else 70), yv - 6,
            f"çekirdek {d.get('cekirdek_maks', 0):.0f}°C", 11, ck.renk["soluk"])
    ck.yazi(x + 16 + (92 if not kucuk else 70), yv + 12,
            f"fan {d.get('fan', 0):.0f} RPM",
            11, ck.renk["yesil"] if d.get("fan") else ck.renk["soluk"])
    if not kucuk:
        ek = " · ".join(f"{a} {b:.0f}°" for a, b in (d.get("ekstra") or [])[:3] if b)
        ck.yazi(x + 16, yv + 42, ek or "—", 11, ck.renk["soluk"])
    alt = y + h - 22
    if h >= 175:
        ck.sparkline(x + 14, yv + 58, w - 28, alt - (yv + 66), list(g["sicaklik"]),
                     ck.renk["sari"], 100)
    ck.bar(x + 14, alt, w - 28, 8, pk, sicaklik_rengi(ck, pk))


def pil(ck, x, y, w, h, v, g):
    d = v.get("pil") or {}
    _baslik(ck, x, y, w, h, "PİL")
    if d.get("yok"):
        return _yok(ck, x, y, w, h, "pil yok (masaüstü?)")
    kucuk = h < 150
    py = d.get("yuzde", 0)
    renk = ck.renk["yesil"] if d.get("ac") else ck.renk["sari"]
    yv, boy = (y + 44, 22) if kucuk else (y + 56, 30)
    ck.yazi(x + 16, yv, f"%{py:.0f}", boy, renk, True)
    durum = {"Charging": "şarj oluyor", "Discharging": "boşalıyor", "Full": "dolu",
             "Not charging": "dolu (fişte)"}.get(d.get("durum"), d.get("durum", "?"))
    ck.yazi(x + 16, yv + 24, f"{durum} · {'fişte' if d.get('ac') else 'pilde'}",
            11, ck.renk["soluk"])
    if not kucuk:
        kalan = d.get("kalan_dk", 0)
        ck.yazi(x + 16, yv + 42,
                (f"kalan ~{int(kalan) // 60}sa {int(kalan) % 60}dk" if kalan
                 else f"sağlık %{d.get('saglik', 0):.0f} · {d.get('guc', 0):.1f} W"),
                11, ck.renk["soluk"])
    alt = y + h - 22
    if h >= 175:
        ck.sparkline(x + 14, yv + 58, w - 28, alt - (yv + 66), list(g["pil"]), renk, 100)
    ck.bar(x + 14, alt, w - 28, 8, py, renk)


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
    ust = y + 30
    alt = y + h - 34
    if alt - ust < 20:
        return
    for anahtar, renk in (("cpu", ck.renk["mavi"]), ("bellek", ck.renk["mor"]),
                          ("sicaklik", ck.renk["sari"])):
        ck.sparkline(x + 14, ust, w - 28, alt - ust, list(g[anahtar]), renk, 100, dolgu=False)
    for i, (etiket, renk) in enumerate((("CPU", ck.renk["mavi"]),
                                        ("BELLEK", ck.renk["mor"]),
                                        ("SICAKLIK", ck.renk["sari"]))):
        ex = x + 18 + i * (w / 3.4)
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

    yy = y + 40
    for k in kartlar[:2]:
        kullanim = k.get("kullanim")
        ck.yazi(x + 16, yy, k.get("model", k.get("ad", "GPU"))[:24], 11, ck.renk["soluk"])
        renk = ck.renk["yesil"] if (kullanim or 0) < 70 else ck.renk["sari"]
        ck.yazi(x + 16, yy + 24, (f"%{kullanim:.0f}" if kullanim is not None else "—"),
                20, renk, True)
        ayrinti = []
        if k.get("mhz"):
            ayrinti.append(f"{k['mhz']:.0f} MHz")
        if k.get("sicaklik"):
            ayrinti.append(f"{k['sicaklik']:.0f}°C")
        ck.yazi(x + 96, yy + 24, " · ".join(ayrinti) or k.get("surucu", ""), 11,
                ck.renk["soluk"])
        yy += 52

    if nv:
        durum = nv.get("durum") or "?"
        ck.yazi(x + 16, yy + 4, (nv.get("model") or "NVIDIA")[:24], 11, ck.renk["soluk"])
        ck.yazi(x + w - 16, yy + 4, durum, 11,
                {"kullanılıyor": ck.renk["yesil"], "yeni kullanıldı": ck.renk["sari"],
                 "boşta": ck.renk["soluk"]}.get(durum, ck.renk["kirmizi"]), True, "e")
        yz = nv.get("yuzde") or 0.0
        ck.yazi(x + 16, yy + 30, f"%{yz:.0f}", 20,
                ck.renk["yesil"] if yz >= 1 else ck.renk["soluk"], True)
        ck.yazi(x + 84, yy + 30,
                f"{nv.get('sicaklik', 0):.0f}°C · {nv.get('vram', 0):.0f}/"
                f"{nv.get('vram_toplam', 0):.0f} MiB · {nv.get('pstate', '?')}",
                11, ck.renk["soluk"])
        kul = nv.get("surecler") or []
        if kul:
            satir = f"{kul[0][0]} · {kul[0][1]:.0f} MiB" + (f" +{len(kul) - 1}" if len(kul) > 1 else "")
        elif nv.get("tepe", 0) >= 5:
            satir = f"son 30 sn tepe %{nv['tepe']:.0f}"
        elif nv.get("son_kullanim") is not None:
            satir = f"son kullanım {sure_metni(nv['son_kullanim'])}"
        else:
            satir = "kullanan süreç yok"
        ck.yazi(x + 16, yy + 50, satir[:34], 10, ck.renk["cok_soluk"])
        yy += 66

    # grafik (yer varsa)
    if h - (yy - y) > 62:
        ck.dik(x + 14, yy, x + w - 14, yy + min(60, h - (yy - y) - 26),
               ck.renk["icerik"], ck.renk["kenar"])
        ck.sparkline(x + 14, yy, w - 28, min(60, h - (yy - y) - 26),
                     list(g["dgpu"] or g["gpu"]), ck.renk["mor"], 100)


# ─── disk / ağ ───────────────────────────────────────────────────────────────
def disk_ag(ck, x, y, w, h, v, g):
    d = v.get("disk") or {}
    a = v.get("ag") or {}
    bel = v.get("bellek") or {}
    _baslik(ck, x, y, w, h, "DİSK / AĞ")
    if d.get("yok") and a.get("yok"):
        return _yok(ck, x, y, w, h)

    yy = y + 40
    ck.yazi(x + 16, yy, d.get("model", "disk")[:26], 11, ck.renk["soluk"])
    ck.yazi(x + 16, yy + 26, f"{d.get('okuma', 0):.1f} / {d.get('yazma', 0):.1f} MB/sn",
            14, ck.renk["yazi"], True)
    ck.bar(x + 16, yy + 42, w - 32, 6, d.get("dolu", 0), ck.renk["mavi"])
    ck.yazi(x + 16, yy + 60, f"disk dolu %{d.get('dolu', 0):.0f} · boş {d.get('bos_gb', 0):.0f} GB",
            11, ck.renk["soluk"])

    yy2 = yy + 88
    if not a.get("yok"):
        ikon = "wifi" if a.get("tur") == "wifi" else "eth"
        ck.yazi(x + 16, yy2, f"ağ: {a.get('arayuz', '-')} ({ikon})  {a.get('ip', '-')}",
                11, ck.renk["soluk"])
        ck.yazi(x + 16, yy2 + 26, f"↓ {a.get('inen', 0):.0f} KB/sn", 13, ck.renk["yesil"], True)
        ck.yazi(x + 16 + (w - 32) / 2, yy2 + 26, f"↑ {a.get('giden', 0):.0f} KB/sn",
                13, ck.renk["sari"], True)
        ck.bar(x + 16, yy2 + 46, w - 32, 6,
               min(100.0, a.get("inen", 0) / 100.0), ck.renk["yesil"])
    if h - (yy2 + 60 - y) > 20:
        ck.bar(x + 16, y + h - 20, w - 32, 6, bel.get("yuzde", 0), ck.renk["mor"])


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
    if yd == "calisiyor":
        ybaslik, yrenk = "ÇALIŞIYOR", ck.renk["mavi"]
    elif yd == "basarili":
        ybaslik, yrenk = "GÜNCEL", ck.renk["yesil"]
    elif yd == "hata":
        ybaslik, yrenk = "HATA", ck.renk["kirmizi"]
    else:
        ybaslik, yrenk = "BİLİNMİYOR", ck.renk["soluk"]

    yy = y + 46
    ck.yazi(x + 16, yy, "şifreli yedek (Drive)", 11, ck.renk["soluk"])
    ck.yazi(x + 16, yy + 34, ybaslik, 24, yrenk, True)
    ck.bar(x + 16, yy + 52, w - 32, 6,
           max(0.0, min(100.0, 100.0 * (1 - yas / 86400))), yrenk)

    def ys(dy, et, dg, drk=None):
        _satir(ck, x + 16, yy + dy, et, dg, drk, 11, 84)

    ys(78, "son yedek", sure_metni(yas) if yas else "—")
    ys(100, "Drive'da", f"{int(d.get('toplam_dosya') or 0)} dosya")
    ys(122, "boyut", boyut_metni(d.get("toplam_bayt")))
    ys(144, "sıradaki", sonraki_metni(d.get("sonraki")))
    if h - (yy + 160 - y) > 10:
        if yd == "calisiyor":
            ys(166, "sürüyor",
               f"{int(gecen) // 60} dk {int(gecen) % 60} sn · {int(d.get('yuklenen') or 0)} dosya",
               ck.renk["mavi"])
        elif yd == "hata":
            ck.yazi(x + 16, yy + 166, (d.get("hata") or "bilinmeyen hata")[:40], 10,
                    ck.renk["kirmizi"])
        else:
            ysure = int(d.get("sure_sn") or 0)
            ys(166, "son süre", f"{ysure // 60} dk {ysure % 60} sn")


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
        _satir(ck, x + 16, yy, et, dg, None, 11, 84)
        yy += 20
    if makine and yy <= y + h - 14:
        ck.yazi(x + 16, yy, makine[:40], 10, ck.renk["cok_soluk"])


CIZIM = {
    "cpu": cpu, "bellek": bellek, "sicaklik": sicaklik, "pil": pil,
    "cekirdek": cekirdek, "gecmis": gecmis, "gpu": gpu, "disk_ag": disk_ag,
    "surecler": surecler, "yedek": yedek, "sistem": sistem,
}
