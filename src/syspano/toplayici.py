"""Ölçüm toplayıcı: tüm cihaz modüllerini tek bir sözlükte birleştirir.

Arka planda ayrı bir iş parçacığında çalışır; arayüz `al()` ile son veriyi
kilit altında okur. Toplayıcının kendisi donanıma özel bilgi tutmaz; yalnızca
modüllerin ihtiyaç duyduğu "önceki örnek" durumunu taşır.
"""

import threading
import time

from .cihaz import TOPLAYICILAR


class Toplayici:
    def __init__(self, ayar):
        self.ayar = ayar
        self.veri = {}
        self.kilit = threading.Lock()
        self.aralik = max(0.25, ayar.get("guncelleme_ms", 1000) / 1000.0)

        # ── modüllerin paylaştığı durum ──
        self.onceki_cpu = None
        self.hwmon = None
        self.pil_dugum = None
        self.ac_dugum = None
        self.pil_arandi = False
        self.rc6_onceki = {}
        self.gpu_kart_onbellek = None
        self.gpu_kart_zaman = 0.0
        self.vcgencmd_sonuc = None
        self.vcgencmd_zaman = 0.0
        self.nvidia = None
        self.nvidia_zaman = 0.0
        self.nvidia_tepe = 0.0
        self.nvidia_tepe_zaman = 0.0
        self.nvidia_son_kullanim = None
        self.nvidia_surecler = []
        self.nvidia_surec_zaman = 0.0
        self.kok_disk = None
        self.kok_disk_arandi = False
        self.disk_onceki = None
        self.ag_onceki = None
        self.ag_arayuz = None
        self.ag_arandi = False
        self.surec_onceki = None
        self.surec_sonuc = {}
        self.surec_son = 0.0
        self.sicaklik_haritasi = None
        # systemd servisleri
        self.servis_birimler = None
        self.servis_kesif = 0.0
        self.servis_son = 0.0
        self.servis_sonuc = {}
        # geliştirici günlükleri (dosya kaynakları)
        self.log_kaynaklar = None
        self.log_kesif = 0.0
        self.log_son = 0.0
        self.log_sonuc = {}
        self.yedek_zaman = 0.0
        self.yedek_sonraki = ""
        self.sistem_arandi = False
        self.sistem_bilgi = {}

    def topla(self):
        veri = {}
        for ad, mod in TOPLAYICILAR:
            try:
                veri[ad] = mod.oku(self, self.ayar)
            except Exception as hata:
                veri[ad] = {"hata": str(hata)}
        with self.kilit:
            self.veri = veri

    def dongu(self):
        while True:
            bas = time.monotonic()
            self.topla()
            kalan = self.aralik - (time.monotonic() - bas)
            time.sleep(max(0.05, kalan))

    def al(self):
        with self.kilit:
            return dict(self.veri)
