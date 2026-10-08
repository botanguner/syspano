"""Sıcaklık ve fan: Intel (coretemp), AMD (k10temp/zenpower), ARM (cpu_thermal),
NVMe, kablosuz ve diğer sensörler. Hangisi varsa onu gösterir.

**Performans (iki katmanlı):**

1. Sensörler (yollarıyla birlikte) **bir kez** bulunur ve
   `d.sicaklik_haritasi` içinde saklanır. Önceden her saniye hwmon dizinleri
   listeleniyor ve 20'den fazla var olmayan `temp*_input` dosyası açılmaya
   çalışılıyordu.
2. Sensör başına **okuma maliyeti ölçülür**. Ucuz sensörler (`coretemp` ~0,04 ms)
   her ölçümde okunur; pahalı olanlar seyreltilir. Örneğin NVMe sıcaklığı her
   okumada diske SMART komutu gönderir ve ~9 ms sürer — bu tek sensör, tüm
   toplayıcının yarısını yiyordu. Artık 10 saniyede bir okunur; NVMe sıcaklığı
   zaten 10 saniyede anlamlı değişmez.

| Okuma maliyeti | Aralık |
|---|---|
| < 0,3 ms | her ölçüm (1 sn) |
| 0,3 – 2 ms | 5 saniyede bir |
| ≥ 2 ms | 10 saniyede bir |

Harita 60 saniyede bir (ya da bir sensör kaybolduğunda) yeniden kurulur.
"""

import os
import time

from . import ortak

# CPU paket sıcaklığı için tercih sırası (yonga adına göre)
_CPU_YONGA = ("coretemp", "k10temp", "zenpower", "k8temp", "cpu_thermal",
              "soc_thermal", "cpu-thermal", "soc-thermal", "acpitz", "acpitz-acpi")
# /sys/class/thermal tip adları (yonga adı bulunamazsa)
_THERMAL_CPU = ("x86_pkg_temp", "cpu-thermal", "cpu_thermal", "soc-thermal",
                "soc_thermal", "acpitz", "rk_thermal", "bcm2835_thermal")
# Fan sunan yongalar (tercih sırası)
_FAN_YONGA = ("asus", "thinkpad", "nct6775", "nct6776", "nct6779", "nct6791",
              "it87", "dell_smm", "applesmc", "f71882fg", "w83627ehf", "emc2103")
# Göstermeye değer diğer sıcaklıklar: (hwmon adı, ekranda görünecek ad)
_EKSTRA = (("nvme", "nvme"), ("pch_cannonlake", "pch"), ("pch_skylake", "pch"),
           ("pch_lewisburg", "pch"), ("pch_icelake", "pch"), ("iwlwifi", "wifi"),
           ("iwlwifi_1", "wifi"), ("iwlwifi_2", "wifi"), ("ath10k_hwmon", "wifi"),
           ("amdgpu", "gpu"), ("nouveau", "gpu"), ("acpitz", "acpi"))

HARITA_OMRU = 60.0        # saniye; sensörler yeniden taranır
YAVAS_ESIK = 0.3          # ms; bu süreden yavaş okunan sensör seyreltilir
COK_YAVAS_ESIK = 2.0      # ms
YAVAS_ARALIK = 5.0        # saniye
COK_YAVAS_ARALIK = 10.0   # saniye
KAPALI = -1.0             # okunamayan sensör


# ─── kayıtlar ────────────────────────────────────────────────────────────────
def _okuma_maliyeti(yol):
    """Bir sensörün okuma süresi (ms) — harita kurulurken bir kez ölçülür."""
    try:
        bas = time.perf_counter()
        ortak.oku_sayi(yol, KAPALI)
        return (time.perf_counter() - bas) * 1000.0
    except Exception:
        return KAPALI


def _kayit(yol, etiket=None, aralik=None):
    maliyet = None
    if aralik is None:
        maliyet = _okuma_maliyeti(yol)
        aralik = (COK_YAVAS_ARALIK if maliyet >= COK_YAVAS_ESIK
                  else YAVAS_ARALIK if maliyet >= YAVAS_ESIK else 0.0)
    return {"yol": yol, "etiket": etiket, "aralik": aralik,
            "deger": None, "zaman": 0.0, "maliyet": maliyet}


def _deger(kayit, simdi):
    """Sensör değeri; seyreltilen sensörlerde son okunan değer döner."""
    if kayit["aralik"] <= 0:
        return ortak.oku_sayi(kayit["yol"], KAPALI)
    if kayit["deger"] is None or simdi - kayit["zaman"] >= kayit["aralik"]:
        kayit["deger"] = ortak.oku_sayi(kayit["yol"], KAPALI)
        kayit["zaman"] = simdi
    return kayit["deger"]


def _temp_sira(anahtar):
    try:
        return int(anahtar[4:])
    except Exception:
        return 999


