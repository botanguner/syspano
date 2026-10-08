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
            guncelleme._denetim_yaz({"zaman": 1, "yeni": True, "yerel": "1.0.0",
                                     "depo_surum": "1.1.0", "kurulum_gerekli": True})
            assert "yeniden kurulum" in guncelleme.metin_ozet()
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_durum_metni_asamalari():
    """Ayarlar ekranındaki durum satırı her aşamayı doğru ve net anlatmalı."""
    import time
    simdi = 1_800_000_000.0
    # 1) denetim sürüyor
    metin, renk = guncelleme.durum_metni(denetim={}, surec={}, simdi=simdi,
                                         denetim_suruyor=True)
    assert "Denetleniyor" in metin and renk == "mavi"
    # 2) güncelleme sürüyor
    metin, renk = guncelleme.durum_metni(
        denetim={}, simdi=simdi, baslangic=0,
        surec={"asama": guncelleme.GUNCELLEME_ASAMASI, "basladi": simdi - 42})
    assert "sürüyor" in metin and "42 sn" in metin and renk == "mavi"
    # 3) güncelleme başarıyla bitti → yeniden başlat çağrısı
    metin, renk = guncelleme.durum_metni(
        denetim={}, simdi=simdi, baslangic=0,
        surec={"asama": guncelleme.GUNCELLEME_ASAMASI, "bitti": simdi,
               "sonuc": 0, "surum": "9.9.9"})
    assert "tamam" in metin and "9.9.9" in metin and "yeniden başlat" in metin.lower()
    assert renk == "sari"
    # 4) güncelleme başarısız
    metin, renk = guncelleme.durum_metni(
        denetim={}, simdi=simdi, baslangic=0,
        surec={"asama": guncelleme.GUNCELLEME_ASAMASI, "bitti": simdi, "sonuc": 1,
               "mesaj": "pip kurulumu başarısız"})
    assert "başarısız" in metin and "pip" in metin and renk == "kirmizi"
    # 5) denetim zaman aşımı
    metin, renk = guncelleme.durum_metni(denetim={}, surec={}, simdi=simdi,
                                         zaman_asimi=True, baslangic=0)
    assert "zaman aşımı" in metin and renk == "kirmizi"
    # 6) denetim hatası
    metin, renk = guncelleme.durum_metni(
        denetim={"zaman": simdi - 10, "hata": "ağ yok"}, surec={}, simdi=simdi,
        baslangic=0)
    assert "Denetlenemedi" in metin and "ağ yok" in metin and renk == "kirmizi"
    # 7) yeni sürüm var
    metin, renk = guncelleme.durum_metni(
        denetim={"zaman": simdi - 10, "yeni": True, "depo_surum": "1.9.0"},
        surec={}, simdi=simdi, baslangic=0)
    assert "Yeni sürüm var" in metin and "1.9.0" in metin and renk == "sari"
    # 8) güncel
    metin, renk = guncelleme.durum_metni(
        denetim={"zaman": simdi - 600, "yeni": False}, surec={}, simdi=simdi,
        baslangic=0)
    assert "Güncel" in metin and "10 dk önce" in metin and renk == "yesil"
    # 9) hiç denetim yok
    metin, renk = guncelleme.durum_metni(denetim={}, surec={}, simdi=simdi,
                                         baslangic=0)
    assert "bilinmiyor" in metin and renk == "soluk"


