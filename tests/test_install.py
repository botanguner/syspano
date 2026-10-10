"""`install.sh` başlatma tercihleri testleri.

Kurulum yapılmaz: `--sadece-baslatma` paket kurulumunu atlar, geçici bir `HOME`
verilir ve betiğin **hangi başlatma ayarını** yazdığı denetlenir. Ayrıca
etkileşimli soru, boru ile beslenen girdiyle (`--sor`) sınanır.
"""

import os
import pathlib
import subprocess
import tempfile

KOK = pathlib.Path(__file__).resolve().parent.parent
BETIK = KOK / "install.sh"


def _calistir(ev, args, girdi=None):
    ortam = dict(os.environ, HOME=ev, XDG_CONFIG_HOME=f"{ev}/.config",
                 WAYLAND_DISPLAY="", DISPLAY="")
    return subprocess.run(["bash", str(BETIK), *args], capture_output=True, text=True,
                          env=ortam, input=girdi, stdin=subprocess.DEVNULL if girdi is None
                          else None, timeout=120)


def _desktop(ev):
    return pathlib.Path(ev) / ".config/autostart/syspano.desktop"


def _servis(ev):
    return pathlib.Path(ev) / ".config/systemd/user/syspano.service"


def test_sozdizimi_ve_yardim():
    c = subprocess.run(["bash", "-n", str(BETIK)], capture_output=True, text=True)
    assert c.returncode == 0, c.stderr
    c = subprocess.run(["bash", str(BETIK), "--yardim"], capture_output=True, text=True)
    assert c.returncode == 0
    for anahtar in ("--baslatma", "--sor", "--sadece-baslatma"):
        assert anahtar in c.stdout, f"{anahtar} yardımda yok"


def test_oturum_acilisi_secenegi_komutu_doldurur():
    with tempfile.TemporaryDirectory() as ev:
        c = _calistir(ev, ["--sadece-baslatma", "--baslatma", "oturum"])
        assert c.returncode == 0, c.stderr
        icerik = _desktop(ev).read_text()
        # şablondaki yer tutucu doldurulmalı (eskiden düz kopyalanınca bozuk kalıyordu)
        assert "@KOMUT@" not in icerik, icerik
        assert "Exec=" in icerik and "syspano" in icerik, icerik
        assert not _servis(ev).exists()


def test_manuel_secenegi_hicbir_sey_yazmaz():
    with tempfile.TemporaryDirectory() as ev:
        c = _calistir(ev, ["--sadece-baslatma", "--baslatma", "manuel"])
        assert c.returncode == 0, c.stderr
        assert "Otomatik başlatma kurulmadı" in c.stdout, c.stdout
        assert not _desktop(ev).exists()
        assert not _servis(ev).exists()


def test_servis_secenegi_birim_yazar():
    with tempfile.TemporaryDirectory() as ev:
        c = _calistir(ev, ["--sadece-baslatma", "--baslatma", "servis"])
        assert c.returncode == 0, c.stderr     # systemctl yoksa da çökmemeli
        icerik = _servis(ev).read_text()
        assert "@KOMUT@" not in icerik, icerik
        assert "ExecStart=" in icerik and "syspano" in icerik, icerik


def test_eski_bayraklar_uyumlu():
    """--autostart-yok = manuel, --servis = servis (geriye dönük uyum)."""
    with tempfile.TemporaryDirectory() as ev:
        assert _calistir(ev, ["--sadece-baslatma", "--autostart-yok"]).returncode == 0
        assert not _desktop(ev).exists()
    with tempfile.TemporaryDirectory() as ev:
        assert _calistir(ev, ["--sadece-baslatma", "--servis"]).returncode == 0
        assert _servis(ev).exists()


def test_etkilesimli_soru():
    """`--sor` ile boru girdisi okunur: 2 → systemd kullanıcı servisi."""
    with tempfile.TemporaryDirectory() as ev:
        c = _calistir(ev, ["--sadece-baslatma", "--sor"], girdi="2\n")
        assert c.returncode == 0, c.stderr
        assert "nasıl başlatmak istersiniz" in c.stdout, c.stdout
        assert _servis(ev).exists(), c.stdout
        assert not _desktop(ev).exists()
    with tempfile.TemporaryDirectory() as ev:
        c = _calistir(ev, ["--sadece-baslatma", "--sor"], girdi="3\n")
        assert "Otomatik başlatma kurulmadı" in c.stdout, c.stdout


def test_varsayilan_etkilesimsiz_oturum():
    """Bayrak/soru yoksa ve etkileşim yoksa: oturum açılışı (eski davranış)."""
    with tempfile.TemporaryDirectory() as ev:
        c = _calistir(ev, ["--sadece-baslatma"])
        assert c.returncode == 0, c.stderr
        assert "etkileşimli değil" in c.stdout, c.stdout
        assert _desktop(ev).exists()


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
