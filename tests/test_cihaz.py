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


# ─── performans davranışları ─────────────────────────────────────────────────
def test_surecler_her_saniye_taranmaz():
    """`/proc` taraması pahalı; `ARALIK` içinde tekrar taranmamalı."""
    from syspano.cihaz import surecler
    d = Toplayici({"guncelleme_ms": 1000})
    sayac = {"n": 0}
    gercek = surecler._ornek

    def sayan():
        sayac["n"] += 1
        return gercek()

    surecler._ornek = sayan
    try:
        surecler.oku(d, {})
        ilk = sayac["n"]
        for _ in range(6):
            surecler.oku(d, {})
        assert sayac["n"] == ilk, "süreç listesi her ölçümde yeniden taranıyor"
        assert d.surec_sonuc.get("liste") is not None
    finally:
        surecler._ornek = gercek


def test_yavas_sensor_seyreltilir():
    """Okuması pahalı sensör (ör. NVMe ~9 ms) her ölçümde okunmamalı."""
    from syspano.cihaz import ortak as _ortak
    from syspano.cihaz import sicaklik as S
    okuma = {"n": 0}
    gercek = _ortak.oku_sayi

    def sayan(yol, varsayilan=None):
        okuma["n"] += 1
        return 45000.0

    _ortak.oku_sayi = sayan
    try:
        kayit = {"yol": "/sahte", "etiket": "nvme", "aralik": 10.0,
                 "deger": None, "zaman": 0.0, "maliyet": 9.0}
        t0 = 1000.0
        assert S._deger(kayit, t0) == 45000.0
        assert okuma["n"] == 1
        for i in range(1, 10):                    # aynı saniye içinde 9 ölçüm daha
            S._deger(kayit, t0 + i * 0.1)
        assert okuma["n"] == 1, "seyreltilen sensör her ölçümde okunuyor"
        S._deger(kayit, t0 + 11)                  # aralık doldu
        assert okuma["n"] == 2
    finally:
        _ortak.oku_sayi = gercek


def test_hizli_sensor_her_olcumde_okunur():
    """Ucuz sensör (coretemp ~0,04 ms) seyreltilmemeli."""
    from syspano.cihaz import ortak as _ortak
    from syspano.cihaz import sicaklik as S
    okuma = {"n": 0}
    gercek = _ortak.oku_sayi

    def sayan(yol, varsayilan=None):
        okuma["n"] += 1
        return 49000.0

    _ortak.oku_sayi = sayan
    try:
        kayit = {"yol": "/sahte", "etiket": None, "aralik": 0.0,
                 "deger": None, "zaman": 0.0, "maliyet": 0.04}
        for i in range(5):
            S._deger(kayit, 1000.0 + i)
        assert okuma["n"] == 5, "ucuz sensör seyreltilmiş"
    finally:
        _ortak.oku_sayi = gercek


def test_sicaklik_haritasi_tekrar_kurulmaz():
    """Sensör haritası her ölçümde yeniden taranmamalı."""
    from syspano.cihaz import sicaklik as S
    d = Toplayici({"guncelleme_ms": 1000})
    d.hwmon = {}
    S.oku(d, {})
    ilk = d.sicaklik_haritasi
    for _ in range(5):
        S.oku(d, {})
    assert d.sicaklik_haritasi is ilk, "sensör haritası her ölçümde yeniden kuruluyor"


def test_gpu_kart_listesi_onbelleklenir():
    """sysfs GPU kart taraması her saniye yapılmamalı."""
    from syspano.cihaz import gpu
    d = Toplayici({"guncelleme_ms": 1000})
    d.hwmon = {}
    sayac = {"n": 0}
    gercek = gpu._kart_bul

    def sayan():
        sayac["n"] += 1
        return gercek()

    gpu._kart_bul = sayan
    try:
        for _ in range(5):
            gpu.gpu_kartlari(d)
        assert sayac["n"] == 1, "GPU kart listesi her ölçümde yeniden taranıyor"
    finally:
        gpu._kart_bul = gercek


def test_which_onbelleklenir():
    from syspano.cihaz import gpu
    gpu._komut_onbellek.clear()
    assert gpu.ortam_komut("bu-komut-yok-12345") is False
    assert "bu-komut-yok-12345" in gpu._komut_onbellek


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