def test_surec_durumu_gidis_donus():
    """Pano, arka plandaki güncelleme sürecinin durumunu dosyadan okuyabilmeli."""
    import time
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        try:
            assert guncelleme.surec_oku() == {}
            guncelleme.surec_yaz(guncelleme.GUNCELLEME_ASAMASI,
                                 baslangic=time.time(), mesaj="başlatıldı")
            surec = guncelleme.surec_oku()
            assert surec["asama"] == guncelleme.GUNCELLEME_ASAMASI
            assert "bitti" not in surec
            # sürerken durum metni "sürüyor" demeli
            metin, renk = guncelleme.durum_metni(baslangic=0)
            assert "sürüyor" in metin and renk == "mavi"
            # bitince sonuç yazılır
            guncelleme.surec_yaz(guncelleme.GUNCELLEME_ASAMASI, sonuc=0, surum="9.9.9")
            surec = guncelleme.surec_oku()
            assert surec["sonuc"] == 0 and surec["surum"] == "9.9.9"
            assert surec["bitti"] >= surec["basladi"]
            metin, _ = guncelleme.durum_metni(baslangic=0)
            assert "tamam" in metin and "9.9.9" in metin
            # başarısız güncelleme
            guncelleme.surec_yaz(guncelleme.GUNCELLEME_ASAMASI, sonuc=1, mesaj="disk dolu")
            metin, renk = guncelleme.durum_metni(baslangic=0)
            assert "başarısız" in metin and "disk dolu" in metin and renk == "kirmizi"
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_yeniden_baslat_gerekli_dosya_zamani():
    """Kurulu kod, pano açıldıktan SONRA değiştiyse yeniden başlatma gerekir."""
    yol = guncelleme.kurulu_dosya()
    if not yol:
        print("    (kurulu paket yolu bulunamadı — atlandı)")
        return
    import time
    # pano "şimdi" açıldı, kurulu dosya eski → gerek yok
    assert guncelleme.yeniden_baslat_gerekli(baslangic=time.time() - 5) is False
    # pano "dün" açıldı, kurulu dosya bugün değişti → gerekli
    assert guncelleme.yeniden_baslat_gerekli(baslangic=time.time() - 86400) is True


def test_yeniden_baslat_yolu_ortama_gore():
    """Servis varsa systemctl, masaüstü oturumunda pano düğmesi söylenmeli."""
    gercek = guncelleme.systemd_kullanici_birimi
    try:
        guncelleme.systemd_kullanici_birimi = lambda: True
        assert "systemctl --user restart syspano" in guncelleme.yeniden_baslat_yolu()
        guncelleme.systemd_kullanici_birimi = lambda: False
        metin = guncelleme.yeniden_baslat_yolu()
        assert "Panoyu yeniden başlat" in metin and "systemctl" not in metin
    finally:
        guncelleme.systemd_kullanici_birimi = gercek


def test_depo_surumu_okuma():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "src", "syspano"))
        with open(os.path.join(d, "src", "syspano", "__init__.py"), "w") as f:
            f.write('"""x"""\n__version__ = "3.4.5"\n')
        assert guncelleme._depo_surumu(d) == "3.4.5"
    assert guncelleme._depo_surumu(None) is None
    assert guncelleme._depo_surumu("/yok/boyle/dizin") is None


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


