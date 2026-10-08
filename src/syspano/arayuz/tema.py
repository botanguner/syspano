"""Renkler ve yazı tipi seçimi."""

KOYU = {
    "ad": "koyu",
    "arka": "#0f1116",
    "kart": "#181c24",
    "kenar": "#242a36",
    "yazi": "#e6e9ef",
    "soluk": "#8b93a7",
    "cok_soluk": "#5f6779",
    "mavi": "#3daee9",
    "yesil": "#27ae60",
    "sari": "#f0c040",
    "kirmizi": "#da4453",
    "mor": "#9b59b6",
    "turkuaz": "#56b6c2",
    "ustluk": "#12151b",
    "dugme": "#1d2330",
    "icerik": "#12151c",
}

ACIK = {
    "ad": "acik",
    "arka": "#eef1f6",
    "kart": "#ffffff",
    "kenar": "#d3dae5",
    "yazi": "#1c2430",
    "soluk": "#5c6470",
    "cok_soluk": "#8a929e",
    "mavi": "#1976c9",
    "yesil": "#1e8e4e",
    "sari": "#b8860b",
    "kirmizi": "#c0392b",
    "mor": "#7d3c98",
    "turkuaz": "#1b7d8a",
    "ustluk": "#e3e8f0",
    "dugme": "#dbe2ec",
    "icerik": "#f4f6fa",
}


def tema_sec(ad):
    return ACIK if str(ad).lower() in ("acik", "açık", "light", "aydinlik") else KOYU


# Yaygın tek aralıklı yazı tipleri; ilk bulunan kullanılır.
YAZI_ADAYLARI = (
    "DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "Ubuntu Mono",
    "JetBrains Mono", "Fira Mono", "Source Code Pro", "Cascadia Mono",
    "FreeMono", "Courier New", "TkFixedFont",
)

_yazi_ailesi = None


def yazi_ailesi(kok=None):
    """Sistemde bulunan ilk uygun tek aralıklı yazı tipi (önbelleğe alınır)."""
    global _yazi_ailesi
    if _yazi_ailesi:
        return _yazi_ailesi
    try:
        from tkinter import font as tkfont
        var_olan = set(tkfont.families(kok))
        for ad in YAZI_ADAYLARI:
            if ad in var_olan:
                _yazi_ailesi = ad
                return ad
    except Exception:
        pass
    _yazi_ailesi = "TkFixedFont"
    return _yazi_ailesi
