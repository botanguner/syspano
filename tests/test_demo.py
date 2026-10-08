"""Demo verisi testleri: uydurma veriler gerçek cihazdan iz taşımamalı.

`syspano --demo` ekran görüntüsü almak ve arayüzü göstermek için kullanılır.
Bu testler, demo verisine yanlışlıkla gerçek bir değerin (makine adı, kullanıcı
adı, IP, çekirdek sürümü, yol) sızmadığını güvenceye alır.
"""

import json
import os

from syspano.demo import ORNEK_SISTEM, DemoToplayici

# Kartların beklediği anahtarlar (arayüz bunları okur)
BEKLENEN = {"sistem", "cpu", "bellek", "sicaklik", "pisaglik", "pil", "gpu",
            "disk", "ag", "surecler", "servisler", "loglar", "guc", "yedek"}


def _veri():
    return DemoToplayici({"guncelleme_ms": 1000}).al()


def test_arayuz_toplayici_ile_ayni():
    """Pano, gerçek toplayıcı yerine demo toplayıcıyı kullanabilmeli."""
    d = DemoToplayici({"guncelleme_ms": 2000})
    for ad in ("al", "dongu", "aralik"):
        assert hasattr(d, ad), f"{ad} eksik"
    assert d.aralik == 2.0
    assert isinstance(d.al(), dict)


def test_beklenen_anahtarlar():
    v = _veri()
    assert set(v) == BEKLENEN, f"eksik/fazla: {set(v) ^ BEKLENEN}"


def test_kartlarin_okudugu_alanlar():
    """Her kartın okuduğu alanlar bulunmalı (yanlış şekil çizim hatası verir)."""
    v = _veri()
    for ad in ("yuzde", "cekirdek", "ghz", "cekirdek_sayisi", "yuk"):
        assert ad in v["cpu"], f"cpu.{ad} yok"
    assert len(v["cpu"]["cekirdek"]) == v["cpu"]["cekirdek_sayisi"]
    for ad in ("toplam", "kullanilan", "yuzde", "swap_t", "swap_k", "takas_tur"):
        assert ad in v["bellek"], f"bellek.{ad} yok"
    for ad in ("paket", "cekirdek_maks", "fan", "ekstra", "sensor_var"):
        assert ad in v["sicaklik"], f"sicaklik.{ad} yok"
    for ad in ("yuzde", "durum", "ac", "guc", "saglik", "kalan_dk"):
        assert ad in v["pil"], f"pil.{ad} yok"
    assert v["gpu"]["kartlar"] and "kullanim" in v["gpu"]["kartlar"][0]
    for ad in ("okuma", "yazma", "dolu", "bos_gb", "model"):
        assert ad in v["disk"], f"disk.{ad} yok"
    for ad in ("arayuz", "ip", "inen", "giden", "tur"):
        assert ad in v["ag"], f"ag.{ad} yok"
    assert v["surecler"]["liste"] and len(v["surecler"]["liste"][0]) == 3
    for ad in ("ham", "simdi", "gecmis", "gerilim", "ghz"):
        assert ad in v["pisaglik"], f"pisaglik.{ad} yok"
    for ad in ("etiket", "yol", "boyut", "son", "okunabilir", "grup"):
        assert ad in v["loglar"]["kaynaklar"][0], f"loglar.{ad} yok"
    assert "pl1" in v["guc"] and "governor" in v["guc"]


def test_kisisel_bilgi_icermez():
    """Demo verisi bu makineden hiçbir gerçek değer taşımamalı."""
    metin = json.dumps(_veri(), ensure_ascii=False)
    yasak = [
        os.uname().nodename,                 # gerçek ana makine adı
        os.uname().release,                  # gerçek çekirdek sürümü
        os.environ.get("USER", "\x00"),      # kullanıcı adı
        os.environ.get("HOME", "\x00"),      # ev dizini
        "192.168.",                          # gerçek yerel ağ öneki
        "10.0.", "172.16.",
    ]
    for s in yasak:
        if len(s) < 3:
            continue
        assert s not in metin, f"demo verisinde gerçek değer var: {s!r}"
    # IP belgeleme için ayrılmış olmalı (RFC 5737)
    assert _veri()["ag"]["ip"].startswith("192.0.2.")


def test_demo_sistem_bilgisi_uydurma():
    v = _veri()["sistem"]
    assert v["ad"] == ORNEK_SISTEM["ad"] == "demo-pc"
    assert "Örnek" in v["makine"]
    assert "botan" not in json.dumps(v, ensure_ascii=False).lower()


def test_degerler_gecerli_aralikta():
    """Anlamsız değerler (negatif yüzde, 100 üstü, boş liste) olmamalı."""
    v = _veri()
    assert 0 <= v["cpu"]["yuzde"] <= 100
    assert all(0 <= c <= 100 for c in v["cpu"]["cekirdek"])
    assert 0 <= v["bellek"]["yuzde"] <= 100
    assert 0 <= v["pil"]["yuzde"] <= 100
    assert v["sicaklik"]["paket"] > 0
    assert v["disk"]["dolu"] <= 100
    assert len(v["surecler"]["liste"]) >= 5


def test_degerler_zamanla_degisir():
    """Grafikler boş görünmesin: değerler dalgalanmalı."""
    import time
    d = DemoToplayici({"guncelleme_ms": 1000})
    ilk = d.al()["cpu"]["yuzde"]
    time.sleep(2.5)
    assert abs(d.al()["cpu"]["yuzde"] - ilk) > 0.05, "demo verisi hiç değişmiyor"


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
