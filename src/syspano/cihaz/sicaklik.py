"""Sıcaklık ve fan: Intel (coretemp), AMD (k10temp/zenpower), ARM (cpu_thermal),
NVMe, kablosuz ve diğer sensörler. Hangisi varsa onu gösterir.
"""

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


def _cpu_paket(hw):
    """(paket_C, cekirdek_maks_C, kaynak_adi) döndürür."""
    icin = ortak.hwmon_bul(*_CPU_YONGA, hwmon=hw)
    if icin:
        paket = ortak.oku_sayi(f"{icin}/temp1_input", 0) / 1000.0
        # coretemp: temp3.. sırayla gerçek çekirdekler
        cekler = [ortak.oku_sayi(f"{icin}/temp{i}_input", 0) / 1000.0
                  for i in range(2, 24)]
        cekler = [c for c in cekler if 1 < c < 150]
        return paket, (max(cekler) if cekler else paket), ortak.oku(f"{icin}/name", "")
    # /sys/class/thermal
    bolge = ortak.thermal_bolgeleri()
    for ad, deger in bolge.items():
        if ad in _THERMAL_CPU or "cpu" in ad or "pkg" in ad or "soc" in ad:
            return deger, deger, ad
    if bolge:
        ad, deger = next(iter(bolge.items()))
        return deger, deger, ad
    return 0.0, 0.0, ""


def _fan(hw):
    for ad in _FAN_YONGA:
        yol = hw.get(ad)
        if yol:
            girdiler = ortak.hwmon_girdileri(yol, "fan")
            for anahtar in sorted(girdiler):
                deger = ortak.oku_sayi(f"{yol}/{anahtar}_input", 0)
                if deger > 0:
                    return deger
    # bilinen yonga yok: sıfırdan büyük ilk fanı al
    for ad, yol in hw.items():
        for anahtar in ortak.hwmon_girdileri(yol, "fan"):
            deger = ortak.oku_sayi(f"{yol}/{anahtar}_input", 0)
            if deger > 0:
                return deger
    return 0.0


def _ekstra(hw):
    """Kart üzerinde göstermeye değer diğer sıcaklıklar."""
    ilgi = [("nvme", "nvme"), ("pch_cannonlake", "pch"), ("pch_skylake", "pch"),
            ("pch_lewisburg", "pch"), ("iwlwifi", "wifi"), ("iwlwifi_1", "wifi"),
            ("iwlwifi_2", "wifi"), ("ath10k_hwmon", "wifi"), ("amdgpu", "gpu"),
            ("nouveau", "gpu"), ("acpitz", "acpi")]
    sonuc = []
    for yonga, etiket in ilgi:
        yol = hw.get(yonga)
        if yol:
            deger = ortak.oku_sayi(f"{yol}/temp1_input", 0) / 1000.0
            if 1 < deger < 150:
                sonuc.append((etiket, deger))
    # yinelenen etiketleri at
    gorulen = set()
    benzersiz = []
    for etiket, deger in sonuc:
        if etiket not in gorulen:
            gorulen.add(etiket)
            benzersiz.append((etiket, deger))
    return benzersiz


def oku(d, ayar):
    if d.hwmon is None:
        d.hwmon = ortak.hwmonlar()
    hw = d.hwmon
    paket, cek_maks, kaynak = _cpu_paket(hw)
    ekstra = _ekstra(hw)

    # çip üzerindeki diğer ilgi çekici sensörler (varsa)
    fan = _fan(hw)

    return {
        "paket": paket,
        "cekirdek_maks": cek_maks,
        "kaynak": kaynak or "yok",
        "fan": fan,
        "ekstra": ekstra,
        "sensor_var": bool(paket or cek_maks),
    }
