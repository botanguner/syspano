"""Raspberry Pi sağlığı testleri: throttle bit maskesi, voltaj/frekans, önbellek.

Saf fonksiyonlar (bit çözümleme, ayrıştırma) ve `oku()`nun `vcgencmd` çağrıları
taklit edilerek denenmesi. Görüntü (X11) gerekmez.
"""

from types import SimpleNamespace

from syspano.cihaz import pisaglik as P


def _durum():
    return SimpleNamespace(pi_sonuc=None, pi_zaman=0.0)


def test_throttle_bitleri():
    assert P.maske_ayristir("throttled=0x0") == 0
    assert P.maske_ayristir("throttled=0x50005") == 0x50005
    assert P.maske_ayristir("bozuk çıktı") is None

    normal = P.ayristir(0)
    assert normal["normal"] is True and not normal["simdi"] and not normal["gecmis"]
    assert normal["ham"] == "0x0"

    # şu an düşük voltaj (bit 0)
    simdi = P.ayristir(0x1)
    assert simdi["simdi_var"] and simdi["simdi"] == [("undervoltage", "düşük voltaj")]
    assert not simdi["gecmis_var"]

    # önyüklemeden beri kısılma (bit 18) — şu an sorun yok ama geçmişte var
    gecmis = P.ayristir(1 << 18)
    assert gecmis["simdi_var"] is False and gecmis["gecmis_var"] is True
    assert gecmis["gecmis"] == [("throttled", "kısılıyor")]
    assert gecmis["normal"] is False

    # hem şimdi hem geçmişte (gerçek dünya örneği: 0x50005)
    ikisi = P.ayristir(0x50005)
    assert len(ikisi["simdi"]) == 2 and len(ikisi["gecmis"]) == 2
    assert [a for a, _ in ikisi["simdi"]] == ["undervoltage", "throttled"]

    assert P.ayristir(None) == {"yok": True}


def test_gerilim_ve_frekans_ayristirma():
    assert P.gerilim("volt=0.8700V") == 0.87
    assert P.gerilim("volt=1.2V") == 1.2
    assert P.gerilim("çöp") is None
    assert abs(P.ghz("frequency(48)=1500345728") - 1.5) < 0.01
    assert P.ghz("frequency(48)=600000000") == 0.6
    assert P.ghz("") is None


def test_ok_vcgencmd_yoksa_yok():
    gercek = P.ortam_komut
    P.ortam_komut = lambda ad: None
    try:
        assert P.oku(_durum(), {}) == {"yok": True}
    finally:
        P.ortam_komut = gercek


def test_oku_degerleri_toplanir_ve_onbelleklenir():
    cagrilar = []

    def sahte_vcgencmd(*args):
        cagrilar.append(args)
        return {
            ("get_throttled",): "throttled=0x50000",
            ("measure_volts", "core"): "volt=0.8700V",
            ("measure_clock", "arm"): "frequency(48)=1500000000",
        }.get(args, "")

    gercek_komut, gercek_vc = P.ortam_komut, P._vcgencmd
    P.ortam_komut = lambda ad: "/usr/bin/vcgencmd"
    P._vcgencmd = sahte_vcgencmd
    try:
        d = _durum()
        ilk = P.oku(d, {})
        assert ilk["gecmis_var"] is True and ilk["simdi_var"] is False
        assert ilk["gerilim"] == 0.87 and ilk["ghz"] == 1.5
        assert len(cagrilar) == 3, cagrilar

        # önbellek: 5 saniye dolmadan yeniden çağrı yapılmamalı
        ikinci = P.oku(d, {})
        assert ikinci is d.pi_sonuc and len(cagrilar) == 3

        # süre dolunca tazelenir
        d.pi_zaman -= P.PI_ARALIK + 1
        P.oku(d, {})
        assert len(cagrilar) == 6, cagrilar
    finally:
        P.ortam_komut, P._vcgencmd = gercek_komut, gercek_vc


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
