"""YEDEKLEME ayar bölümü testleri: durum satırları ve eylemler.

`systemctl` çağrıları taklit edilir; durum dosyası geçici dizinde yazılır.
Görüntü (X11) gerekmez.
"""

import json
import os
import tempfile
import time

from syspano.cihaz import yedek


def _durum_dosyasi(d, veri):
    yol = os.path.join(d, "durum.json")
    with open(yol, "w") as f:
        json.dump(veri, f)
    return yol


def _sahte_sorgu(zamanlayici=None, etkin=True, calisiyor=False):
    return {"zamanlayici_etkin": etkin, "calisiyor": calisiyor}


def test_durum_yoksa_kurulu_degil():
    with tempfile.TemporaryDirectory() as d:
        satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/yok.json"})
    assert "kurulu değil" in satirlar[0][0] and eylemler == [], (satirlar, eylemler)


def test_durum_basarili_ve_siradaki():
    with tempfile.TemporaryDirectory() as d:
        _durum_dosyasi(d, {"durum": "basarili", "baslangic": time.time() - 300,
                           "sonuc": 0, "yuklenen": 635, "toplam_bayt": 1_517_173_162})
        gercek = yedek._sorgu
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(calisiyor=False)
        try:
            satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
    assert "başarılı" in satirlar[0][0] and "635" in satirlar[0][0], satirlar
    assert satirlar[0][1] == "yesil"
    assert eylemler == ["yedek_simdi", "zamanlayici_kapat"], eylemler


def test_durum_surerken_ve_hatali():
    with tempfile.TemporaryDirectory() as d:
        _durum_dosyasi(d, {"sonuc": 0, "baslangic": time.time()})
        gercek = yedek._sorgu
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(calisiyor=True)
        try:
            satirlar, _ = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
        assert "sürüyor" in satirlar[0][0] and satirlar[0][1] == "mavi", satirlar

        _durum_dosyasi(d, {"sonuc": 1, "hata": "rclone: kota aşıldı"})
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(calisiyor=False)
        try:
            satirlar, _ = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
        assert "başarısız" in satirlar[0][0] and satirlar[0][1] == "kirmizi", satirlar


def test_zamanlayici_kapaliysa_uyari():
    with tempfile.TemporaryDirectory() as d:
        _durum_dosyasi(d, {"sonuc": 0, "baslangic": time.time()})
        gercek = yedek._sorgu
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(etkin=False)
        try:
            satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
    assert any("Zamanlayıcı kapalı" in s for s, _ in satirlar), satirlar
    assert "zamanlayici_ac" in eylemler, eylemler


def test_eylemler_no_block_ile():
    """Yedek dakikalarca sürer: `start` **--no-block** olmalı, yoksa pano donar."""
    cagrilar = []
    gercek = yedek._calistir
    yedek._calistir = lambda k, z=10: (cagrilar.append(list(k)), (0, ""))[1]
    try:
        assert yedek.eylem("yedek_simdi")[0] is True
        assert "--no-block" in cagrilar[-1], cagrilar[-1]
        assert yedek.eylem("zamanlayici_kapat")[0] is True
        assert "stop" in cagrilar[-1] and "yedek.timer" in cagrilar[-1]
        assert yedek.eylem("zamanlayici_ac")[0] is True
        assert "start" in cagrilar[-1] and "yedek.timer" in cagrilar[-1]
        assert yedek.eylem("yok-boyle")[0] is False
    finally:
        yedek._calistir = gercek


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
