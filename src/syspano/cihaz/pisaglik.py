"""Raspberry Pi sağlığı: kısılma (throttle) ve düşük voltaj durumu.

`vcgencmd get_throttled` bir bit maskesi döndürür:

| Bit | Anlamı |
|---|---|
| 0 | **şu an** düşük voltaj |
| 1 | şu an frekans kısıtlı |
| 2 | şu an kısılıyor (throttled) |
| 3 | şu an yazılımsal sıcaklık sınırı |
| 16–19 | aynı durumların **önyüklemeden beri** görülüp görülmediği |

Yetersiz adaptör/kablo ya da yıpranmış bir SD kart kendini burada gösterir; bu
yüzden Pi'de ilk bakılacak göstergelerden biridir. `vcgencmd` yoksa (Pi değil)
kart gizlenir.

**Maliyet:** `vcgencmd` süreç başlatır (~5–10 ms); üç çağrı (`get_throttled`,
`measure_volts core`, `measure_clock arm`) `PI_ARALIK` boyunca önbelleğe alınır.
"""

import subprocess

from . import ortak
from .gpu import ortam_komut

PI_ARALIK = 5.0        # saniye; vcgencmd süreç başlatır
BITLER = (
    (0, "undervoltage", "düşük voltaj"),
    (1, "freq_capped", "frekans kısıtlı"),
    (2, "throttled", "kısılıyor"),
    (3, "soft_temp_limit", "sıcaklık sınırı"),
)


def maske_ayristir(metin):
    """'throttled=0x50005' → 327685 (okunamazsa None)."""
    try:
        ham = str(metin).split("=")[-1].strip()
        return int(ham, 16) if ham.lower().startswith("0x") else int(ham)
    except Exception:
        return None


def ayristir(maske):
    """Bit maskesini okunur sözlüğe çevirir (saf fonksiyon, test edilebilir)."""
    if maske is None:
        return {"yok": True}
    simdi, gecmis = [], []
    for bit, ad, etiket in BITLER:
        if maske & (1 << bit):
            simdi.append((ad, etiket))
        if maske & (1 << (bit + 16)):
            gecmis.append((ad, etiket))
    return {"ham": f"0x{maske:x}", "mask": maske, "simdi": simdi, "gecmis": gecmis,
            "simdi_var": bool(simdi), "gecmis_var": bool(gecmis),
            "normal": not simdi and not gecmis}


def _vcgencmd(*args):
    try:
        c = subprocess.run(["vcgencmd", *args], capture_output=True, text=True,
                           timeout=4)
        return (c.stdout or "").strip()
    except Exception:
        return ""


def gerilim(metin):
    """'volt=0.8700V' → 0.87"""
    return ortak.sayi(str(metin).replace("V", "").split("=")[-1])


def ghz(metin):
    """'frequency(48)=1500345728' → 1.5 (GHz)"""
    hz = ortak.sayi(str(metin).split("=")[-1])
    return hz / 1e9 if hz else None


def oku(d, ayar):
    if not ortam_komut("vcgencmd"):
        return {"yok": True}
    simdi = ortak.zaman()
    if d.pi_sonuc is not None and simdi - d.pi_zaman < PI_ARALIK:
        return d.pi_sonuc

    ham = _vcgencmd("get_throttled")
    if not ham:
        return {"yok": True}
    sonuc = ayristir(maske_ayristir(ham))
    if sonuc.get("yok"):
        return {"yok": True}
    sonuc["gerilim"] = gerilim(_vcgencmd("measure_volts", "core"))
    sonuc["ghz"] = ghz(_vcgencmd("measure_clock", "arm"))
    d.pi_sonuc, d.pi_zaman = sonuc, simdi
    return sonuc
