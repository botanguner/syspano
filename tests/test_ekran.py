"""Ekran keşfi testleri: xrandr/kscreen çıktısı ayrıştırma ve ekran seçimi.

Sistem komutları sahte çıktılarla değiştirilir; gerçek donanım gerekmez.
"""

from syspano import ekran

XRANDR = """Screen 0: minimum 16 x 16, current 2592 x 2538, maximum 32767 x 32767
eDP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 309mm x 174mm
   1920x1080     59.98*+
HDMI-A-1 connected 2160x1080+220+1458 right (normal left inverted right x axis y axis) 134mm x 66mm
   2160x1080     60.00*+
DP-1 disconnected (normal left inverted right x axis y axis)
"""

KSCREEN = """Output: 1 HDMI-A-1 38c60ac6
\tenabled
\tGeometry: 163,1080 1600x800
\tScale: 1.35
Output: 2 eDP-1 c633866f
\tenabled
\tGeometry: 0,0 1920x1080
\tScale: 1
"""


def _sahte_komut(harita):
    def komut(cmd, zaman=4):
        for anahtar, cikti in harita.items():
            if anahtar in " ".join(cmd):
                return cikti
        return ""
    return komut


def test_xrandr_ayristirma(monkeypatch=None):
    eski = ekran.ortam.komut
    ekran.ortam.komut = _sahte_komut({"xrandr": XRANDR, "kscreen-doctor": KSCREEN})
    try:
        cikislar = ekran.cikislari_bul()
        adlar = [c.ad for c in cikislar]
        assert adlar == ["eDP-1", "HDMI-A-1"], adlar
        edp, hdmi = cikislar
        assert edp.birincil and not hdmi.birincil
        assert (hdmi.x, hdmi.y, hdmi.g, hdmi.yuk) == (220, 1458, 2160, 1080)
        assert (hdmi.mm_g, hdmi.mm_y) == (134, 66)
        # KWin mantıksal geometrisi eklenmiş olmalı
        assert hdmi.kk == (163, 1080, 1600, 800)
        assert edp.kk == (0, 0, 1920, 1080)
        assert hdmi.tk_geom == (220, 1458, 2160, 1080)
        assert hdmi.kwin_geom == (163, 1080, 1600, 800)
    finally:
        ekran.ortam.komut = eski


def test_dpi_hesabi():
    c = ekran.Cikis("X", 0, 0, 2592, 1458)   # 309x174 mm ≈ 14" köşegen
    c.mm_g, c.mm_y = 309, 174
    assert 200 < c.dpi < 225
    bos = ekran.Cikis("Y", 0, 0, 1920, 1080)
    assert bos.dpi == 0.0            # mm yoksa 0


def test_ekran_secimi():
    eski = ekran.ortam.komut
    ekran.ortam.komut = _sahte_komut({"xrandr": XRANDR, "kscreen-doctor": KSCREEN})
    try:
        c = ekran.cikislari_bul()
        assert ekran.ekran_sec("ana", c).ad == "eDP-1"
        assert ekran.ekran_sec("HDMI-A-1", c).ad == "HDMI-A-1"
        assert ekran.ekran_sec("auto", c).ad == "HDMI-A-1"   # ikincil yeğlenir
        assert ekran.ekran_sec("0", c).ad == "eDP-1"
        assert ekran.ekran_sec("1", c).ad == "HDMI-A-1"
        assert ekran.ekran_sec("tumu", c) is None
        assert ekran.ekran_sec("yok-boyle", c) is None
    finally:
        ekran.ortam.komut = eski


def test_sanal_ekran():
    eski = ekran.ortam.komut
    ekran.ortam.komut = _sahte_komut({"xrandr": XRANDR})
    try:
        assert ekran.sanal_ekran() == (2592, 2538)
    finally:
        ekran.ortam.komut = eski


if __name__ == "__main__":
    import traceback
    gecen = kalan = 0
    for ad, fonk in sorted(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            try:
                fonk(); print(f"  ✓ {ad}"); gecen += 1
            except Exception:
                print(f"  ✗ {ad}"); traceback.print_exc(); kalan += 1
    print(f"\n{gecen} geçti, {kalan} kaldı")
    raise SystemExit(1 if kalan else 0)
