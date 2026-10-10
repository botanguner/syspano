"""Başlatma yöntemi ve systemd kullanıcı servisi testleri.

`systemctl` çağrıları taklit edilir; geçici `HOME`/`XDG_STATE_HOME` kullanılır.
Görüntü (X11) gerekmez.
"""

import os
import pathlib
import tempfile

from syspano import baslatma


def _sahte_calistir(durum="active"):
    """systemctl/journalctl çağrılarını taklit eder; çağrıları kaydeder."""
    cagrilar = []

    def sahte(komut, zaman=8):
        cagrilar.append(list(komut))
        ad = komut[2] if len(komut) > 2 and komut[0] == "systemctl" else ""
        if ad == "is-active":
            return 0, durum
        if ad == "is-failed":
            return 0, "failed" if durum == "failed" else "inactive"
        if ad == "show":
            return 0, "4242"
        if ad == "cat":
            return 0, "[Unit]"
        return 0, ""

    return sahte, cagrilar


def test_durum_elle():
    with tempfile.TemporaryDirectory() as ev:
        eski = os.environ.get("HOME")
        os.environ["HOME"] = ev
        try:
            baslatma._onbellek.update({"zaman": 0.0, "sonuc": {}})
            gercek = baslatma._calistir
            sahte, _ = _sahte_calistir()
            sahte_kod = lambda k, z=8: (1, "")          # birim yok
            baslatma._calistir = sahte_kod
            try:
                metin, renk, eylemler = baslatma.durum_metni()
            finally:
                baslatma._calistir = gercek
            assert "elle" in metin and eylemler == ["servis_kur"], (metin, eylemler)
        finally:
            if eski:
                os.environ["HOME"] = eski
            else:
                del os.environ["HOME"]


def test_durum_oturum_acilisi():
    with tempfile.TemporaryDirectory() as ev:
        os.environ["HOME"] = ev
        try:
            yol = pathlib.Path(ev) / ".config/autostart"
            yol.mkdir(parents=True)
            (yol / "syspano.desktop").write_text("[Desktop Entry]\nExec=x\n")
            baslatma._onbellek.update({"zaman": 0.0, "sonuc": {}})
            gercek = baslatma._calistir
            baslatma._calistir = lambda k, z=8: (1, "")
            try:
                metin, renk, eylemler = baslatma.durum_metni()
            finally:
                baslatma._calistir = gercek
            assert "oturum açılışı" in metin and renk == "yesil", metin
            assert eylemler == ["servis_kur"], eylemler
        finally:
            del os.environ["HOME"]


def test_servis_kurulunca_durum_ve_eylemler():
    with tempfile.TemporaryDirectory() as ev:
        os.environ["HOME"] = ev
        try:
            baslatma._onbellek.update({"zaman": 0.0, "sonuc": {}})
            gercek = baslatma._calistir
            sahte, cagrilar = _sahte_calistir("active")
            baslatma._calistir = sahte
            try:
                # birim yokken kur
                basarili, mesaj = baslatma.servis_kur()
                assert basarili and "kuruldu" in mesaj.lower(), mesaj
                birim = pathlib.Path(baslatma.birim_yolu())
                assert birim.exists()
                icerik = birim.read_text()
                assert "ExecStart=" in icerik and "syspano" in icerik
                assert "WantedBy=graphical-session.target" in icerik
                # çalışan servis: durdur + yeniden başlat sunulur
                metin, renk, eylemler = baslatma.durum_metni()
            finally:
                baslatma._calistir = gercek
            assert "systemd kullanıcı servisi" in metin and renk == "yesil", metin
            assert eylemler == ["servis_yeniden", "servis_durdur"], eylemler
        finally:
            del os.environ["HOME"]


def test_servis_durmus_ise_baslat_sunulur():
    with tempfile.TemporaryDirectory() as ev:
        os.environ["HOME"] = ev
        try:
            baslatma._onbellek.update({"zaman": 0.0, "sonuc": {}})
            gercek = baslatma._calistir
            sahte, _ = _sahte_calistir("inactive")
            baslatma._calistir = sahte
            try:
                baslatma.servis_kur()
                metin, renk, eylemler = baslatma.durum_metni()
            finally:
                baslatma._calistir = gercek
            assert "inactive" in metin or "kapalı" in metin, metin
            assert "servis_baslat" in eylemler and "servis_durdur" not in eylemler, eylemler
        finally:
            del os.environ["HOME"]


def test_servis_kur_oturum_girdisini_kapatir():
    """Servis kurulunca oturum açılışı girdisi kapatılmalı (çift pano olmasın)."""
    with tempfile.TemporaryDirectory() as ev:
        os.environ["HOME"] = ev
        try:
            baslatma._onbellek.update({"zaman": 0.0, "sonuc": {}})
            girdi = pathlib.Path(ev) / ".config/autostart/syspano.desktop"
            girdi.parent.mkdir(parents=True)
            girdi.write_text("[Desktop Entry]\nExec=x\nHidden=false\n")
            gercek = baslatma._calistir
            sahte, _ = _sahte_calistir()
            baslatma._calistir = sahte
            try:
                baslatma.servis_kur()
            finally:
                baslatma._calistir = gercek
            assert "Hidden=true" in girdi.read_text()
        finally:
            del os.environ["HOME"]


def test_servis_eylemleri_ve_hata():
    cagrilar = []
    gercek = baslatma._calistir
    baslatma._calistir = lambda komut, z=20: (cagrilar.append(list(komut)), (0, ""))[1]
    try:
        for eylem, beklenen in (("baslat", "start"), ("durdur", "stop"),
                                ("yeniden", "restart")):
            basarili, mesaj = baslatma.servis_eylemi(eylem)
            assert basarili, mesaj
            assert beklenen in cagrilar[-1], cagrilar[-1]
        # durdurma bloklamasın (systemctl bizi kapatacak)
        durdurma = [c for c in cagrilar if "stop" in c][-1]
        assert "--no-block" in durdurma, durdurma
        basarili, mesaj = baslatma.servis_eylemi("yok-boyle")
        assert basarili is False and "bilinmeyen" in mesaj
    finally:
        baslatma._calistir = gercek
    gercek = baslatma._calistir
    baslatma._calistir = lambda komut, z=20: (1, "parola gerekli")
    try:
        basarili, mesaj = baslatma.servis_eylemi("baslat")
        assert basarili is False and "systemctl" in mesaj, mesaj
    finally:
        baslatma._calistir = gercek


def test_birim_icerigi_bekci_ile():
    icerik = baslatma.birim_icerigi("/usr/bin/python3 -m syspano", bekci=True)
    assert "ExecStart=/usr/bin/python3 -m syspano --bekci" in icerik, icerik
    # zaten --bekci varsa iki kez eklenmez
    icerik2 = baslatma.birim_icerigi("/bin/syspano --bekci", bekci=True)
    assert icerik2.count("--bekci") == 1, icerik2


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