def _thermal_bolge_sec():
    """CPU sıcaklığını veren /sys/class/thermal bölgesinin adı."""
    if not os.path.isdir("/sys/class/thermal"):
        return None
    for z in sorted(os.listdir("/sys/class/thermal")):
        if not z.startswith("thermal_zone"):
            continue
        ad = ortak.oku(f"/sys/class/thermal/{z}/type") or z
        if ad in _THERMAL_CPU or "cpu" in ad or "pkg" in ad or "soc" in ad:
            return ad
    bolgeler = ortak.thermal_bolgeleri()
    return next(iter(bolgeler), None)


# ─── harita ──────────────────────────────────────────────────────────────────
def _harita_kur(hw):
    """Hangi dosyaların hangi sıklıkta okunacağını belirler (bir kez)."""
    h = {"paket": None, "cekirdekler": [], "kaynak": "yok",
         "fanlar": [], "ekstra": [], "zaman": ortak.zaman()}

    icin = ortak.hwmon_bul(*_CPU_YONGA, hwmon=hw)
    if icin:
        girdiler = ortak.hwmon_girdileri(icin, "temp")        # tek listdir
        anahtarlar = sorted(girdiler, key=_temp_sira)
        if anahtarlar:
            # coretemp'te ilk girdi paket, sonrakiler çekirdekler
            h["paket"] = _kayit(f"{icin}/{anahtarlar[0]}_input")
            # çekirdekler paketle aynı yongada: aynı aralığı paylaşsınlar
            h["cekirdekler"] = [
                _kayit(f"{icin}/{a}_input", aralik=h["paket"]["aralik"])
                for a in anahtarlar[1:]]
            h["kaynak"] = ortak.oku(f"{icin}/name", "") or "hwmon"

    if h["paket"] is None:
        ad = _thermal_bolge_sec()
        if ad:
            h["paket"] = _kayit(f"/sys/class/thermal/{ad}/temp")
            h["kaynak"] = ad

    # fanlar: tercih sırasına göre adaylar (ilk sıfırdan büyük olan kullanılır)
    fanlar = []
    for ad in _FAN_YONGA:
        yol = hw.get(ad)
        if yol:
            for anahtar in sorted(ortak.hwmon_girdileri(yol, "fan")):
                fanlar.append(f"{yol}/{anahtar}_input")
    for ad, yol in hw.items():
        if ad in _FAN_YONGA:
            continue
        for anahtar in sorted(ortak.hwmon_girdileri(yol, "fan")):
            fanlar.append(f"{yol}/{anahtar}_input")
    h["fanlar"] = [_kayit(y) for y in fanlar]

    # ekstra sıcaklıklar (etiket → kayıt); aynı etiket bir kez
    gorulen = set()
    for yonga, etiket in _EKSTRA:
        if etiket in gorulen:
            continue
        yol = hw.get(yonga)
        if yol:
            dosya = f"{yol}/temp1_input"
            if os.path.exists(dosya):
                h["ekstra"].append(_kayit(dosya, etiket=etiket))
                gorulen.add(etiket)
    return h


# ─── ölçüm ───────────────────────────────────────────────────────────────────
def oku(d, ayar):
    if d.hwmon is None:
        d.hwmon = ortak.hwmonlar()
    simdi = ortak.zaman()
    h = d.sicaklik_haritasi
    if h is None or simdi - h["zaman"] > HARITA_OMRU:
        h = d.sicaklik_haritasi = _harita_kur(d.hwmon)

    paket = 0.0
    if h["paket"] is not None:
        ham = _deger(h["paket"], simdi)
        paket = (ham / 1000.0) if ham > 0 else 0.0
        # Yalnızca dosya gerçekten kaybolduysa haritayı yenile (kart çıkarıldı,
        # modül boşaltıldı…). 0 okumak yenileme sebebi değil: bazı bölgeler
        # geçici olarak 0 döndürebilir ve her saniye yeniden tarama pahalıdır.
        if ham <= 0 and not os.path.exists(h["paket"]["yol"]) and simdi - h["zaman"] > 5.0:
            h = d.sicaklik_haritasi = _harita_kur(d.hwmon)
            if h["paket"] is not None:
                ham = _deger(h["paket"], simdi)
                paket = (ham / 1000.0) if ham > 0 else 0.0

    cekler = [_deger(k, simdi) / 1000.0 for k in h["cekirdekler"]]
    cekler = [c for c in cekler if 1 < c < 150]
    cek_maks = max(cekler) if cekler else paket

    fan = 0.0
    for kayit in h["fanlar"]:
        deger = _deger(kayit, simdi)
        if deger > 0:
            fan = deger
            break

    ekstra = []
    for kayit in h["ekstra"]:
        deger = _deger(kayit, simdi) / 1000.0
        if 1 < deger < 150:
            ekstra.append((kayit["etiket"], deger))

    return {
        "paket": paket,
        "cekirdek_maks": cek_maks,
        "kaynak": h["kaynak"] or "yok",
        "fan": fan,
        "ekstra": ekstra,
        "sensor_var": bool(h["paket"]),
    }
