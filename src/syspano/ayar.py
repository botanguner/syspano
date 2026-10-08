"""Yapılandırma dosyası: ~/.config/syspano/config.json

Komut satırı seçenekleri her zaman dosyadaki değerleri geçersiz kılar.
"""

import copy
import json
import os

from . import ortam

VARSAYILAN = {
    # hedef ekran: "auto" | "ana" | "tumu" | çıkış adı (örn. "HDMI-A-1") | sıra no
    "ekran": "auto",
    # mod: "ekran" (hedef ekranı kapla) | "pencere" (belirli boyut) | "tam-ekran"
    "mod": "ekran",
    "pencere": [1280, 720],
    # ölçek: None → DPI'dan hesaplanır; sayı → sabit katsayı (0.7 – 3.0)
    "olcek": None,
    "tema": "koyu",
    "kartlar": ["cpu", "bellek", "sicaklik", "pil", "cekirdek", "gecmis",
                "gpu", "disk_ag", "surecler", "yedek", "sistem"],
    # true | false | "auto": auto → yalnızca faresinin olduğu, yeterince geniş
    # ekranlarda açılır (dokunmatik panellerde kendiliğinden kapalı).
    "buyutec": "auto",
    "fare_ile_kaydirma": True,
    "terminal": True,
    "terminal_yazi": None,      # None → ölçeğe göre; px cinsinden sayı → sabit
    "tepsi": True,
    "guncelleme_ms": 1000,
    "uygulama_basligi": "SysPano",
    "saydam_olmayan": True,
}


def yol():
    return os.path.join(ortam.yapilandirma_dizini(), "config.json")


def oku():
    d = copy.deepcopy(VARSAYILAN)
    try:
        with open(yol()) as f:
            d.update(json.load(f))
    except Exception:
        pass
    return d


def dosya_oku():
    """Yalnızca dosyadaki değerler (varsayılanlarla birleştirilmez)."""
    try:
        with open(yol()) as f:
            return json.load(f)
    except Exception:
        return {}


def yaz(sozluk):
    ortam.emin_ol(ortam.yapilandirma_dizini())
    gecici = yol() + ".tmp"
    with open(gecici, "w") as f:
        json.dump(sozluk, f, indent=2, ensure_ascii=False)
    os.replace(gecici, yol())
    return yol()


def guncelle(degisim=None, sil=()):
    """Var olan dosyayı koruyup yalnızca istenen anahtarları değiştirir.

    Varsayılanları dosyaya yazmadığı için, `"auto"` gibi akıllı bir varsayılan
    ilk çalıştırmada sabit bir değere dönüşmez.
    """
    mevcut = dosya_oku()
    if degisim:
        mevcut.update(degisim)
    for anahtar in sil:
        mevcut.pop(anahtar, None)
    return yaz(mevcut)