def test_guncelleme_sonrasi_rozet_duzelir():
    """`guncelle()` sonrası önbellek "güncel" demeli.

    Güncellemeyi çalıştıran süreç **eski sürümü bellekte** tutar. Denetim
    çalışan sürümle yapılırsa önbelleğe "depodaki sürüm X, kurulu paket Y"
    yazılır ve panoda güncelleme sonrası yanlış bir rozet kalır. Bu, canlı bir
    sistemde görüldü (Raspberry Pi: 1.3.1 kurulduktan sonra rozet duruyordu).
    """
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
        os.makedirs(os.path.join(yerel, "src", "syspano"))
        with open(os.path.join(yerel, "src", "syspano", "__init__.py"), "w") as f:
            f.write('"""x"""\n__version__ = "9.9.9"\n')      # depo sürümü
        _git("add", "-A", cwd=yerel)
        _git("commit", "-m", "surum 9.9.9", cwd=yerel)
        _git("remote", "add", "origin", uzak, cwd=yerel)
        _git("push", "-u", "origin", "main", cwd=yerel)

        os.environ["XDG_STATE_HOME"] = os.path.join(kok, "durum")
        try:
            guncelleme.kayit_yaz("pip-kullanici", yerel, uzak)
            once = guncelleme.denetle()
            assert once["kurulum_gerekli"] is True, once
            assert guncelleme.yeni_surum_var() is True

            cikti = guncelleme.guncelle(tekrar_kur=False)   # yalnız git adımı
            assert cikti["ok"] is True, cikti

            sonra = guncelleme.denetim_oku()
            assert not sonra.get("kurulum_gerekli"), sonra
            assert sonra["yeni"] is False, sonra
            assert sonra["yerel"] == "9.9.9", sonra
            assert guncelleme.yeni_surum_var() is False
            assert "güncel" in guncelleme.metin_ozet()
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_guncelle_sh_surum_farkini_yakalar():
    """`git pull` yapılıp paket kurulmadıysa guncelle.sh bunu görmeli.

    Kullanıcının yaşadığı durum: depo ilerletilmiş ama `pip install`
    çalıştırılmamış; betik "yeni commit yok" deyip hiçbir şey yapmıyordu.
    Artık kurulu sürümle depo sürümünü karşılaştırıp yeniden kuruyor.
    """
    if not GIT:
        print("    (git yok — atlandı)")
        return
    betik = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "guncelle.sh")
    if not os.path.exists(betik):
        print("    (guncelle.sh yok — atlandı)")
        return

    with tempfile.TemporaryDirectory() as kok:
        # sahte `syspano`: sürümünü biz belirliyoruz
        bindir = os.path.join(kok, "bin")
        os.makedirs(bindir)
        sahte = os.path.join(bindir, "syspano")

        def surum_ayarla(surum):
            with open(sahte, "w") as f:
                f.write(f"#!/bin/sh\necho 'SysPano {surum}'\n")
            os.chmod(sahte, 0o755)

        # uzak depo + klon
        uzak = os.path.join(kok, "uzak.git")
        depo = os.path.join(kok, "depo")
        subprocess.run([GIT, "init", "--bare", "--initial-branch=main", uzak],
                       capture_output=True, text=True)
        os.makedirs(depo)
        _git("init", "--initial-branch=main", cwd=depo)
        os.makedirs(os.path.join(depo, "src", "syspano"))
        with open(os.path.join(depo, "src", "syspano", "__init__.py"), "w") as f:
            f.write('"""x"""\n__version__ = "1.1.0"\n')
        shutil.copy2(betik, os.path.join(depo, "guncelle.sh"))
        os.chmod(os.path.join(depo, "guncelle.sh"), 0o755)
        _git("add", "-A", cwd=depo)
        _git("commit", "-m", "surum 1.1.0", cwd=depo)
        _git("remote", "add", "origin", uzak, cwd=depo)
        _git("push", "-u", "origin", "main", cwd=depo)

        ortam = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"],
                     XDG_STATE_HOME=os.path.join(kok, "durum"))

        # 1) kurulu sürüm depoyla aynı → yapılacak bir şey yok
        surum_ayarla("1.1.0")
        c = subprocess.run(["./guncelle.sh", "--denetle"], cwd=depo, env=ortam,
                           capture_output=True, text=True, timeout=60)
        cikti = c.stdout + c.stderr
        assert "yapılacak bir şey yok" in cikti, cikti
        assert c.returncode == 0, cikti

        # 2) kurulu sürüm eski (git pull yapılmış, kurulmamış) → fark bildirilmeli
        surum_ayarla("1.0.0")
        c = subprocess.run(["./guncelle.sh", "--denetle"], cwd=depo, env=ortam,
                           capture_output=True, text=True, timeout=60)
        cikti = c.stdout + c.stderr
        assert "Düzeltmek için" in cikti, cikti
        assert "1.0.0" in cikti and "1.1.0" in cikti, cikti
        assert c.returncode == 0, cikti

        # 3) paket hiç kurulu değilse bunu açıkça söylemeli
        if not shutil.which("syspano", path="/usr/local/bin:/usr/bin:/bin"):
            os.remove(sahte)
            c = subprocess.run(["./guncelle.sh", "--denetle"], cwd=depo, env=ortam,
                               capture_output=True, text=True, timeout=60)
            cikti = c.stdout + c.stderr
            assert "PATH'te 'syspano' yok" in cikti, cikti



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
