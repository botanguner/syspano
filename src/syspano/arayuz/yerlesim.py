"""Uyarlanabilir yerleşim: hangi kart, kaç sütun, hangi yükseklik.

Bu modül **saf**tır (Tk kullanmaz), böylece her çözünürlük ve en-boy oranı
için ayrı ayrı test edilebilir. Arayüz yalnızca buradan dönen dikdörtgenleri
çizer.

Tasarım uzayı gerçek pikselden bağımsızdır: pencere `tasarim_g` × `tasarim_y`
tasarım birimi büyüklüğündedir ve çizim sırasında ölçekle çarpılır. Kartların
yüksekliği sabit değil, **ağırlıklı**dır: satırlar mevcut yüksekliği oranlarına
göre paylaşır, böylece hem küçük bir dokunmatik panelde hem 4K monitörde
dengeli görünür.
"""

# Her kartın yerleşim özellikleri:
#   sutun  : kaç sütun yer kaplar (1 veya 2)
#   yuk    : satır yüksekliği ağırlığı (boyutsuz)
#   oncelik: yer yetmediğinde düşürme sırası (küçük = önce düşer)
KART_BILGI = {
    "cpu":      {"baslik": "CPU",                 "sutun": 1, "min": 120, "dogal": 150, "oncelik": 100},
    "bellek":   {"baslik": "BELLEK",              "sutun": 1, "min": 110, "dogal": 140, "oncelik": 99},
    "sicaklik": {"baslik": "SICAKLIK / FAN",      "sutun": 1, "min": 100, "dogal": 130, "oncelik": 95},
    "pisaglik": {"baslik": "Pİ SAĞLIĞI",          "sutun": 1, "min": 95, "dogal": 120, "oncelik": 82},
    "pil":      {"baslik": "PİL",                 "sutun": 1, "min": 78, "dogal": 96, "oncelik": 84},
    "cekirdek": {"baslik": "ÇEKİRDEK KULLANIMI",  "sutun": 2, "min": 85, "dogal": 98, "oncelik": 80},
    "gecmis":   {"baslik": "GEÇMİŞ (son 4 dk)",   "sutun": 2, "min": 95, "dogal": 125, "oncelik": 70},
    "gpu":      {"baslik": "GPU",                 "sutun": 1, "min": 110, "dogal": 150, "oncelik": 66},
    "disk_ag":  {"baslik": "DİSK / AĞ",           "sutun": 1, "min": 115, "dogal": 165, "oncelik": 76},
    "surecler": {"baslik": "SÜREÇLER",            "sutun": 1, "min": 110, "dogal": 175, "oncelik": 55},
    "servisler": {"baslik": "SERVİSLER",          "sutun": 1, "min": 110, "dogal": 175, "oncelik": 85},
    "loglar":   {"baslik": "GÜNLÜKLER",           "sutun": 1, "min": 105, "dogal": 160, "oncelik": 58},
    "yedek":    {"baslik": "YEDEK",               "sutun": 1, "min": 100, "dogal": 135, "oncelik": 40},
    "sistem":   {"baslik": "SİSTEM",              "sutun": 1, "min": 105, "dogal": 140, "oncelik": 30},
}

_ONCELIK_SIRASI = sorted(KART_BILGI, key=lambda k: KART_BILGI[k]["oncelik"])

UST = 46           # üst şerit yüksekliği (tasarım birimi)
BOSLUK = 14        # kartlar arası boşluk
KENAR = 14         # ekran kenarı boşluğu
MIN_SUTUN_G = 250  # bir sütunun en az genişliği (tasarım birimi)
MIN_SATIR_Y = 78   # bir satırın en az yüksekliği (tasarım birimi)
ALT_BILGI = 20     # alt bilgi şeridi


