"""Geometri yardımcıları testleri (Tk gerekmez).

Özellikle `parca_kirp`: çemberi hiç kesmeyen bir doğru parçası için parçanın
tamamını döndürmemeli (aksi hâlde büyüteç açıkken daire dışına taşan çizgiler
çizilirdi).
"""

from syspano.arayuz import cekim as C


def test_parca_kirp_icerde():
    # tamamen içeride → parça olduğu gibi döner
    assert C.parca_kirp(-10, -10, 10, 10, 0, 0, 100) == (-10.0, -10.0, 10.0, 10.0)


def test_parca_kirp_kesen():
    # çemberin içinden geçen → uçları kırpılır
    k = C.parca_kirp(-200, 0, 200, 0, 0, 0, 100)
    assert k is not None
    assert round(k[0], 3) == -100.0 and round(k[2], 3) == 100.0


def test_parca_kirp_tamamen_disarda():
    # uzantısı çemberi kesmeyen dış parça → None (eski hata: tamamı dönüyordu)
    assert C.parca_kirp(300, 300, 500, 500, 0, 0, 100) is None
    assert C.parca_kirp(200, -1, 200, 1, 0, 0, 100) is None
    assert C.parca_kirp(-120, 0, 120, 0, 0, 300, 100) is None


def test_parca_kirp_dogrunun_uzantisi_kesiyor_parca_gormuyor():
    # doğru çemberi kesiyor ama parça dışarıda → None
    assert C.parca_kirp(150, -1, 150, 1, 0, 0, 100) is None


def test_cokgen_kirp_kare():
    # kareyi çembere kırp: alan küçülmeli, en az 3 nokta kalmalı
    kenarlar = C.cember_kenarlari(0, 0, 50, 24)
    noktalar = C.cokgen_kirp([(-40, -40), (40, -40), (40, 40), (-40, 40)], kenarlar, 0, 0)
    assert len(noktalar) >= 3
    assert all(x * x + y * y <= 50 * 50 + 1e-6 for x, y in noktalar)


def test_cokgen_kirp_disarda():
    # çemberin tamamen dışındaki kare → boş
    kenarlar = C.cember_kenarlari(0, 0, 50, 24)
    assert C.cokgen_kirp([(200, 200), (300, 200), (300, 300)], kenarlar, 0, 0) == []


def test_cember_kenarlari_kapali():
    kenarlar = C.cember_kenarlari(0, 0, 10, 8)
    assert len(kenarlar) == 8
    # her kenarın bitişi bir sonrakinin başlangıcı
    for i in range(len(kenarlar)):
        sonraki = kenarlar[(i + 1) % len(kenarlar)]
        assert abs(kenarlar[i][2] - sonraki[0]) < 1e-9
        assert abs(kenarlar[i][3] - sonraki[1]) < 1e-9


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
