"""Uydurma veri üretici — `syspano --demo`.

Arayüzü göstermek, **ekran görüntüsü almak** ve donanımı olmadan denemek için
kullanılır. Hiçbir sistem dosyası okunmaz; çıktıda kişisel bilgi bulunmaz:
makine adı, IP, disk modeli, işlemci modeli ve süreç adlarının hepsi uydurmadır.

Değerler zamanla yumuşak biçimde dalgalanır, böylece grafikler boş görünmez.
`DemoToplayici`, gerçek `Toplayici` ile aynı arayüzü sunar (`al`, `dongu`,
`aralik`), bu yüzden pano tarafında hiçbir değişiklik gerekmez.
"""

import math
import time

# Örnek sistem bilgisi: hiçbiri gerçek bir cihaza işaret etmez.
ORNEK_SISTEM = {
    "ad": "demo-pc",
    "dagitim": "Debian GNU/Linux 12",
    "cekirdek": "6.6.0-generic",
    "mimari": "x86_64",
    "oturum": "wayland",
    "masaustu": "kde",
    "makine": "Örnek Dizüstü",
    "islemci": "8 × 2.4 GHz",
}

# Genel açık kaynak program adları — kişisel bir kurulumu yansıtmaz.
ORNEK_SURECLER = ("firefox", "code", "python3", "gnome-shell", "terminal",
                  "thunderbird", "docker", "node")


class DemoToplayici:
    """Gerçek toplayıcının yerine geçen sahte veri kaynağı."""

    def __init__(self, ayar):
        self.aralik = max(0.25, ayar.get("guncelleme_ms", 1000) / 1000.0)
        self.t0 = time.monotonic()
        self.baslangic = time.time()

    # ── Toplayici arayüzü ──
    def dongu(self):
        while True:
            time.sleep(self.aralik)

    def al(self):
        return self._uret()

    # ── üretim ──
    def _uret(self):
        t = time.monotonic() - self.t0

        def dalga(periyot, genlik, taban, faz=0.0):
            return taban + genlik * math.sin(t / periyot + faz)

        # CPU: çekirdekler birbirinden hafif farklı fazlarda dalgalansın
        cek_sayi = 8
        cekirdek = [max(2.0, min(99.0, dalga(7 + i * 0.7, 20 + i, 26 + i * 3, i)))
                    for i in range(cek_sayi)]
        cpu_yuzde = sum(cekirdek) / cek_sayi
        ghz = dalga(23, 0.5, 2.1)

        # Bellek: yavaş bir testere gibi
        bel_yuzde = max(20.0, min(92.0, dalga(61, 14, 54)))
        bel_toplam = 16.0

        sicaklik = dalga(37, 5, 54)
        fan = int(max(0.0, dalga(31, 900, 2400)))

        pil_yuzde = max(5.0, min(100.0, 78 - (t / 90.0) % 40))

        gpu_kul = max(0.0, min(100.0, dalga(19, 16, 14, 1.3)))
        disk_oku = max(0.0, dalga(9, 18, 22, 0.7))
        disk_yaz = max(0.0, dalga(11, 6, 5, 2.1))
        ag_in = max(0.0, dalga(6, 240, 260, 0.4))
        ag_out = max(0.0, dalga(7, 60, 70, 1.9))

        surecler = []
        for i, ad in enumerate(ORNEK_SURECLER):
            yuzde = max(0.4, dalga(13 + i, 9, 6 + (len(ORNEK_SURECLER) - i) * 3.4, i * 0.9))
            surecler.append((round(yuzde, 1), ad, int(90e6 + i * 22e6)))
        surecler.sort(reverse=True)

        return {
            "sistem": dict(ORNEK_SISTEM, uptime_sn=int(4 * 3600 + t)),
            "cpu": {
                "yuzde": cpu_yuzde,
                "cekirdek": cekirdek,
                "ghz": ghz,
                "maks_ghz": 4.6,
                "yuk": [f"{dalga(53, 0.7, 1.2):.2f}", f"{dalga(47, 0.5, 0.9):.2f}",
                        f"{dalga(41, 0.4, 0.8):.2f}"],
                "cekirdek_sayisi": cek_sayi,
                "cekirdek_ghz": [ghz * 1000] * cek_sayi,
                "governor": "powersave",
            },
            "bellek": {
                "toplam": bel_toplam,
                "kullanilan": bel_toplam * bel_yuzde / 100.0,
                "yuzde": bel_yuzde,
                "swap_t": 8.0,
                "swap_k": 1.4,
                "takas_tur": "zram",
            },
            "sicaklik": {
                "paket": sicaklik,
                "cekirdek_maks": sicaklik + 3,
                "kaynak": "demo",
                "fan": fan,
                "ekstra": [("nvme", 40.0), ("pch", 45.0), ("wifi", 42.0)],
                "sensor_var": True,
            },
            "pil": {
                "yuzde": pil_yuzde, "durum": "Discharging", "ac": False,
                "guc": 9.4, "saglik": 88.0, "kalan_dk": pil_yuzde * 2.7,
                "enerji": 30.0, "tam": 40.0, "dugum": "BAT0",
            },
            "gpu": {
                "kartlar": [{
                    "ad": "card0", "surucu": "i915", "uretim": "Intel",
                    "model": "Örnek GPU", "kullanim": gpu_kul,
                    "mhz": 300 + 500 * gpu_kul / 100.0, "maks_mhz": 1150.0,
                    "sicaklik": sicaklik - 4,
                }],
                "nvidia": None,
            },
            "disk": {
                "okuma": disk_oku, "yazma": disk_yaz, "dolu": 62.0,
                "bos_gb": 105.0, "toplam_gb": 512.0, "aygit": "nvme0n1",
                "model": "Örnek SSD 512 GB",
            },
            "ag": {
                "arayuz": "wlan0", "inen": ag_in, "giden": ag_out,
                "ip": "192.0.2.10",          # RFC 5737: belgeleme için ayrılmış
                "tur": "wifi", "hiz": 866,
            },
            "surecler": {"liste": surecler, "toplam": 214, "olcum_sn": 3.0},
            "guc": {"tur": "RAPL", "pl1": 15, "pl2": 25, "governor": "powersave"},
            "yedek": {
                "yok": False, "durum": "basarili",
                "baslangic": self.baslangic - 3600, "bitis": self.baslangic - 3300,
                "sure_sn": 300, "yuklenen": 42, "toplam_dosya": 1874,
                "toplam_bayt": 1_286_553_600, "hata": "", "sonraki": "",
            },
        }
