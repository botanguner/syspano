"""`kur-pi.sh` (Raspberry Pi / kiosk kurulumu) testleri.

Betik çalıştırılmaz gibi görünse de aslında **kuru çalıştırma** modu ile çalıştırılır:
geçici bir `HOME` verilir ve hiçbir dosyaya dokunulmadığı kanıtlanır. Böylece
kurulum betiğinin yolu/çıktısı bozulduğunda test yakalar. Görüntü gerekmez.
"""

import os
import pathlib
import subprocess
import tempfile

KOK = pathlib.Path(__file__).resolve().parent.parent
BETIK = KOK / "kur-pi.sh"


def test_sozdizimi():
    """`bash -n` temiz olmalı (CI de aynı denetimi yapar)."""
    c = subprocess.run(["bash", "-n", str(BETIK)], capture_output=True, text=True)
    assert c.returncode == 0, c.stderr


def test_kuru_calistirma_hicbir_seyi_degistirmez():
    """--kuru: planı yazar, hiçbir dosya oluşturmaz/değiştirmez."""
    with tempfile.TemporaryDirectory() as ev:
        ortam = dict(os.environ, HOME=ev, XDG_CONFIG_HOME=f"{ev}/.config",
                     WAYLAND_DISPLAY="", DISPLAY="")
        c = subprocess.run(["bash", str(BETIK), "--kuru"], capture_output=True,
                           text=True, env=ortam, timeout=120)
        assert c.returncode == 0, c.stderr
        cikti = c.stdout
        assert "--bekci" in cikti, cikti
        assert "Storage=persistent" in cikti, cikti
        assert "(kuru)" in cikti, cikti
        # hiçbir yapılandırma dosyası yazılmamalı
        yazilanlar = [str(p) for p in pathlib.Path(ev).rglob("*") if p.is_file()]
        assert yazilanlar == [], f"kuru çalıştırma dosya yazdı: {yazilanlar}"


def test_kuru_calistirma_var_olani_tekrar_eklemez():
    """Bekçi satırı zaten varsa kuru çalıştırma 'eklenecek' dememeli."""
    with tempfile.TemporaryDirectory() as ev:
        labwc = pathlib.Path(ev) / ".config/labwc"
        labwc.mkdir(parents=True)
        (labwc / "autostart").write_text("# mevcut\n/usr/bin/foo &\n"
                                         "/home/x/.local/bin/syspano --bekci &\n")
        ortam = dict(os.environ, HOME=ev, XDG_CURRENT_DESKTOP="labwc")
        c = subprocess.run(["bash", str(BETIK), "--kuru"], capture_output=True,
                           text=True, env=ortam, timeout=120)
        assert c.returncode == 0, c.stderr
        assert "zaten var" in c.stdout, c.stdout
        assert "eklenecek: " not in c.stdout.replace("(kuru)", ""), c.stdout


def test_yardim_metni():
    c = subprocess.run(["bash", str(BETIK), "--help"], capture_output=True, text=True)
    assert c.returncode == 0
    for anahtar in ("--kuru", "--geri-al", "--gunluk-yok", "--kartlar-ekle"):
        assert anahtar in c.stdout, f"{anahtar} yardımda yok"


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
