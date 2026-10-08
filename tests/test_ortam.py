"""Ortam algılama testleri: girdi aygıtları ve büyüteç kararı.

Fare/dokunmatik ayrımı, Raspberry Pi gibi yalnız dokunmatik cihazlarda
büyütecin gereksiz yere açılmasını önler; bu yüzden ayrıştırıcı burada
örnek /proc/bus/input/devices içerikleriyle sınanır.
"""

from syspano import ortam

# Logitech alıcı: göreli eksenleri var (fare) → REL=143 içinde bit 0 ve 1 açık
FARE = """I: Bus=0003 Vendor=046d Product=c52b Version=0111
N: Name="Logitech USB Receiver Mouse"
P: Phys=usb-0000:00:14.0-1/input0
S: Sysfs=/devices/pci0000:00/usb1/1-1/1-1:1.0/0003:046D:C52B.0001/input/input5
U: Uniq=
H: Handlers=sysrq kbd leds mouse0 event5
B: PROP=0
B: EV=17
B: KEY=ffff0000 0 0 0 0 0 0 0 0
B: REL=143
B: MSC=10
"""

# 7" dokunmatik panel: yalnız mutlak eksenler → REL satırı yok
DOKUNMATIK = """I: Bus=0018 Vendor=0000 Product=0000 Version=0000
N: Name="FT5406 memory based driver"
P: Phys=
S: Sysfs=/devices/platform/soc/fe804000.i2c/i2c-1/1-0048/input/input0
U: Uniq=
H: Handlers=event0
B: PROP=2
B: EV=b
B: KEY=400 0 0 0 0 0 0 0 0 0 0
B: ABS=2608000 1000003
"""

YALNIZ_KLAVYE = """I: Bus=0011 Vendor=0001 Product=0001 Version=ab41
N: Name="AT Translated Set 2 keyboard"
P: Phys=isa0060/serio0/input0
B: PROP=0
B: EV=120013
B: KEY=402000000 3803078f800d001 feffffdfffefffff fffffffffffffffe
B: MSC=10
B: LED=7
"""

# göreli ama yalnızca X ekseni (ör. dikey kaydırma tekerleği) → fare sayılmaz
YALNIZ_REL_X = """I: Bus=0003 Vendor=1234 Product=5678 Version=0001
N: Name="Garip Aygıt"
B: REL=1
"""


def test_fare_algilanir():
    assert ortam.goreli_ayristir(FARE) is True


def test_dokunmatik_fare_sayilmaz():
    assert ortam.goreli_ayristir(DOKUNMATIK) is False


def test_dokunmatik_mutlak_eksen():
    assert ortam.mutlak_ayristir(DOKUNMATIK) is True
    assert ortam.mutlak_ayristir(FARE) is False


def test_klavye_hicbiri():
    assert ortam.goreli_ayristir(YALNIZ_KLAVYE) is False
    assert ortam.mutlak_ayristir(YALNIZ_KLAVYE) is False


def test_tek_eksen_yetmez():
    assert ortam.goreli_ayristir(YALNIZ_REL_X) is False


def test_bos_icerik():
    assert ortam.goreli_ayristir("") is False
    assert ortam.goreli_ayristir(None) is False


def test_bozuk_maskeler_cokertmez():
    assert ortam.goreli_ayristir("B: REL=zzz\nB: REL=\nB: REL=3") is True


def test_ikisi_birden():
    """Fare + dokunmatik birlikte: fare varsa göreli eksen de vardır."""
    assert ortam.goreli_ayristir(FARE + "\n" + DOKUNMATIK) is True


if __name__ == "__main__":
    import sys
    import traceback
    gecen, kalan = 0, 0
    for ad, fonk in sorted(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            try:
                fonk()
                print(f"  ✓ {ad}")
                gecen += 1
            except Exception:
                print(f"  ✗ {ad}")
                traceback.print_exc()
                kalan += 1
    print(f"\n{gecen} geçti, {kalan} kaldı")
    sys.exit(1 if kalan else 0)
