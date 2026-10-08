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
                "gpu", "disk_ag", "servisler", "surecler", "yedek", "sistem"],
    # true | false | "auto": auto → yalnızca faresinin olduğu, yeterince geniş
    # ekranlarda açılır (dokunmatik panellerde kendiliğinden kapalı).
    "buyutec": "auto",
    "terminal": True,
    "terminal_yazi": None,      # None → ölçeğe göre; px cinsinden sayı → sabit
    "tepsi": True,
    "guncelleme_ms": 1000,
    # açılışta ve günde bir kez yeni sürüm denetimi (ağa çıkar; false → hiç çıkmaz)
    "guncelleme_denetimi": True,
    # yer yetmezse düşük öncelikli kartları gizle (ayar ekranındaki anahtar)
    "otomatik_kart": True,
    # GDrive yedeği: YEDEK kartının okuduğu durum dosyası ve systemd timer adı
    "yedek_durum_yolu": "~/.local/state/gdrive-yedek/durum.json",
    "yedek_zamanlayici": "yedek.timer",
    # systemd servisleri: ek olarak izlenecek birimler (ör. ["apache2", "mysql"])
    "servisler": [],
    # birim → log dosyası (ör. {"apache2": "/var/log/apache2/error.log"})
    "servis_log_dosyalari": {},
    "servis_aralik": 30,        # saniye; servis durumu bu aralıkta okunur (düşürülebilir)
    "servis_log_satir": 200,    # günlük görüntüleyicide gösterilecek satır
    "uygulama_basligi": "SysPano",
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
