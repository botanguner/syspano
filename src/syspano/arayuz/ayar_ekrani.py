"""Pano üzerinden ayar ekranı — dokunmatik dostu.

Ayarlar panonun kendi tuvalinde, kartların yerine çizilir; ayrı bir pencere
açılmaz. Tüm denetimler parmakla kullanılacak biçimde tasarlandı:

* Her denetim en az `DOKUNMA` (46 tasarım birimi) yüksekliğinde — küçük bir
  panelde bile rahat basılır.
* Yalnızca **dokunma** ve **sürükleme** kullanılır; üzerine gelme, sağ tık,
  ince kaydırıcı tutamacı yok. Kaydırıcı, çubuğun herhangi bir yerine dokunup
  sürüklenerek ayarlanır; ayrıca −/+ düğmeleri vardır.
* Yerleşim saf bir fonksiyondur (`yerlesim`), böylece her ekran boyutunda test
  edilebilir. Dar ekranda etiket üstte, geniş ekranda solda durur.

Bu modül Tk kullanmaz; yalnızca `cekim.Cekim` üzerinden çizer.
"""

KENAR = 12            # ekran kenarı boşluğu
BOSLUK = 10           # öğeler arası boşluk
DOKUNMA = 46          # en küçük dokunma hedefi (tasarım birimi)
ETIKET_H = 22         # dar düzende etiket satırı
ICERIK_G_MAX = 780    # içerik en fazla bu genişlikte (geniş ekranda ortalanır)
UST = 46              # üst şerit yüksekliği


# ─── seçenek düğmeleri (sarma) ───────────────────────────────────────────────
def _secenek_konumlari(w, secenekler, bosluk=6, min_gen=74):
    """Seçenekleri satırlara sarar: [(deger, etiket, gen, satir, x_ic]"""
    konumlar, cx, satir = [], 0.0, 0
    for deger, etiket in secenekler:
        gen = min(max(min_gen, len(str(etiket)) * 8 + 26), w)
        if cx + gen > w and cx > 0:
            satir += 1
            cx = 0.0
        konumlar.append((deger, etiket, gen, satir, cx))
        cx += gen + bosluk
    return konumlar


def _secenek_yuksekligi(w, secenekler, bosluk=6, min_gen=74):
    konumlar = _secenek_konumlari(w, secenekler, bosluk, min_gen)
    if not konumlar:
        return 0.0
    satir_sayisi = max(k[3] for k in konumlar) + 1
    return satir_sayisi * DOKUNMA + (satir_sayisi - 1) * bosluk


def _secenek_kutulari(x, y, w, secenekler, bosluk=6, min_gen=74):
    kutular = []
    for deger, etiket, gen, satir, x_ic in _secenek_konumlari(w, secenekler, bosluk, min_gen):
        kutular.append((deger, etiket, (x + x_ic, y + satir * (DOKUNMA + bosluk), gen, DOKUNMA)))
    return kutular


# ─── denetim yerleşimleri ────────────────────────────────────────────────────
def _anahtar_yerlesim(x, y, w, h):
    """Sağda açma/kapama anahtarı."""
    kg, ky = 58.0, min(32.0, h - 6)
    return (x + w - kg, y + (h - ky) / 2, kg, ky)


def _kaydirici_yerlesim(x, y, w, h, oto_var=True):
    """[-] [çubuk] [+] ve (genişse) 'Oto' düğmesi.

    Çubuğun görünen yüksekliği 8 birimdir ama **dokunma alanı** parmakla
    basılabilmesi için `DOKUNMA` yüksekliğindedir (`dokunma`).
    """
    d = min(DOKUNMA, h)
    eksi = (x, y + (h - d) / 2, d, d)
    arti_x = x + w - d
    oto = None
    if oto_var and w >= 300:
        oto = (arti_x - 6 - 54, y + (h - 34) / 2, 54, 34)
        arti_x = oto[0] - 6 - d
    arti = (arti_x, y + (h - d) / 2, d, d)
    bas = eksi[0] + d + 8
    gen = max(20.0, arti[0] - 8 - bas)
    cubuk = (bas, y + h / 2 - 4, gen, 8)
    dokunma = (bas, y + (h - DOKUNMA) / 2, gen, min(DOKUNMA, h))
    return {"eksi": eksi, "arti": arti, "cubuk": cubuk,
            "dokunma": dokunma, "oto": oto}


