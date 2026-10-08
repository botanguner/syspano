"""Komut satırı davranış testleri: kart listesi ekleme/çıkarma ve kalıcılık.

`--kart-ekle`/`--kart-cikar` **kalıcıdır** (yapılandırmaya yazılır); `--kartlar`
ise yalnızca o çalıştırma için geçerlidir. Pano başlatılmaz, görüntü gerekmez.
"""

import json
import os
import tempfile

from syspano import ayar
from syspano import cli
from syspano.arayuz.yerlesim import KART_BILGI


def test_kart_ekle_cikar_yerlesim_sirasinda():
    temel = {"kartlar": ["cpu", "bellek"]}
    yeni = cli._kart_uygula(temel, "loglar,sistem")
    assert yeni == [k for k in KART_BILGI if k in {"cpu", "bellek", "loglar", "sistem"}]
    # çıkarma
    yeni = cli._kart_uygula({"kartlar": list(KART_BILGI)}, cikar="gecmis,servisler")
    assert "gecmis" not in yeni and "servisler" not in yeni and "cpu" in yeni
    # bilinmeyen ad ve değişiklik yok → None
    assert cli._kart_uygula({"kartlar": ["cpu"]}, ekle="yok-boyle-kart") is None
    assert cli._kart_uygula({"kartlar": ["cpu"]}, ekle="cpu") is None
    # hepsini çıkarmaya çalışmak listeyi boşaltmaz
    assert cli._kart_uygula({"kartlar": ["cpu"]}, cikar="cpu") is None


def test_kart_listesi_kalicidir():
    """Kart listesi yapılandırmaya yazılmalı (eskiden sessizce kayboluyordu)."""
    with tempfile.TemporaryDirectory() as d:
        os.environ["SYSPANO_YAPILANDIRMA_DIZINI"] = d
        try:
            cli._kartlari_kaydet(["cpu", "loglar", "sistem"])
            with open(ayar.yol()) as f:
                veri = json.load(f)
            assert veri["kartlar"] == ["cpu", "loglar", "sistem"], veri
            # varsayılanlar dosyaya düşmemeli: yalnızca değişen anahtar yazılır
            assert set(veri) == {"kartlar"}, veri
        finally:
            del os.environ["SYSPANO_YAPILANDIRMA_DIZINI"]


def test_kartlar_secenegi_kalici_degil():
    """`--kartlar` yalnızca o çalıştırma için: yapılandırmaya yazılmaz."""
    with tempfile.TemporaryDirectory() as d:
        os.environ["SYSPANO_YAPILANDIRMA_DIZINI"] = d
        try:
            ayarlar = ayar.oku()
            ayarlar["kartlar"] = ["cpu", "bellek"]      # çalıştırma anındaki override
            assert not os.path.exists(ayar.yol()), "dosya yazılmamalı"
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