def sutun_sayisi(tasarim_g):
    """Genişliğe göre sütun sayısı (1–4)."""
    kullanilir = tasarim_g - 2 * KENAR + BOSLUK
    n = int(kullanilir // (MIN_SUTUN_G + BOSLUK))
    return max(1, min(4, n))


def _kart_span(kart, n):
    """Kartın kapladığı sütun sayısı. Dar düzenlerde (n≤2) her kart tek sütun
    alır; böylece küçük ekranlarda sütun boşa gitmez."""
    temel = KART_BILGI[kart]["sutun"]
    if n <= 2:
        return 1
    return min(temel, n)


def _satirlara_yerlestir(kartlar, n):
    """Kartları satırlara dağıtır: her satır [(kart, sütun_kaplama), ...]."""
    satirlar, mevcut, dolu = [], [], 0
    for kart in kartlar:
        span = _kart_span(kart, n)
        if mevcut and dolu + span > n:
            satirlar.append(mevcut)
            mevcut, dolu = [], 0
        mevcut.append((kart, span))
        dolu += span
    if mevcut:
        satirlar.append(mevcut)
    return satirlar


def _satiri_yay(satir, n):
    """Satırda boş sütun kalırsa kartlara eşit dağıt (kartlar satırı doldursun)."""
    dolu = sum(s for _, s in satir)
    bos = n - dolu
    if bos > 0 and satir:
        ek, kalan = divmod(bos, len(satir))
        return [(k, s + ek + (1 if i < kalan else 0))
                for i, (k, s) in enumerate(satir)]
    return satir


def _dogal(satir):
    """Satırın doğal yüksekliği: içindeki kartların içerik yüksekliğinin en büyüğü."""
    return max(KART_BILGI[k].get("dogal", 120) for k, _ in satir)


def _asgari(satir):
    """Satırın alt sınırı: kartların kendi alt sınırlarının en büyüğü."""
    return max(KART_BILGI[k].get("min", MIN_SATIR_Y) for k, _ in satir)


def _olcu(satirlar, kullanilabilir):
    """Satır yükseklikleri: **içeriğe göre** doğal yükseklik, sığmazsa ölçeklenir.

    Eskiden tek bir birim katsayısı kullanılıyordu; bu yüzden benzer ağırlıklı
    kartlar (ör. pil ile CPU) aynı yüksekliği alıyordu. Artık her kartın
    içeriğine göre bir doğal yüksekliği ve bir alt sınırı var: pil kısa kalır,
    süreç/servis listeleri uzar. Yer darsa doğal yükseklikler orantılı küçülür
    ama alt sınırların altına inmez; alt sınırlar bile sığmıyorsa `sigar=False`
    döner (çağıran önemsiz kartları gizler ya da panoyu kaydırılabilir yapar).
    """
    # satır aralıkları (BOSLUK) da yer kaplar; hesaba katılmazsa içerik taşar
    kullanilabilir = max(MIN_SATIR_Y, kullanilabilir - len(satirlar) * BOSLUK)
    dogallar = [_dogal(s) for s in satirlar]
    asgariler = [_asgari(s) for s in satirlar]
    toplam_d, toplam_a = sum(dogallar), sum(asgariler)
    if toplam_a > kullanilabilir and len(satirlar) > 1:
        return dogallar, False
    # büyük ekranda boşluk kalmasın: doğal yükseklik %60'a kadar büyür
    olcek = min(1.6, kullanilabilir / toplam_d) if toplam_d else 1.0
    yukler = [max(a, d * olcek) for d, a in zip(dogallar, asgariler)]
    return yukler, sum(yukler) <= kullanilabilir + 0.5


def planla(tasarim_g, tasarim_y, aktif_kartlar=None, otomatik=True):
    """Kartların tasarım uzayındaki dikdörtgenlerini hesaplar.

    Dönen sözlük:
        kartlar     : {ad: (x, y, w, h)}
        sutun       : sütun sayısı
        icerik_y    : içeriğin toplam yüksekliği
        gizli       : yer darlığından gizlenen kartlar
        kaydirilir  : içerik ekrana sığmıyor, dikey kaydırma gerekli
    """
    istenen = [k for k in (aktif_kartlar or list(KART_BILGI)) if k in KART_BILGI]
    if not istenen:
        istenen = ["cpu", "bellek"]

    n = sutun_sayisi(tasarim_g)
    # üst şeritten sonra bir boşluk, en altta ALT_BILGI kadar pay kalır;
    # bu boşluklar düşülmezse içerik her zaman bir boşluk kadar taşar
    kullanilabilir = max(80.0, tasarim_y - UST - ALT_BILGI - BOSLUK)

    aktif = list(istenen)
    satirlar = _satirlara_yerlestir(aktif, n)
    yukler, sigar = _olcu(satirlar, kullanilabilir)

    # yer yetmiyorsa en önemsiz kartlardan başlayarak düşür (birikimli)
    if otomatik:
        dusen = []
        for ad in _ONCELIK_SIRASI:
            if sigar or len(aktif) <= 2:
                break
            if ad not in aktif:
                continue
            dusen.append(ad)
            aday = [k for k in aktif if k not in dusen]
            s2 = _satirlara_yerlestir(aday, n)
            yukler2, sigar2 = _olcu(s2, kullanilabilir)
            aktif, satirlar, yukler, sigar = aday, s2, yukler2, sigar2

    kaydirilir = False
    if not sigar:
        kaydirilir = True
        # sabit (kaydırılabilir) yükseklik: en küçük satır MIN_SATIR_Y olsun
        yukler = [_dogal(s) for s in satirlar]      # içeriğe göre doğal yükseklik

    kartlar = {}
    y = UST + BOSLUK
    for satir, syuk in zip(satirlar, yukler):
        satir = _satiri_yay(satir, n)
        dolu = sum(s for _, s in satir)
        birim = (tasarim_g - 2 * KENAR - BOSLUK * (dolu - 1)) / dolu if dolu else tasarim_g
        x = KENAR
        for kart, span in satir:
            gen = birim * span + BOSLUK * (span - 1)
            kartlar[kart] = (x, y, gen, syuk)
            x += gen + BOSLUK
        y += syuk + BOSLUK

    return {
        "kartlar": kartlar,
        "sutun": n,
        "icerik_y": y - BOSLUK + ALT_BILGI,
        "gizli": [k for k in istenen if k not in kartlar],
        "kaydirilir": kaydirilir,
    }
