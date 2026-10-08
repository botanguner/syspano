"""Bekçi testleri: karar mantığı, kalp atışı, süreç tanıma ve sonlandırma.

Süreç başlatılmaz: `oldur()` yalnızca zararsız bir `sleep` süreci üzerinde
denenir. Görüntü (X11) gerekmez.
"""

import os
import subprocess
import tempfile
import time

from syspano import bekci


# ─── karar mantığı (saf) ─────────────────────────────────────────────────────
def test_karar_baslat_oldur_bekle():
    assert bekci.karar(False, None, 90) == "baslat"
    assert bekci.karar(False, 1000, 90) == "baslat"          # süreç yoksa kalp bakılmaz
    assert bekci.karar(True, None, 90) == "bekle"            # kalp dosyası yok: yeni başlıyor
    assert bekci.karar(True, 5, 90) == "bekle"
    assert bekci.karar(True, 90, 90) == "bekle"              # eşitlik donma sayılmaz
    assert bekci.karar(True, 90.5, 90) == "oldur"
    assert bekci.karar(True, 500, 90) == "oldur"
    assert bekci.karar(True, 100, None) == "oldur"           # varsayılan eşik 90


def test_karar_yeni_baslayan_panoyu_oldurmez():
    """Eski kalp atışı yüzünden yeni başlayan pano öldürülmemeli (Pi'de yaşandı)."""
    assert bekci.karar(True, 600, 30, surec_yasi_sn=1) == "bekle"
    assert bekci.karar(True, 600, 30, surec_yasi_sn=14.9) == "bekle"
    assert bekci.karar(True, 600, 30, surec_yasi_sn=16) == "oldur"
    # süreç yaşı bilinmiyorsa eski davranış: eşiğe göre karar
    assert bekci.karar(True, 600, 30, surec_yasi_sn=None) == "oldur"


def test_surec_yasi_okunur():
    yas = bekci.surec_yasi(os.getpid())
    assert yas is not None and 0 <= yas < 3600, yas
    assert bekci.surec_yasi(999999) is None                  # olmayan süreç


def test_eslesme():
    assert bekci.eslesme(["python3", "-m", "syspano"]) is True
    assert bekci.eslesme(["/usr/bin/python3", "/home/x/.local/bin/syspano"]) is True
    assert bekci.eslesme(["python3", "-m", "syspano", "--demo"]) is True
    # bekçinin kendisi ve tepsi pano sayılmamalı
    assert bekci.eslesme(["python3", "-m", "syspano", "--bekci"]) is False
    assert bekci.eslesme(["python3", "-m", "syspano.tepsi"]) is False
    assert bekci.eslesme(["python3", "/usr/lib/syspano/tepsi.py"]) is False
    assert bekci.eslesme(["bash", "-c", "echo syspano"]) is False
    assert bekci.eslesme([]) is False


def test_kalp_yasi():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_RUNTIME_DIR"] = d
        try:
            assert bekci.kalp_yasi() is None                  # dosya yok
            yol = bekci.kalp_yolu()
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            with open(yol, "w") as f:
                f.write("{}")
            os.utime(yol, (time.time() - 120, time.time() - 120))
            yas = bekci.kalp_yasi()
            assert 115 < yas < 130, yas
            assert bekci.karar(True, yas, 90) == "oldur"
        finally:
            del os.environ["XDG_RUNTIME_DIR"]


def test_gunluk_yolu_kalici_dizinde():
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        try:
            yol = bekci.gunluk_yolu()
            assert yol.startswith(d) and yol.endswith("pano.log"), yol
            bekci._log("deneme satırı")
            with open(yol) as f:
                assert "deneme satırı" in f.read()
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_dongu_kuru_calistirma_bir_tur():
    """Kuru çalıştırma hiçbir şeyi başlatmaz; kararını döndürür."""
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        os.environ["XDG_RUNTIME_DIR"] = d
        try:
            karar = bekci.dongu(kuru=True, tur_sayisi=1)
            assert karar in ("baslat", "bekle", "oldur"), karar
            with open(bekci.gunluk_yolu()) as f:
                icerik = f.read()
            assert "bekçi:" in icerik, icerik
            if karar == "baslat":
                assert "başlatılmadı" in icerik
        finally:
            del os.environ["XDG_STATE_HOME"], os.environ["XDG_RUNTIME_DIR"]


def test_olur_zararsiz_sureci_sonlandirir():
    """Donmuş pano yerine zararsız bir süreç: SIGTERM ile kapanmalı."""
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_STATE_HOME"] = d
        try:
            surec = subprocess.Popen(["sleep", "30"])
            try:
                assert bekci.oldur(surec.pid, zaman_asimi=3) is True
                time.sleep(0.3)
                assert surec.poll() is not None, "süreç kapanmadı"
            finally:
                if surec.poll() is None:
                    surec.kill()
        finally:
            del os.environ["XDG_STATE_HOME"]


def test_tani_metni_okunur():
    parca = bekci.tani(os.getpid())
    assert "pid" in parca and "State:" in parca, parca


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
