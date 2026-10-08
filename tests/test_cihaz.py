"""Cihaz toplayıcılarının duman testi.

Gerçek donanımı okur; bu yüzden iddialar esnektir (değer aralığı ve yapı
denetlenir). Amaç: hiçbir toplayıcının çökmemesi ve her kartın arayüzün
beklediği alanları üretmesi.
"""

import time

from syspano.toplayici import Toplayici


def _veri():
    t = Toplayici({"guncelleme_ms": 300})
    t.topla()
    time.sleep(1.1)
    t.topla()
    time.sleep(1.1)
    t.topla()
    return t.al()


def test_hicbir_toplayici_cokmuyor():
    v = _veri()
    for anahtar in ("sistem", "cpu", "bellek", "sicaklik", "pil", "gpu", "disk",
                    "ag", "surecler", "guc", "yedek"):
        assert anahtar in v, f"{anahtar} yok"
        assert isinstance(v[anahtar], dict), f"{anahtar} sözlük değil"
        # Toplayici bir hata yakalarsa sözlük yalnızca {"hata": ...} olur;
        # bazı kartların (yedek) kendi verisinde de "hata" alanı bulunabilir.
        assert not (len(v[anahtar]) == 1 and "hata" in v[anahtar]), \
            f"{anahtar} hata verdi: {v[anahtar].get('hata')}"


def test_cpu_ve_bellek_degerleri():
    v = _veri()
    cpu = v["cpu"]
    if not cpu.get("yok"):
        assert 0 <= cpu["yuzde"] <= 100
        assert cpu["cekirdek_sayisi"] >= 1
        assert len(cpu["cekirdek"]) == cpu["cekirdek_sayisi"]
    bel = v["bellek"]
    if not bel.get("yok"):
        assert bel["toplam"] > 0
        assert 0 <= bel["yuzde"] <= 100


def test_pil_structure():
    v = _veri()["pil"]
    assert "yok" in v or ("yuzde" in v and "durum" in v and "ac" in v)


def test_gpu_yapisi():
    g = _veri()["gpu"]
    assert "kartlar" in g
    assert isinstance(g["kartlar"], list)
    for k in g["kartlar"]:
        assert "model" in k and "kullanim" in k


def test_ag_ve_disk():
    v = _veri()
    a = v["ag"]
    if not a.get("yok"):
        assert a["inen"] >= 0 and a["giden"] >= 0
        assert "ip" in a
    d = v["disk"]
    if not d.get("yok"):
        assert 0 <= d["dolu"] <= 100
        assert d["okuma"] >= 0 and d["yazma"] >= 0


def test_yardimci_bicimler():
    from syspano.cihaz.ortak import boyut_metni, sure_metni
    assert boyut_metni(0) == "0 B"
    assert boyut_metni(1536).endswith("KiB")
    assert boyut_metni(2 * 1024 ** 3).endswith("GiB")
    assert sure_metni(10) == "az önce"
    assert "dk" in sure_metni(600)
    assert "saat" in sure_metni(7200)


if __name__ == "__main__":
    import traceback
    gecen = kalan = 0
    for ad, fonk in sorted(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            try:
                fonk(); print(f"  ✓ {ad}"); gecen += 1
            except Exception:
                print(f"  ✗ {ad}"); traceback.print_exc(); kalan += 1
    print(f"\n{gecen} geçti, {kalan} kaldı")
    raise SystemExit(1 if kalan else 0)
