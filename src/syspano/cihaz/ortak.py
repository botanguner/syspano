"""Cihaz toplayıcıları: /proc ve /sys'den veri okuyan, donanımdan bağımsız modüller.

Her modül `oku(d, ayar)` imzasını taşır; `d` paylaşılan durumu (önceki örnekler,
bulunan sensör yolları) tutan Toplayici nesnesidir. Hiçbir modül zorunlu değildir:
veri yoksa boş sözlük ya da `{"yok": True}` döner ve arayüz o kartı gizler.
"""

import os
import time


# ─── dosya okuma ─────────────────────────────────────────────────────────────
def oku(yol, varsayilan=None):
    try:
        with open(yol) as f:
            return f.read().strip()
    except Exception:
        return varsayilan


def oku_sayi(yol, varsayilan=0.0):
    try:
        return float(oku(yol).split()[0])
    except Exception:
        return varsayilan


def sayi(metin):
    """Metni sayıya çevirir; '[N/A]' ya da boş değerde None döner."""
    try:
        return float(str(metin).strip().split()[0].replace("%", "").replace(",", ""))
    except Exception:
        return None


def sure_metni(sn):
    """Saniyeyi 'az önce', '12 dk önce', '3 saat önce' biçimine çevirir."""
    sn = max(0, int(sn))
    if sn < 90:
        return "az önce"
    dk = sn // 60
    if dk < 60:
        return f"{dk} dk önce"
    sa = dk // 60
    if sa < 24:
        return f"{sa} saat önce"
    return f"{sa // 24} gün önce"


def kuyruk(yol, satir=200, azami_bayt=512 * 1024):
    """Dosyanın son `satir` satırını verimli biçimde okur (sondan geriye).

    Dosyanın tamamı okunmaz: yalnızca gereken kadar bayt, en fazla
    `azami_bayt`. Tek satırlık dev bir dosya (ya da SD karttaki büyük bir
    günlük) bu yüzden belleği ve diski yormaz.
    """
    try:
        with open(yol, "rb") as f:
            f.seek(0, 2)
            boyut = f.tell()
            parca, adim = b"", 8192
            while boyut > 0 and parca.count(b"\n") <= satir:
                adim = min(adim, boyut, azami_bayt - len(parca))
                if adim <= 0:
                    break
                boyut -= adim
                f.seek(boyut)
                parca = f.read(adim) + parca
        satirlar = parca.decode("utf-8", "replace").splitlines()
        return "\n".join(satirlar[-satir:])
    except Exception as hata:
        return f"(okunamadı: {hata})"


def boyut_metni(bayt):
    """Baytı okunur biçime çevirir: '1.33 GiB'."""
    b = float(bayt or 0)
    for birim in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(b) < 1024:
            return f"{b:.0f} {birim}" if birim == "B" else f"{b:.2f} {birim}"
        b /= 1024
    return f"{b:.2f} PiB"


# ─── hwmon ───────────────────────────────────────────────────────────────────
def hwmonlar():
    """{ad: yol} — /sys/class/hwmon altındaki sensör yongaları."""
    sonuc = {}
    try:
        for h in sorted(os.listdir("/sys/class/hwmon")):
            yol = f"/sys/class/hwmon/{h}"
            ad = oku(f"{yol}/name")
            if ad:
                sonuc.setdefault(ad, yol)
    except Exception:
        pass
    return sonuc


def hwmon_bul(*adlar, hwmon=None):
    """Verilen adlardan ilk bulunanın yolunu döndürür."""
    h = hwmon if hwmon is not None else hwmonlar()
    for ad in adlar:
        if ad in h:
            return h[ad]
    return None


def hwmon_girdileri(yol, tur):
    """Bir hwmon yongasındaki girdiler: {'temp1': 'Package id 0', 'fan1': 'cpu_fan'}."""
    sonuc = {}
    if not yol:
        return sonuc
    try:
        for dosya in os.listdir(yol):
            if dosya.startswith(tur) and dosya.endswith("_input"):
                anahtar = dosya[:-len("_input")]
                etiket = oku(f"{yol}/{anahtar}_label") or anahtar
                sonuc[anahtar] = etiket
    except Exception:
        pass
    return sonuc


# ─── thermal_zone ────────────────────────────────────────────────────────────
def thermal_bolgeleri():
    """{ad: sıcaklık_C} — /sys/class/thermal/thermal_zone*."""
    sonuc = {}
    try:
        for z in sorted(os.listdir("/sys/class/thermal")):
            if not z.startswith("thermal_zone"):
                continue
            yol = f"/sys/class/thermal/{z}"
            ad = oku(f"{yol}/type") or z
            t = oku_sayi(f"{yol}/temp", -1)
            if t > 0:
                sonuc.setdefault(ad, t / 1000.0)
    except Exception:
        pass
    return sonuc


# ─── ortak: geçmiş örnek farkı ───────────────────────────────────────────────
def zaman():
    return time.monotonic()
