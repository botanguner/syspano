"""Güncelleme testleri.

Klon tabanlı güncelleme gerçek bir git senaryosuyla sınanır: geçici bir "uzak"
depo kurulur, yerel kopya bir commit geride bırakılır ve denetle/güncelle
adımlarının doğru davrandığı görülür. Görüntü (X11) gerekmez.
"""

import os
import shutil
import subprocess
import tempfile

from syspano import guncelleme

GIT = shutil.which("git")


# ─── saf yardımcılar ─────────────────────────────────────────────────────────
def test_surum_karsilastir():
    assert guncelleme.surum_karsilastir("1.0.0", "1.0.1") == -1
    assert guncelleme.surum_karsilastir("1.0.1", "1.0.1") == 0
    assert guncelleme.surum_karsilastir("v1.2.0", "1.1.9") == 1
    assert guncelleme.surum_karsilastir("2.0", "1.9.9") == 1
    assert guncelleme.surum_karsilastir("çöp", "0.0.1") == -1


def test_surum_parcala():
    assert guncelleme.surum_parcala("v1.2.3-4-gabcdef") == (1, 2, 3)
    assert guncelleme.surum_parcala("1.4") == (1, 4, 0)
    assert guncelleme.surum_parcala(None) == (0, 0, 0)
    assert guncelleme.surum_parcala("yok") == (0, 0, 0)


def test_etiket_ayristirma():
    cikti = (
        "aaa111\trefs/tags/v1.0.0\n"
        "bbb222\trefs/tags/v1.1.0\n"
        "ccc333\trefs/tags/v1.1.0^{}\n"
        "ddd444\trefs/tags/surum-degil\n"
        "eee555\trefs/heads/main\n"
    )
    assert guncelleme.etiketleri_ayristir(cikti) == ["v1.0.0", "v1.1.0"]
    assert guncelleme.etiketleri_ayristir("") == []


# ─── kurulum kaydı ───────────────────────────────────────────────────────────
def test_kayit_gidis_donus():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        try:
            assert guncelleme.kayit_oku() == {}
            guncelleme.kayit_yaz("pipx", "/tmp/depo", "https://ornek/depo.git", "9.9.9")
            kayit = guncelleme.kayit_oku()
            assert kayit["yontem"] == "pipx"
            assert kayit["kaynak"] == "/tmp/depo"
            assert kayit["surum"] == "9.9.9"
            assert os.path.exists(guncelleme.kayit_yolu())
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_denetim_bayati():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        try:
            assert guncelleme.denetim_bayati(24) is True     # kayıt yok → bayat
            guncelleme._denetim_yaz({"zaman": __import__("time").time(), "yeni": False})
            assert guncelleme.denetim_bayati(24) is False
            assert guncelleme.yeni_surum_var() is False
            guncelleme._denetim_yaz({"zaman": __import__("time").time(), "yeni": True})
            assert guncelleme.yeni_surum_var() is True
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_ozet_metni():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        try:
            assert "bilinmiyor" in guncelleme.metin_ozet()
            guncelleme._denetim_yaz({"zaman": 1, "yeni": False, "yerel": "1.0.1"})
            assert "güncel" in guncelleme.metin_ozet()
            guncelleme._denetim_yaz({"zaman": 1, "yeni": True, "yerel": "1.0.1",
                                     "uzak": "v1.0.2"})
            ozet = guncelleme.metin_ozet()
            assert "yeni sürüm" in ozet and "v1.0.2" in ozet
        finally:
            del os.environ["XDG_STATE_HOME"]


# ─── gerçek git senaryosu ────────────────────────────────────────────────────
def _git(*args, cwd):
    return subprocess.run([GIT, "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          cwd=cwd, capture_output=True, text=True)


def test_klon_denetle_ve_guncelle():
    if not GIT:
        print("    (git yok — atlandı)")
        return
    with tempfile.TemporaryDirectory() as kok:
        uzak = os.path.join(kok, "uzak.git")
        yerel = os.path.join(kok, "yerel")
        os.makedirs(yerel)
        subprocess.run([GIT, "init", "--bare", "--initial-branch=main", uzak],
                       capture_output=True, text=True)
        _git("init", "--initial-branch=main", cwd=yerel)
        with open(os.path.join(yerel, "dosya.txt"), "w") as f:
            f.write("ilk\n")
        _git("add", "-A", cwd=yerel)
        _git("commit", "-m", "ilk", cwd=yerel)
        _git("remote", "add", "origin", uzak, cwd=yerel)
        _git("push", "-u", "origin", "main", cwd=yerel)

        # ikinci bir kopyayla uzağa yeni bir commit ekle → yerel geride kalsın
        digeri = os.path.join(kok, "digeri")
        subprocess.run([GIT, "clone", uzak, digeri], capture_output=True, text=True)
        with open(os.path.join(digeri, "dosya.txt"), "w") as f:
            f.write("ikinci\n")
        _git("add", "-A", cwd=digeri)
        _git("commit", "-m", "ikinci surum", cwd=digeri)
        _git("push", cwd=digeri)

        os.environ["XDG_STATE_HOME"] = os.path.join(kok, "durum")
        try:
            guncelleme.kayit_yaz("pip-kullanici", yerel, uzak, "1.0.0")

            sonuc = guncelleme.denetle()
            assert sonuc["yeni"] is True, sonuc
            assert sonuc["geride"] == 1, sonuc
            assert "ikinci" in sonuc["mesaj"]
            assert guncelleme.yeni_surum_var() is True

            # güncelle: yalnızca git adımı (kurulum adımı atlanır)
            cikti = guncelleme.guncelle(tekrar_kur=False)
            assert cikti["ok"] is True, cikti
            assert cikti["yeniden_baslat"] is True
            with open(os.path.join(yerel, "dosya.txt")) as f:
                assert f.read() == "ikinci\n"

            # artık güncel olmalı
            sonuc2 = guncelleme.denetle()
            assert sonuc2["yeni"] is False, sonuc2
            assert guncelleme.yeni_surum_var() is False
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_kirli_agacta_guncellemez():
    if not GIT:
        print("    (git yok — atlandı)")
        return
    with tempfile.TemporaryDirectory() as kok:
        yerel = os.path.join(kok, "yerel")
        os.makedirs(yerel)
        _git("init", "--initial-branch=main", cwd=yerel)
        with open(os.path.join(yerel, "a.txt"), "w") as f:
            f.write("a\n")
        _git("add", "-A", cwd=yerel)
        _git("commit", "-m", "a", cwd=yerel)
        with open(os.path.join(yerel, "a.txt"), "w") as f:
            f.write("değişti\n")          # kaydedilmemiş değişiklik

        os.environ["XDG_STATE_HOME"] = os.path.join(kok, "durum")
        try:
            guncelleme.kayit_yaz("pip-kullanici", yerel)
            cikti = guncelleme.guncelle(tekrar_kur=False)
            assert cikti["ok"] is False
            assert any("kaydedilmemiş" in m for _, m in cikti["adimlar"]), cikti
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_kayit_yoksa_yonlendirir():
    with tempfile.TemporaryDirectory() as kok:
        os.environ["XDG_STATE_HOME"] = os.path.join(kok, "durum")
        try:
            cikti = guncelleme.guncelle(tekrar_kur=False)
            assert cikti["ok"] is False
            assert any("Kurulum kaydı yok" in m for _, m in cikti["adimlar"]), cikti
        finally:
            del os.environ["XDG_STATE_HOME"]


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
