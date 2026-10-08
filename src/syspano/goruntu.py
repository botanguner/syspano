"""Ekran görüntüsü (`--cek`): panonun/ekranın PNG kaydı.

Wayland oturumunda **grim**, X11'de **scrot** (yoksa ImageMagick `import`)
kullanılır. Böylece Raspberry Pi'nin labwc oturumunda da, masaüstünde de
çalışır. Ek bağımlılık yoktur; yalnızca sistemde bulunan araç çağrılır.

Kullanım:

    syspano --cek                 # ~/Pictures/syspano-<tarih>.png (varsa)
    syspano --cek /tmp/pano.png   # belirli dosya

Pano içinden de tetiklenebilir: tepsi iletişim dosyasına `cek` yazmak
(ör. bir donanım düğmesine bağlamak için) ekran görüntüsü alır ve nereye
kaydedildiğini bildirim olarak gösterir.
"""

import os
import shutil
import subprocess
import time

ON_EK = "syspano"


def arac_sec(ortam=None, bul=shutil.which):
    """Kullanılabilir aracı seçer: `(ad, komut)` ya da `None`.

    Öncelik: Wayland → `grim`; X11 → `scrot`. ImageMagick `import` **bilerek
    dışarıda**: X11'de pencere seçimi için etkileşimli bekleyip otomasyonu
    kilitleyebiliyor (denedik: `import -window root dosya.png` hata verirken
    seçeneksiz çağrı kullanıcı tıklaması bekliyor).
    """
    ortam = os.environ if ortam is None else ortam
    if ortam.get("WAYLAND_DISPLAY") and bul("grim"):
        return ("grim", ["grim"])
    if ortam.get("DISPLAY") and bul("scrot"):
        return ("scrot", ["scrot", "-o"])
    return None


def varsayilan_yol(simdi=None):
    """`~/Pictures` varsa oraya, yoksa ev dizinine zaman damgalı dosya adı."""
    damga = time.strftime("%Y%m%d-%H%M%S", time.localtime(simdi or time.time()))
    ad = f"{ON_EK}-{damga}.png"
    resimler = os.path.expanduser("~/Pictures")
    return os.path.join(resimler if os.path.isdir(resimler) else os.path.expanduser("~"),
                        ad)


def cek(yol=None, ortam=None, calistir=None, bul=shutil.which):
    """Ekran görüntüsünü kaydeder: `(basarili, mesaj)`.

    `calistir` ve `bul` test için değiştirilebilir (varsayılan: `subprocess.run`
    ve `shutil.which`).
    """
    secim = arac_sec(ortam, bul)
    if not secim:
        return (False, "ekran görüntüsü aracı yok — Wayland'de `grim`, "
                       "X11'de `scrot` kurun")
    ad, komut = secim
    hedef = os.path.expanduser(yol) if yol else varsayilan_yol()
    klasor = os.path.dirname(hedef)
    if klasor:
        try:
            os.makedirs(klasor, exist_ok=True)
        except Exception as hata:
            return (False, f"klasör oluşturulamadı: {hata}")
    calistir = calistir or (lambda k: subprocess.run(k, capture_output=True,
                                                     text=True, timeout=15))
    try:
        sonuc = calistir([*komut, hedef])
    except Exception as hata:
        return (False, f"{ad} çalıştırılamadı: {hata}")
    if getattr(sonuc, "returncode", 1) != 0 or not os.path.exists(hedef):
        satirlar = [s for s in (getattr(sonuc, "stderr", "") or "").splitlines() if s.strip()]
        return (False, f"{ad} başarısız: {satirlar[0][:120] if satirlar else 'çıktı yok'}")
    return (True, f"{hedef} · {ad}")
