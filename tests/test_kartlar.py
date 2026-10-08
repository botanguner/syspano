"""Kart çizim testleri: her kart, her boyutta kendi dikdörtgeninde kalmalı.

Tk bir görüntü gerektirir; görüntü yoksa test atlanır. Kartlar gizli bir
pencerede çizilir ve çizilen her öğenin sınırlayıcı kutusu (bbox) kart
dikdörtgeninin içinde mi diye bakılır. Bu, küçük ekranlarda taşan yazı/çubuk
hatalarını yakalar.
"""

import sys

from syspano.arayuz import kartlar, tema
from syspano.arayuz.cekim import Cekim

# ── gerçekçi örnek veri (tüm kartlar için) ───────────────────────────────────
ORNEK = {
    "cpu": {"yuzde": 42.0, "cekirdek": [10, 55, 3, 88, 21, 7, 99, 44],
            "ghz": 2.13, "maks_ghz": 4.6, "yuk": ["1.2", "1.0", "0.9"],
            "cekirdek_sayisi": 8, "cekirdek_ghz": [2100] * 8, "governor": "powersave"},
    "bellek": {"toplam": 15.4, "kullanilan": 8.2, "yuzde": 53.0, "swap_t": 8.0,
               "swap_k": 1.0, "takas_tur": "zram"},
    "sicaklik": {"paket": 62.0, "cekirdek_maks": 65.0, "kaynak": "coretemp",
                 "fan": 2400.0, "ekstra": [("nvme", 40.0), ("pch", 45.0), ("wifi", 44.0)],
                 "sensor_var": True},
    "pil": {"yuzde": 78.0, "durum": "Discharging", "ac": False, "guc": 9.4,
            "saglik": 88.0, "kalan_dk": 210.0, "enerji": 30.0, "tam": 40.0},
    "gpu": {"kartlar": [{"ad": "card1", "model": "Örnek GPU", "kullanim": 33.0,
                         "mhz": 700.0, "maks_mhz": 1150.0, "sicaklik": 51.0}],
            "nvidia": {"yuzde": 5.0, "vram": 120.0, "vram_toplam": 2048.0, "sicaklik": 55.0,
                       "pstate": "P0", "model": "NVIDIA GeForce GTX 1050", "durum": "kullanılıyor",
                       "tepe": 12.0, "son_kullanim": 5.0, "surecler": [("python3", 220.0)]}},
    "disk": {"okuma": 12.4, "yazma": 3.1, "dolu": 62.0, "bos_gb": 105.0,
             "toplam_gb": 155.0, "model": "Örnek SSD 512 GB"},
    "ag": {"arayuz": "wlan0", "inen": 120.0, "giden": 22.0, "ip": "192.0.2.10",
           "tur": "wifi"},
    "surecler": {"liste": [(45.0, "tarayici", 1_200_000_000), (20.0, "pencere-yoneticisi", 300_000_000),
                           (12.0, "python3", 50_000_000)], "toplam": 356},
    "servisler": {"yok": False, "toplam": 4, "aralik": 30.0, "birimler": [
        {"ad": "apache2.service", "etiket": "Apache", "durum": "active", "alt": "running",
         "baslama": 1_700_000_000.0, "bellek": 12_000_000, "pid": 812},
        {"ad": "mariadb.service", "etiket": "MariaDB", "durum": "active", "alt": "running",
         "baslama": 1_700_000_000.0, "bellek": 240_000_000, "pid": 654},
        {"ad": "nginx.service", "etiket": "nginx", "durum": "failed", "alt": "failed",
         "baslama": None, "bellek": None, "pid": 0},
        {"ad": "redis-server.service", "etiket": "Redis", "durum": "inactive", "alt": "dead",
         "baslama": None, "bellek": None, "pid": 0}]},
    "loglar": {"yok": False, "toplam": 5, "kaynaklar": [
        {"grup": "php", "etiket": "PHP-FPM", "ad": "php8.2-fpm.log",
         "yol": "/var/log/php8.2-fpm.log", "boyut": 240_000, "son": 1_700_000_000.0,
         "okunabilir": True},
        {"grup": "uygulama", "etiket": "Laravel", "ad": "laravel.log",
         "yol": "/var/www/ornek/storage/logs/laravel.log", "boyut": 1_450_000,
         "son": 1_700_000_000.0, "okunabilir": True},
        {"grup": "apache", "etiket": "Apache", "ad": "error.log",
         "yol": "/var/log/apache2/error.log", "boyut": 88_000, "son": 1_700_000_000.0,
         "okunabilir": True},
        {"grup": "veritabani", "etiket": "PostgreSQL", "ad": "postgresql-16-main.log",
         "yol": "/var/log/postgresql/postgresql-16-main.log", "boyut": 420_000,
         "son": 1_700_000_000.0, "okunabilir": True},
        {"grup": "veritabani", "etiket": "MySQL", "ad": "error.log",
         "yol": "/var/log/mysql/error.log", "boyut": 64_000, "son": 1_700_000_000.0,
         "okunabilir": False}]},
    "guc": {"tur": "RAPL", "pl1": 15, "pl2": 25, "governor": "powersave"},
    "yedek": {"durum": "basarili", "baslangic": 1000, "bitis": 2000, "sonuc": 0,
              "yuklenen": 39, "toplam_dosya": 2235, "toplam_bayt": 1_435_350_008,
              "hata": "", "sonraki": "Thu 2026-10-08 20:08:54 +03", "yok": False},
    "sistem": {"ad": "ornek-pc", "dagitim": "Debian GNU/Linux 12", "cekirdek": "6.6.0-generic",
               "mimari": "x86_64", "uptime_sn": 123456, "oturum": "wayland",
               "masaustu": "kde", "makine": "Örnek Dizüstü",
               "islemci": "8 × 2.4 GHz"},
}

