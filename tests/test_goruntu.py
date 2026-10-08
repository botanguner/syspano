"""Ekran görüntüsü (`--cek`) testleri: araç seçimi ve kaydetme davranışı.

Süreç başlatılmaz: `shutil.which` ve `subprocess.run` taklit edilir; dosya
oluşturma geçici dizinde yapılır. Görüntü (X11) gerekmez.
"""

import os
import tempfile
from types import SimpleNamespace

from syspano import goruntu


def _bul(sahte):
    return lambda ad: f"/usr/bin/{ad}" if ad in sahte else None


def test_arac_sec_wayland_grim():
    secim = goruntu.arac_sec({"WAYLAND_DISPLAY": "wayland-0"}, bul=_bul({"grim"}))
    assert secim == ("grim", ["grim"])


def test_arac_sec_wayland_grim_yoksa_x11e_duser():
    ortam = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
    assert goruntu.arac_sec(ortam, bul=_bul({"scrot"})) == ("scrot", ["scrot", "-o"])
    # ImageMagick `import` bilerek otomatik seçilmez (etkileşimli bekleyebiliyor)
    assert goruntu.arac_sec(ortam, bul=_bul({"import"})) is None


def test_arac_sec_x11_scrot_oncelikli():
    secim = goruntu.arac_sec({"DISPLAY": ":0"}, bul=_bul({"scrot", "import"}))
    assert secim[0] == "scrot"


def test_arac_sec_arac_yoksa_none():
    assert goruntu.arac_sec({"DISPLAY": ":0"}, bul=_bul(set())) is None
    assert goruntu.arac_sec({}, bul=_bul({"grim", "scrot"})) is None


def test_varsayilan_yol_zaman_damgali():
    yol = goruntu.varsayilan_yol(1_800_000_000)
    assert yol.endswith(".png") and "/syspano-" in yol
    assert "2026" in os.path.basename(yol) or "2027" in os.path.basename(yol)


def test_cek_dosya_olusturulur():
    """Başarılı çekim: (True, mesaj) ve dosya yerinde olmalı."""
    with tempfile.TemporaryDirectory() as d:
        hedef = os.path.join(d, "alt", "pano.png")

        def sahte_calistir(komut):
            # araç dosyayı yazmış gibi davran
            with open(komut[-1], "w") as f:
                f.write("png")
            return SimpleNamespace(returncode=0, stderr="")

        ok, mesaj = goruntu.cek(hedef, {"WAYLAND_DISPLAY": "wayland-0"},
                                calistir=sahte_calistir, bul=_bul({"grim"}))
        assert ok is True and "grim" in mesaj and os.path.exists(hedef)


def test_cek_basarisizlik_mesaji():
    def sahte_calistir(komut):
        return SimpleNamespace(returncode=1, stderr="cannot open display\nayrıntı")

    with tempfile.TemporaryDirectory() as d:
        ok, mesaj = goruntu.cek(os.path.join(d, "x.png"), {"DISPLAY": ":0"},
                                calistir=sahte_calistir, bul=_bul({"scrot"}))
    assert ok is False and "scrot" in mesaj and "cannot open display" in mesaj


def test_cek_arac_yoksa_anlasilir_hata():
    ok, mesaj = goruntu.cek("/tmp/yok.png", {}, bul=_bul(set()))
    assert ok is False and "grim" in mesaj and "scrot" in mesaj


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
