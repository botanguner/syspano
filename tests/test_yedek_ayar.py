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


def test_durum_yoksa_bolum_gizli():
    """Kurulu değilse boş döner: ayar ekranı YEDEKLEME bölümünü çizmez."""
    with tempfile.TemporaryDirectory() as d:
        satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/yok.json"})
    assert satirlar == [] and eylemler == [], (satirlar, eylemler)


def test_sorgu_activating_durumunu_suruyor_sayar():
    """`systemctl is-active` bir oneshot çalışırken 'activating' döner."""
    gercek = yedek._calistir
    yedek._calistir = lambda k, z=10: (0, "activating")
    yedek._onbellek.update({"zaman": 0.0, "sonuc": {}})
    try:
        s = yedek._sorgu("yedek.timer")
    finally:
        yedek._calistir = gercek
        yedek._onbellek.update({"zaman": 0.0, "sonuc": {}})
    assert s["calisiyor"] is True and s["zamanlayici_etkin"] is True, s


def test_sorgu_inactive_suruyor_saymaz():
    gercek = yedek._calistir
    yedek._calistir = lambda k, z=10: (3, "inactive")
    yedek._onbellek.update({"zaman": 0.0, "sonuc": {}})
    try:
        s = yedek._sorgu("yedek.timer")
    finally:
        yedek._calistir = gercek
        yedek._onbellek.update({"zaman": 0.0, "sonuc": {}})
    assert s == {"zamanlayici_etkin": False, "calisiyor": False}, s


def test_dosya_surerken_dese_suruyor_ve_dugme_yok():
    """systemctl henüz 'active' demese bile durum dosyası 'calisiyor' diyorsa
    bölüm 'başarılı' göstermemeli ve ikinci yedek düğmesi çıkmamalı."""
    with tempfile.TemporaryDirectory() as d:
        _durum_dosyasi(d, {"durum": "calisiyor", "sonuc": 0,
                           "baslangic": time.time() - 1200, "yuklenen": 169})
        gercek = yedek._sorgu
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(etkin=True, calisiyor=False)
        try:
            satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
    assert "sürüyor" in satirlar[0][0] and satirlar[0][1] == "mavi", satirlar
    assert "20 dk" in satirlar[0][0] and "169 dosya" in satirlar[0][0], satirlar
    assert "yedek_simdi" not in eylemler, eylemler


def test_bozuk_dosyada_hata_ve_dugme():
    with tempfile.TemporaryDirectory() as d:
        yol = os.path.join(d, "durum.json")
        with open(yol, "w") as f:
            f.write("{bozuk json")
        satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": yol})
    assert "okunamadı" in satirlar[0][0] and satirlar[0][1] == "kirmizi", satirlar
    assert eylemler == ["yedek_simdi"], eylemler


def test_yarida_kalmis_kayit_bayat_sayilir():
    """Yedek sürerken makine kapanırsa durum dosyası 'calisiyor' kalır: bu kayıt
    sonsuza kadar 'sürüyor' göstermemeli, 'Şimdi yedekle' geri gelmeli."""
    with tempfile.TemporaryDirectory() as d:
        _durum_dosyasi(d, {"durum": "calisiyor", "sonuc": 0,
                           "baslangic": time.time() - 5 * 3600})
        gercek = yedek._sorgu
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(etkin=True, calisiyor=False)
        try:
            satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
    assert "yarıda kalmış" in satirlar[0][0] and satirlar[0][1] == "sari", satirlar
    assert "yedek_simdi" in eylemler, eylemler


def test_uzun_suren_yedek_hala_suruyor():
    """Birim gerçekten çalışıyorsa süre uzun da olsa bayat sayılmaz."""
    with tempfile.TemporaryDirectory() as d:
        _durum_dosyasi(d, {"durum": "calisiyor", "sonuc": 0,
                           "baslangic": time.time() - 5 * 3600})
        gercek = yedek._sorgu
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(etkin=True, calisiyor=True)
        try:
            satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
    assert "sürüyor" in satirlar[0][0], satirlar
    assert "yedek_simdi" not in eylemler, eylemler


def test_bozuk_sayilar_cokme_yaratmaz():
    """Durum dosyası bozuk sayı içerse de bölüm çizilebilmeli."""
    with tempfile.TemporaryDirectory() as d:
        _durum_dosyasi(d, {"durum": "basarili", "sonuc": 0, "baslangic": "bozuk",
                           "yuklenen": "N/A", "toplam_bayt": "yok"})
        gercek = yedek._sorgu
        yedek._sorgu = lambda z, taze=False: _sahte_sorgu(etkin=False)
        try:
            satirlar, eylemler = yedek.durum_metni({"yedek_durum_yolu": f"{d}/durum.json"})
        finally:
            yedek._sorgu = gercek
    assert satirlar and "başarılı" in satirlar[0][0], satirlar
    assert "zamanlayici_ac" in eylemler, eylemler


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