GECMIS = {k: [float((i * 7) % 100) for i in range(60)]
          for k in ("cpu", "bellek", "sicaklik", "pil", "gpu", "dgpu", "ag_in", "ag_out")}

BOYUTLAR = [(360, 84), (360, 120), (360, 175), (360, 260), (360, 360),
            (240, 84), (240, 150), (600, 200), (600, 400), (200, 90)]


def _kontrol(kok):
    import tkinter as tk
    c = tk.Canvas(kok, width=800, height=800)
    cekim = Cekim(c, 1.0, tema.tema_sec("koyu"), tema.yazi_ailesi(kok))
    hatalar = []
    for kid, fonk in kartlar.CIZIM.items():
        for (w, h) in BOYUTLAR:
            c.delete("all")
            x, y = 10, 10
            fonk(cekim, x, y, w, h, ORNEK, GECMIS)
            for oge in c.find_all():
                if "mercek" in c.gettags(oge):
                    continue
                bx0, by0, bx1, by1 = c.bbox(oge)
                if bx1 > x + w + 2 or by1 > y + h + 2 or bx0 < x - 2 or by0 < y - 2:
                    hatalar.append((kid, w, h, c.type(oge), (bx0, by0, bx1, by1)))
    return hatalar


def test_liste_kartlarinda_daha_yazisi_cakismaz():
    """"+N daha" satırı son satırın (ya da kart kenarının) üstüne binmemeli.

    Raspberry Pi panelinde görüldü: kısa bir SERVİSLER kartında "+7 servis
    daha" yazısı "Bluetooth" satırının üzerine biniyordu.
    """
    import tkinter as tk
    try:
        kok = tk.Tk()
    except Exception as hata:
        print(f"atlandı (görüntü yok: {hata})")
        return
    kok.withdraw()
    try:
        c = tk.Canvas(kok, width=900, height=900)
        cekim = Cekim(c, 1.0, tema.tema_sec("koyu"), tema.yazi_ailesi(kok))
        hatalar = []
        for kid in ("servisler", "loglar"):
            for (w, h) in BOYUTLAR:
                c.delete("all")
                kartlar.CIZIM[kid](cekim, 10, 10, w, h, ORNEK, GECMIS)
                metinler = [(c.bbox(o), c.itemcget(o, "text"))
                            for o in c.find_all()
                            if c.type(o) == "text"]
                daha = [(b, t) for b, t in metinler if "daha" in t]
                if not daha:
                    continue
                for (db, dt) in daha:
                    for (ob, ot) in metinler:
                        if ot is dt or not ot.strip():
                            continue
                        # dikdörtgenler kesişiyor mu?
                        if (db[0] < ob[2] and ob[0] < db[2]
                                and db[1] < ob[3] and ob[1] < db[3]):
                            hatalar.append((kid, w, h, dt, ot))
        assert not hatalar, "liste kartlarında çakışma:\n" + "\n".join(
            f"  {k} {w}x{h}: {a!r} ↔ {b!r}" for k, w, h, a, b in hatalar[:20])
    finally:
        kok.destroy()


def test_kartlar_tasmaz():
    import tkinter as tk
    try:
        kok = tk.Tk()
    except Exception as hata:
        print(f"atlandı (görüntü yok: {hata})")
        return
    kok.withdraw()
    try:
        hatalar = _kontrol(kok)
    finally:
        kok.destroy()
    assert not hatalar, "taşan kart öğeleri:\n" + "\n".join(
        f"  {k} {w}x{h}: {t} {b}" for k, w, h, t, b in hatalar[:40])


if __name__ == "__main__":
    import traceback
    gecen, kalan = 0, 0
    for ad, fonk in sorted(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            try:
                fonk()
                print(f"  ✓ {ad}")
                gecen += 1
            except AssertionError as e:
                print(f"  ✗ {ad}\n{e}")
                kalan += 1
            except Exception:
                traceback.print_exc()
                kalan += 1
    print(f"\n{gecen} geçti, {kalan} kaldı")
    sys.exit(1 if kalan else 0)
