"""Yerleşim motoru testleri: her ekran boyutunda dikdörtgenler tutarlı mı?

Çalıştırma:  ./run.sh test    ya da    PYTHONPATH=src python3 -m pytest -q
Tk gerekmez (yerleşim saf Python'dur).
"""

from syspano.arayuz import yerlesim as Y

TUM_KARTLAR = list(Y.KART_BILGI)

# gerçek cihazlara karşılık gelen (tasarım_g, tasarım_y, açıklama) örnekleri
ORNEKLER = [
    (1600, 800, "21:10 geniş ekran"),
    (1920, 1080, "16:9 tam HD monitör"),
    (2000, 1125, "16:9 büyük, 1x ölçek"),
    (1113, 557, "ScreenPad 2160x1080 @1.94"),
    (720, 360, "ScreenPad 2160x1080 @3.0"),
    (575, 345, "Raspberry Pi 800x480 dokunmatik"),
    (480, 320, "küçük 3.5\" panel"),
    (1024, 600, "netbook 1024x600"),
    (1080, 1920, "dikey 9:16"),
    (800, 1280, "dikey 5:8"),
    (2560, 1080, "21:9 ultrawide"),
    (3840, 2160, "4K"),
    (320, 240, "çok küçük"),
    (1440, 900, "kareye yakın"),
]


def _kontrol(tg, ty, aciklama, otomatik=True):
    sonuc = Y.planla(tg, ty, TUM_KARTLAR, otomatik=otomatik)
    kartlar = sonuc["kartlar"]
    n = sonuc["sutun"]
    assert 1 <= n <= 4, f"{aciklama}: sütun sayısı {n}"
    assert kartlar, f"{aciklama}: hiç kart yok"

    # 1) dikdörtgenler ekran içinde mi?
    for ad, (x, y, w, h) in kartlar.items():
        assert x >= 0 and y >= 0, f"{aciklama}/{ad}: negatif konum {x},{y}"
        assert x + w <= tg + 0.5, f"{aciklama}/{ad}: sağa taşma {x + w} > {tg}"
        if not sonuc["kaydirilir"]:
            assert y + h <= ty + 0.5, f"{aciklama}/{ad}: alta taşma {y + h} > {ty}"

    # 2) aynı satırdaki kartlar çakışmasın
    satirlar = {}
    for ad, (x, y, w, h) in kartlar.items():
        satirlar.setdefault(round(y, 3), []).append((x, x + w))
    for y, araliklar in satirlar.items():
        araliklar.sort()
        for (_, b1), (a2, _) in zip(araliklar, araliklar[1:]):
            assert a2 >= b1 - 0.5, f"{aciklama}: satır {y} çakışma {araliklar}"

    # 3) sütun sınırı aşılmıyor mu?
    for y, araliklar in satirlar.items():
        assert len(araliklar) <= n, f"{aciklama}: satır {y} {len(araliklar)} kart > {n} sütun"

    # 4) verilen yüksekliği aşmıyor mu? (kaydırma yoksa tam sığmalı)
    if not sonuc["kaydirilir"]:
        assert sonuc["icerik_y"] <= ty + 0.5, \
            f"{aciklama}: içerik {sonuc['icerik_y']:.0f} > pencere {ty}"

    return sonuc


def test_tum_boyutlar():
    for tg, ty, aciklama in ORNEKLER:
        _kontrol(tg, ty, aciklama)
        _kontrol(tg, ty, aciklama, otomatik=False)


def test_yer_varsa_gizlenmez():
    """Geniş ve yüksek bir ekranda tüm kartlar görünmeli."""
    sonuc = _kontrol(2200, 1300, "geniş")
    assert len(sonuc["kartlar"]) == len(TUM_KARTLAR), sonuc["kartlar"].keys()
    assert not sonuc["kaydirilir"]


def test_gizleme_sinirli_ve_kaydirma_acik():
    """Yer darlığında en fazla AZAMI_GIZLEME kart gizlenir; yetmezse kaydırılır.

    Pi'de (533×320) 14 karttan 12'si gizleniyor ve kaydırma da kapalı kalıyordu
    → servisler kartının altı görünmüyor, kaydırılamıyordu (kullanıcı bildirdi).
    """
    for tg, ty, aciklama in ORNEKLER:
        s = Y.planla(tg, ty)
        assert len(s["gizli"]) <= Y.AZAMI_GIZLEME, \
            f"{aciklama}: {len(s['gizli'])} kart gizlendi"
        if s["gizli"]:
            assert not s["kaydirilir"], \
                f"{aciklama}: gizleme varken kaydırma da açık (gereksiz gizleme)"
    # küçük ekranda bütün kartlar kalır ve pano kaydırılabilir olur
    s = Y.planla(533, 320)
    assert len(s["kartlar"]) == len(Y.KART_BILGI), s["gizli"]
    assert s["kaydirilir"] and s["icerik_y"] > 320


def test_kucukte_kart_duser():
    """Küçük ekranda otomatik mod kart sayısını azaltmalı (ya da kaydırmalı)."""
    sonuc = _kontrol(480, 320, "küçük")
    assert len(sonuc["kartlar"]) <= len(TUM_KARTLAR)


def test_onemli_kartlar_her_zaman():
    """Küçük ekranda bile CPU ve bellek kartları kalmalı."""
    for tg, ty, aciklama in ORNEKLER:
        sonuc = Y.planla(tg, ty, TUM_KARTLAR)
        assert "cpu" in sonuc["kartlar"], f"{aciklama}: CPU kartı düştü"
        assert "bellek" in sonuc["kartlar"], f"{aciklama}: bellek kartı düştü"


def test_bos_liste():
    sonuc = Y.planla(1600, 800, [])
    assert sonuc["kartlar"], "boş liste varsayılana düşmeli"


if __name__ == "__main__":
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
    raise SystemExit(1 if kalan else 0)
