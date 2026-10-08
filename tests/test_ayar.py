"""Yapılandırma testleri: okuma, güncelleme ve varsayılanların dosyaya düşmemesi.

`guncelle` yalnızca değişen anahtarı yazar. Bu önemli: aksi hâlde ilk
çalıştırmada tüm varsayılanlar dosyaya yazılır ve `"buyutec": "auto"` gibi
akıllı bir varsayılan sabit bir değere dönüşürdü.
"""

import json
import os
import tempfile

from syspano import ayar


def _kutu():
    """Geçici yapılandırma dizini (ortam değişkeniyle yönlendirilir)."""
    return tempfile.TemporaryDirectory()


def test_guncelle_varsayilanlari_yazmaz():
    with _kutu() as d:
        os.environ["SYSPANO_YAPILANDIRMA_DIZINI"] = d
        try:
            ayar.guncelle({"terminal_yazi": 22})
            with open(ayar.yol()) as f:
                veri = json.load(f)
            assert veri == {"terminal_yazi": 22}, veri
            assert "buyutec" not in veri, "varsayılan dosyaya yazılmış"
            assert "ekran" not in veri
        finally:
            del os.environ["SYSPANO_YAPILANDIRMA_DIZINI"]


def test_guncelle_siler():
    with _kutu() as d:
        os.environ["SYSPANO_YAPILANDIRMA_DIZINI"] = d
        try:
            ayar.guncelle({"terminal_yazi": 30, "tema": "acik"})
            ayar.guncelle(sil=("terminal_yazi",))
            with open(ayar.yol()) as f:
                veri = json.load(f)
            assert "terminal_yazi" not in veri
            assert veri.get("tema") == "acik", "ilgisiz anahtar korunmalı"
        finally:
            del os.environ["SYSPANO_YAPILANDIRMA_DIZINI"]


def test_oku_varsayilanlarla_birlesir():
    with _kutu() as d:
        os.environ["SYSPANO_YAPILANDIRMA_DIZINI"] = d
        try:
            ayar.guncelle({"tema": "acik"})
            birlesik = ayar.oku()
            assert birlesik["tema"] == "acik"
            assert birlesik["buyutec"] == "auto", "varsayılan korunmalı"
            assert birlesik["ekran"] == "auto"
        finally:
            del os.environ["SYSPANO_YAPILANDIRMA_DIZINI"]


def test_satilan_yapilandirma_gecerli():
    """Yazılan dosya yeniden okunabilmeli (biçim bozulmamalı)."""
    with _kutu() as d:
        os.environ["SYSPANO_YAPILANDIRMA_DIZINI"] = d
        try:
            ayar.guncelle({"kartlar": ["cpu", "bellek"], "olcek": 1.25})
            yol = ayar.yol()
            assert os.path.exists(yol)
            with open(yol) as f:
                ham = f.read()
            assert json.loads(ham)["olcek"] == 1.25
            assert "cpu" in ham
        finally:
            del os.environ["SYSPANO_YAPILANDIRMA_DIZINI"]


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