# ─── ana yerleşim ────────────────────────────────────────────────────────────
def yerlesim(tasarim_g, tasarim_y, ayarlar, cikislar=(), durum=None):
    """Ayar ekranının kutularını hesaplar (saf fonksiyon).

    Dönen: {"kutular": [...], "icerik_y": float, "icerik_g": float, "dar": bool}
    """
    durum = durum or {}
    icerik_g = max(240.0, min(tasarim_g - 2 * KENAR, ICERIK_G_MAX))
    x0 = (tasarim_g - icerik_g) / 2
    dar = icerik_g < 560

    kutular = []
    y = UST + BOSLUK
    # geniş düzende denetimler sağda; dar düzende etiket altta tam genişlik
    kx_denetim = x0 if dar else x0 + icerik_g * 0.44
    kg_denetim = icerik_g if dar else icerik_g * 0.56

    def baslik(metin):
        nonlocal y
        kutular.append({"tur": "baslik", "id": None, "etiket": metin,
                        "x": x0, "y": y, "w": icerik_g, "h": 20})
        y += 20 + 8

    def aciklama(metin):
        nonlocal y
        kutular.append({"tur": "aciklama", "id": None, "etiket": metin,
                        "x": x0, "y": y, "w": icerik_g, "h": 16})
        y += 16 + 8

    def durum_satiri(metin, renk="soluk"):
        """Renkli durum satırı (ör. güncelleme durumu: güncel/yeni sürüm/hata)."""
        nonlocal y
        kh = 20
        kutular.append({"tur": "durum", "id": None, "etiket": metin,
                        "renk": renk, "x": x0, "y": y, "w": icerik_g, "h": kh})
        y += kh + 8

    def etiket_noktasi(kh):
        """Etiketin çizileceği yer: dar düzende üstte, geniş düzende ortada."""
        return (x0 + 2, y + 11) if dar else (x0 + 4, y + kh / 2)

    def _satir_ekle(kutu, kh, etiketli=True):
        nonlocal y
        kutu["h"] = kh
        kutular.append(kutu)
        y += ((ETIKET_H if (dar and etiketli) else 0) + kh) + BOSLUK

    def secenek_satiri(kid, etiket, secenekler, deger):
        kh = _secenek_yuksekligi(kg_denetim, secenekler)
        ky = y + ETIKET_H if dar else y
        kutu = {"tur": "secenek", "id": kid, "etiket": etiket,
                "x": x0, "y": y, "w": icerik_g,
                "etiket_nokta": etiket_noktasi(kh), "deger": deger,
                "secenekler": _secenek_kutulari(kx_denetim, ky, kg_denetim, secenekler),
                "denetim": (kx_denetim, ky, kg_denetim, kh)}
        _satir_ekle(kutu, kh)

    def anahtar_satiri(kid, etiket, deger, notu=""):
        kh = DOKUNMA
        ky = y + ETIKET_H if dar else y
        kutu = {"tur": "anahtar", "id": kid, "etiket": etiket,
                "x": x0, "y": y, "w": icerik_g,
                "etiket_nokta": etiket_noktasi(kh), "deger": bool(deger),
                "anahtar": _anahtar_yerlesim(kx_denetim, ky, kg_denetim, kh),
                "notu": notu, "denetim": (kx_denetim, ky, kg_denetim, kh)}
        _satir_ekle(kutu, kh)

    def kaydirici_satiri(kid, etiket, deger, alt, ust, adim, oto_id=None, oto_var=False):
        kh = DOKUNMA
        ky = y + ETIKET_H if dar else y
        parcalar = _kaydirici_yerlesim(kx_denetim, ky, kg_denetim, kh, oto_var)
        kutu = {"tur": "kaydirici", "id": kid, "etiket": etiket,
                "x": x0, "y": y, "w": icerik_g,
                "etiket_nokta": etiket_noktasi(kh), "deger": float(deger or 0.0),
                "alt": alt, "ust": ust, "adim": adim, "parcalar": parcalar,
                "oto_id": oto_id, "denetim": (kx_denetim, ky, kg_denetim, kh)}
        _satir_ekle(kutu, kh)

    def dugme_satiri(kid, etiket):
        kh = DOKUNMA
        ky = y
        kutu = {"tur": "dugme", "id": kid, "etiket": etiket,
                "x": x0, "y": y, "w": icerik_g, "etiket_nokta": None,
                "dugme": (kx_denetim, ky, kg_denetim, kh)}
        _satir_ekle(kutu, kh, etiketli=False)

    # ── görünüm ──
    baslik("GÖRÜNÜM")
    kaydirici_satiri("olcek", "Ölçek", float(ayarlar.get("olcek") or 0.0),
                     0.7, 3.0, 0.05, oto_id="olcek_oto", oto_var=True)
    _istenen = durum.get("olcek_istenen") or 0.0
    _etkin = durum.get("olcek_etkin") or 0.0
    if _istenen and _etkin and abs(float(_istenen) - float(_etkin)) > 0.01:
        aciklama(f"Bu ekranda en fazla {_etkin:.2f} uygulanabiliyor "
                 f"(istenen {_istenen:.2f})")
    secenek_satiri("tema", "Tema",
                   [("koyu", "Koyu"), ("acik", "Açık")],
                   ayarlar.get("tema", "koyu"))
    secenek_satiri("buyutec", "Büyüteç",
                   [("auto", "Otomatik"), ("acik", "Açık"), ("kapali", "Kapalı")],
                   _buyutec_degeri(ayarlar))
    secenek_satiri("aralik", "Güncelleme",
                   [("500", "0,5 sn"), ("1000", "1 sn"), ("2000", "2 sn"), ("5000", "5 sn")],
                   str(ayarlar.get("guncelleme_ms", 1000)))
    secenek_satiri("ekran", "Hedef ekran", _ekran_secenekleri(cikislar),
                   str(ayarlar.get("ekran", "auto")))

    # ── davranış ──
    baslik("DAVRANIŞ")
    anahtar_satiri("terminal", "Gömülü terminal", ayarlar.get("terminal", True))
    anahtar_satiri("tepsi", "Tepsi simgesi", ayarlar.get("tepsi", True),
                   notu="yeniden başlatma gerekir")
    anahtar_satiri("otomatik_kart", "Kartları otomatik gizle",
                   ayarlar.get("otomatik_kart", True))

    # ── kartlar ──
    baslik("KARTLAR")
    aciklama("Gösterilecek kartlar — yer darsa önemsizler gizlenir")
    kartlar = durum.get("kart_bilgi") or {}
    adlar = list(kartlar)
    n_kolon = 2 if icerik_g >= 420 else 1
    if adlar:
        kolon_g = (icerik_g - BOSLUK * (n_kolon - 1)) / n_kolon
        for i, ad in enumerate(adlar):
            r, c = divmod(i, n_kolon)
            kx = x0 + c * (kolon_g + BOSLUK)
            ky = y + r * (DOKUNMA + 6)
            kutular.append({"tur": "kart_anahtar", "id": "kart:" + ad,
                            "etiket": kartlar[ad], "x": kx, "y": ky,
                            "w": kolon_g, "h": DOKUNMA, "deger": ad in set(
                                ayarlar.get("kartlar") or []),
                            "anahtar": (kx + kolon_g - 54, ky + (DOKUNMA - 30) / 2, 54, 30)})
        satir_sayisi = -(-len(adlar) // n_kolon)
        y += satir_sayisi * (DOKUNMA + 6) + BOSLUK

    # ── başlatma yöntemi ──
    baslatma = durum.get("baslatma") or {}
    if baslatma.get("metin"):
        baslik("BAŞLATMA")
        durum_satiri(baslatma["metin"], baslatma.get("renk") or "soluk")
        etiketler = {"servis_kur": "Servisi kur (systemd)",
                     "servis_baslat": "Servisi başlat",
                     "servis_durdur": "Servisi durdur",
                     "servis_yeniden": "Servisi yeniden başlat"}
        for eylem in baslatma.get("eylemler") or []:
            if eylem in etiketler:
                dugme_satiri(eylem, etiketler[eylem])

    # ── sürüm / güncelleme ──
    baslik("SÜRÜM")
    aciklama(durum.get("surum_metni") or "")
    guncelleme_durum = durum.get("guncelleme") or {}
    if guncelleme_durum.get("metin"):
        durum_satiri(guncelleme_durum["metin"],
                     guncelleme_durum.get("renk") or "soluk")
    dugme_satiri("guncelle_denetle", "Güncellemeyi denetle")
    dugme_satiri("guncelle_uygula", "Güncelle (arka planda)")
    dugme_satiri("yeniden_baslat", "Panoyu yeniden başlat")
    dugme_satiri("sifirla", "Ayarları varsayılana döndür")
    dugme_satiri("kapat", "Panoya dön")

    return {"kutular": kutular, "icerik_y": y + BOSLUK, "icerik_g": icerik_g, "dar": dar}


# ─── değer yardımcıları ──────────────────────────────────────────────────────
def _buyutec_degeri(ayarlar):
    b = ayarlar.get("buyutec", "auto")
    if b is True:
        return "acik"
    if b is False:
        return "kapali"
    return "auto"


def _ekran_secenekleri(cikislar):
    secenekler = [("auto", "Otomatik"), ("ana", "Ana")]
    for c in cikislar or ():
        secenekler.append((c.ad, c.ad))
    secenekler.append(("tumu", "Tümü"))
    return secenekler


# ─── çizim ───────────────────────────────────────────────────────────────────
def ciz(cek, plan, durum=None):
    """Ayar ekranını çizer. `plan`, `yerlesim()` çıktısıdır."""
    R = cek.renk
    for k in plan["kutular"]:
        tur = k["tur"]
        if tur == "baslik":
            cek.yazi(k["x"], k["y"] + 10, k["etiket"], 12, R["mavi"], True)
            cek.dik(k["x"], k["y"] + 21, k["x"] + k["w"], k["y"] + 21.8, R["kenar"])
        elif tur == "aciklama":
            cek.yazi(k["x"], k["y"] + 8, k["etiket"], 10, R["cok_soluk"])
        elif tur == "durum":
            cek.yazi(k["x"], k["y"] + k["h"] / 2, k["etiket"], 11.5,
                     R.get(k.get("renk") or "soluk", R["soluk"]), True)
        elif tur == "secenek":
            _etiket(cek, k)
            for deger, etiket, (bx, by, bw, bh) in k["secenekler"]:
                secili = str(deger) == str(k["deger"])
                cek.dik(bx, by, bx + bw, by + bh, R["mavi"] if secili else R["dugme"], R["kenar"])
                cek.yazi(bx + bw / 2, by + bh / 2 + 1, etiket, 11,
                         R["arka"] if secili else R["yazi"], secili, "center")
        elif tur in ("anahtar", "kart_anahtar"):
            if tur == "kart_anahtar":
                # kart anahtarında etiket kutunun içinde, solda durur
                x, y, w, h = k["x"], k["y"], k["w"], k["h"]
                cek.yazi(x + 10, y + h / 2,
                         _kirp(cek, k["etiket"], 11, w - 54 - 18),
                         11, R["yazi"])
            else:
                _etiket(cek, k)
            _anahtar_ciz(cek, k["anahtar"], k["deger"])
        elif tur == "kaydirici":
            _kaydirici_ciz(cek, k)
        elif tur == "dugme":
            dx, dy, dw, dh = k["dugme"]
            cek.dik(dx, dy, dx + dw, dy + dh, R["dugme"], R["kenar"])
            cek.yazi(dx + dw / 2, dy + dh / 2 + 1, k["etiket"], 11.5, R["yazi"], True, "center")


def _kaydirici_ciz(cek, k):
    R = cek.renk
    deger = k["deger"] or 0.0
    metin = f"{deger:.2f}" if k["deger"] else "oto"
    _etiket(cek, k, sag=metin)
    p = k["parcalar"]
    for ad, etiket in (("eksi", "−"), ("arti", "+")):
        dx, dy, dw, dh = p[ad]
        cek.dik(dx, dy, dx + dw, dy + dh, R["dugme"], R["kenar"])
        cek.yazi(dx + dw / 2, dy + dh / 2 + 1, etiket, 20, R["yazi"], True, "center")
    if p.get("oto"):
        dx, dy, dw, dh = p["oto"]
        cek.dik(dx, dy, dx + dw, dy + dh, R["dugme"], R["kenar"])
        cek.yazi(dx + dw / 2, dy + dh / 2 + 1, "Oto", 11, R["yazi"], True, "center")
    bx, by, bw, bh = p["cubuk"]
    cek.dik(bx, by, bx + bw, by + bh, R["kenar"])
    oran = (deger - k["alt"]) / (k["ust"] - k["alt"]) if k["ust"] > k["alt"] else 0
    oran = max(0.0, min(1.0, oran))
    dolu = bw * oran
    if dolu > 0:
        cek.dik(bx, by, bx + dolu, by + bh, R["mavi"])
    # tutamak (parmakla sürüklenebilir geniş bir daire)
    tx = bx + dolu
    cek.oval(tx - 10, by + bh / 2 - 10, tx + 10, by + bh / 2 + 10,
             R["mavi"], R["arka"], 2)


def _etiket(cek, k, sag=None):
    if not k.get("etiket_nokta"):
        return
    x, y = k["etiket_nokta"]
    cek.yazi(x, y, k["etiket"], 11.5, cek.renk["yazi"], True)
    if k.get("notu"):
        g = cek._yazi_tipi(11.5, True)[0].measure(k["etiket"]) / cek.S + 10
        cek.yazi(x + g, y, k["notu"], 10, cek.renk["cok_soluk"])
    if sag:
        cek.yazi(k["x"] + k["w"] - 6, y, sag, 11.5, cek.renk["mavi"], True, "e")


def _kirp(cek, metin, boyut, azami_gen):
    """Metni azami genişliğe sığdırır (sonda '…'). Tasarım birimi cinsinden."""
    s = str(metin)
    if azami_gen <= 8:
        return ""
    try:
        f = cek._yazi_tipi(boyut, False)[0]
        olcek = cek.S * cek._donusum[2]
        if f.measure(s) / olcek <= azami_gen:
            return s
        while s and f.measure(s + "…") / olcek > azami_gen:
            s = s[:-1]
        return (s + "…") if s else ""
    except Exception:
        return s[:12]


def _anahtar_ciz(cek, rect, acik):
    R = cek.renk
    x, y, w, h = rect
    r = h / 2
    arka = R["yesil"] if acik else R["kenar"]
    cek.dik(x + r, y, x + w - r, y + h, arka)          # gövde
    cek.oval(x, y, x + h, y + h, arka)                 # sol kapak
    cek.oval(x + w - h, y, x + w, y + h, arka)         # sağ kapak
    top = (x + w - h + 3) if acik else (x + 3)
    cek.oval(top, y + 3, top + h - 6, y + h - 3, R["kart"], R["kenar"], 1)


# ─── isabet denetimi ─────────────────────────────────────────────────────────
def icinde(rect, x, y):
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def isabet(plan, x, y):
    """(id, eylem, deger) döndürür; hiçbir şeye denk gelmezse None.

    eylem: sec | anahtar | kaydirici_basla | kaydirici_adim | dugme
    """
    for k in plan["kutular"]:
        tur = k["tur"]
        if tur == "secenek":
            for deger, _et, rect in k["secenekler"]:
                if icinde(rect, x, y):
                    return (k["id"], "sec", deger)
        elif tur in ("anahtar", "kart_anahtar"):
            if icinde(k["anahtar"], x, y) or icinde((k["x"], k["y"], k["w"], k["h"]), x, y):
                return (k["id"], "anahtar", not k["deger"])
        elif tur == "kaydirici":
            p = k["parcalar"]
            if p.get("oto") and icinde(p["oto"], x, y):
                return (k["oto_id"] or k["id"], "dugme", None)
            if icinde(p["eksi"], x, y):
                return (k["id"], "kaydirici_adim", -1)
            if icinde(p["arti"], x, y):
                return (k["id"], "kaydirici_adim", +1)
            if icinde(p["dokunma"], x, y):
                return (k["id"], "kaydirici_basla", _kaydirici_deger(k, x))
        elif tur == "dugme":
            if icinde(k["dugme"], x, y):
                return (k["id"], "dugme", None)
    return None


def _kaydirici_deger(k, x):
    """Çubuktaki konuma karşılık gelen değer (adıma yuvarlanır)."""
    bx, _, bw, _ = k["parcalar"]["cubuk"]
    oran = max(0.0, min(1.0, (x - bx) / bw if bw else 0))
    ham = k["alt"] + oran * (k["ust"] - k["alt"])
    adim = k["adim"]
    return round(round(ham / adim) * adim, 4) if adim else ham
