"""Ayar ekranı yerleşim testleri.

Yerleşim saf bir fonksiyon olduğu için Tk gerekmez. Denetimlerin çakışmaması,
dokunma hedeflerinin yeterince büyük olması ve her ekran boyutunda içeriğin
hesaplanabilmesi sınanır.
"""

from syspano.arayuz import ayar_ekrani as A

AYARLAR = {
    "olcek": None, "tema": "koyu", "buyutec": "auto", "guncelleme_ms": 1000,
    "ekran": "auto", "kartlar": ["cpu", "bellek", "sistem"], "terminal": True,
    "tepsi": True, "otomatik_kart": True,
}

DURUM = {
    "kart_bilgi": {k: k.upper() for k in
                   ("cpu", "bellek", "sicaklik", "pil", "cekirdek", "gecmis",
                    "gpu", "disk_ag", "surecler", "yedek", "sistem")},
    "surum_metni": "SysPano 1.0.1 · güncel",
}

BOYUTLAR = [
    (1600, 900, "geniş pano"),
    (1200, 700, "orta pano"),
    (465, 320, "küçük pencere"),
    (575, 343, "Raspberry Pi 7\""),
    (720, 360, "mikro panel"),
    (300, 260, "çok küçük"),
    (2000, 1126, "1080p tasarım uzayı"),
]


class SahteCikis:
    def __init__(self, ad):
        self.ad = ad


def _denetim_dikdortgenleri(plan):
    """Tıklanabilir tüm dikdörtgenler: (rect, etiket)."""
    sonuc = []
    for k in plan["kutular"]:
        tur = k["tur"]
        if tur == "secenek":
            for _d, et, rect in k["secenekler"]:
                sonuc.append((rect, f"{k['id']}:{et}"))
        elif tur in ("anahtar", "kart_anahtar"):
            sonuc.append((k["anahtar"], k["id"]))
        elif tur == "kaydirici":
            for ad in ("eksi", "arti", "dokunma"):
                sonuc.append((k["parcalar"][ad], f"{k['id']}:{ad}"))
            if k["parcalar"].get("oto"):
                sonuc.append((k["parcalar"]["oto"], f"{k['id']}:oto"))
        elif tur == "dugme":
            sonuc.append((k["dugme"], k["id"]))
    return sonuc


def _cakismalar(plan):
    dikdortgenler = _denetim_dikdortgenleri(plan)
    cakisan = []
    for i in range(len(dikdortgenler)):
        (ax, ay, aw, ah), an = dikdortgenler[i]
        for j in range(i + 1, len(dikdortgenler)):
            (bx, by, bw, bh), bn = dikdortgenler[j]
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                cakisan.append((an, bn))
    return cakisan


def test_cakisma_yok():
    for tg, ty, ad in BOYUTLAR:
        plan = A.yerlesim(tg, ty, AYARLAR,
                          [SahteCikis("HDMI-A-1"), SahteCikis("DSI-1")], DURUM)
        cakisan = _cakismalar(plan)
        assert not cakisan, f"{ad} ({tg}x{ty}): {cakisan[:4]}"


def test_dokunma_hedefleri():
    """Her denetim en az DOKUNMA kadar yüksek olmalı (parmakla basılabilir)."""
    for tg, ty, ad in BOYUTLAR:
        if tg < 300:
            continue
        plan = A.yerlesim(tg, ty, AYARLAR, [], DURUM)
        for rect, etiket in _denetim_dikdortgenleri(plan):
            _x, _y, w, h = rect
            assert h >= 28, f"{ad}: {etiket} yüksekliği {h:.0f} < 28"
            assert w >= 20, f"{ad}: {etiket} genişliği {w:.0f} < 20"


def test_icerik_ekran_icinde():
    """Kutular içerik genişliğini aşmamalı; içerik yüksekliği makul olmalı."""
    for tg, ty, ad in BOYUTLAR:
        plan = A.yerlesim(tg, ty, AYARLAR, [], DURUM)
        for k in plan["kutular"]:
            assert k["x"] >= -1 and k["x"] + k["w"] <= tg + 1, \
                f"{ad}: {k['id']} yatay taşma"
        assert plan["icerik_y"] > 0
        assert plan["icerik_y"] < 4000


def test_olcek_kaydiricisi_iki_ucta():
    """Çubuğun sol ucu en küçük, sağ ucu en büyük değeri vermeli."""
    plan = A.yerlesim(1600, 900, AYARLAR, [], DURUM)
    k = next(x for x in plan["kutular"] if x["id"] == "olcek")
    bx, _by, bw, _bh = k["parcalar"]["cubuk"]
    assert A._kaydirici_deger(k, bx) == k["alt"]
    assert A._kaydirici_deger(k, bx + bw) == k["ust"]
    orta = A._kaydirici_deger(k, bx + bw / 2)
    assert k["alt"] < orta < k["ust"]


def test_isabet_tiklama():
    """Bir seçeneğin ortasına dokunmak o seçeneği döndürmeli."""
    plan = A.yerlesim(1600, 900, AYARLAR, [], DURUM)
    k = next(x for x in plan["kutular"] if x["id"] == "tema")
    for deger, _et, (bx, by, bw, bh) in k["secenekler"]:
        isaret = A.isabet(plan, bx + bw / 2, by + bh / 2)
        assert isaret and isaret[0] == "tema" and isaret[2] == deger, isaret


def test_isabet_anahtar():
    plan = A.yerlesim(1600, 900, AYARLAR, [], DURUM)
    k = next(x for x in plan["kutular"] if x["id"] == "terminal")
    ax, ay, aw, ah = k["anahtar"]
    isaret = A.isabet(plan, ax + aw / 2, ay + ah / 2)
    assert isaret == ("terminal", "anahtar", not k["deger"]), isaret


def test_isabet_kart_anahtari():
    plan = A.yerlesim(1600, 900, AYARLAR, [], DURUM)
    hedef = [x for x in plan["kutular"] if x["id"] == "kart:cpu"][0]
    ax, ay, aw, ah = hedef["anahtar"]
    isaret = A.isabet(plan, ax + 2, ay + ah / 2)
    assert isaret and isaret[0] == "kart:cpu" and isaret[1] == "anahtar", isaret


def test_isabet_bos_yer():
    plan = A.yerlesim(1600, 900, AYARLAR, [], DURUM)
    assert A.isabet(plan, 5, 5) is None


def test_butun_ayar_anahtarlari_var():
    """Ayar ekranı beklenen denetimleri içermeli."""
    plan = A.yerlesim(1600, 900, AYARLAR, [SahteCikis("DSI-1")], DURUM)
    idler = {k.get("id") for k in plan["kutular"]} | {k.get("oto_id") for k in plan["kutular"]}
    for beklenen in ("olcek", "olcek_oto", "tema", "buyutec", "aralik", "ekran",
                     "terminal", "tepsi", "otomatik_kart", "guncelle_denetle",
                     "guncelle_uygula", "yeniden_baslat", "sifirla", "kapat"):
        assert beklenen in idler, f"{beklenen} yok"
    assert "kart:cpu" in idler


def test_ekran_secenekleri():
    plan = A.yerlesim(1600, 900, AYARLAR,
                      [SahteCikis("HDMI-A-1"), SahteCikis("DSI-1")], DURUM)
    k = next(x for x in plan["kutular"] if x["id"] == "ekran")
    degerler = [d for d, _e, _r in k["secenekler"]]
    assert "auto" in degerler and "tumu" in degerler
    assert "HDMI-A-1" in degerler and "DSI-1" in degerler


# ─── çizim testleri (Tk gerekir) ─────────────────────────────────────────────
def _cekim_hazirla(olcek=2.0, g=1400, y=1600):
    """Gizli bir tuval ve Cekim döndürür; görüntü yoksa None."""
    import tkinter as tk
    from syspano.arayuz.cekim import Cekim
    from syspano.arayuz import tema
    try:
        kok = tk.Tk()
    except Exception:
        print("    (görüntü yok — atlandı)")
        return None, None, None
    kok.withdraw()
    cv = tk.Canvas(kok, width=g, height=y)
    cek = Cekim(cv, olcek, tema.tema_sec("koyu"), tema.yazi_ailesi(kok))
    return kok, cv, cek


def _sinirlar(cv):
    kutular = [cv.bbox(o) for o in cv.find_all()]
    kutular = [k for k in kutular if k]
    return (min(k[0] for k in kutular), min(k[1] for k in kutular),
            max(k[2] for k in kutular), max(k[3] for k in kutular))


def test_anahtar_olcege_uyar():
    """Anahtar tasarım dikdörtgeninin tam üstüne, ölçeklenmiş olarak çizilmeli.

    Ham `create_oval` çağrıları ölçeği atlar (bir dönem anahtarın kapakları
    yanlış yere düşüyordu); bu test onu yakalar.
    """
    kok, cv, cek = _cekim_hazirla(olcek=2.0)
    if cek is None:
        return
    try:
        S = cek.S
        rect = (100.0, 50.0, 58.0, 32.0)
        A._anahtar_ciz(cek, rect, True)
        x0, y0, x1, y1 = _sinirlar(cv)
        assert abs(x0 - rect[0] * S) <= 3, f"sol {x0} ≠ {rect[0] * S}"
        assert abs(y0 - rect[1] * S) <= 3, f"üst {y0} ≠ {rect[1] * S}"
        assert abs(x1 - (rect[0] + rect[2]) * S) <= 3, f"sağ {x1}"
        assert abs(y1 - (rect[1] + rect[3]) * S) <= 3, f"alt {y1}"
    finally:
        kok.destroy()


def test_guncelleme_durumu_gorunur():
    """SÜRÜM kutusu, güncelleme durumunu renkli satır olarak göstermeli."""
    durum = dict(DURUM)
    durum["guncelleme"] = {"metin": "✓ Güncel · son denetim az önce", "renk": "yesil"}
    plan = A.yerlesim(1200, 700, AYARLAR, [], durum)
    durum_kutulari = [k for k in plan["kutular"] if k["tur"] == "durum"]
    assert durum_kutulari, "güncelleme durumu satırı yok"
    k = durum_kutulari[0]
    assert k["etiket"] == "✓ Güncel · son denetim az önce"
    assert k["renk"] == "yesil"
    assert k["h"] >= 18, "durum satırı çok ince"
    # durum yoksa satır da olmamalı (boş satır bırakmasın)
    plan2 = A.yerlesim(1200, 700, AYARLAR, [], DURUM)
    assert not [k for k in plan2["kutular"] if k["tur"] == "durum"]
    # durum satırı içeriği aşağı itmeli (plan yüksekliği artar)
    assert plan["icerik_y"] > plan2["icerik_y"]


def test_olcek_kirpildiginda_uyarir():
    """Küçük ekranda istenen ölçek uygulanamıyorsa ayar ekranı bunu söylemeli."""
    ayarlar = dict(AYARLAR, olcek=2.8)
    durum = dict(DURUM, olcek_istenen=2.8, olcek_etkin=1.5)
    plan = A.yerlesim(575, 343, ayarlar, [], durum)
    metinler = [k["etiket"] for k in plan["kutular"] if k["tur"] == "aciklama"]
    assert any("en fazla 1.50" in m for m in metinler), metinler
    # kırpma yoksa uyarı da olmamalı
    durum2 = dict(DURUM, olcek_istenen=2.8, olcek_etkin=2.8)
    plan2 = A.yerlesim(2000, 1126, ayarlar, [], durum2)
    metinler2 = [k["etiket"] for k in plan2["kutular"] if k["tur"] == "aciklama"]
    assert not any("en fazla" in m for m in metinler2), metinler2


def test_cizim_icerik_icinde():
    """Tüm ayar ekranı, ölçekli içerik alanının dışına taşmamalı."""
    kok, cv, cek = _cekim_hazirla(olcek=1.7)
    if cek is None:
        return
    try:
        S = cek.S
        tasarim_g, tasarim_y = 1000, 700
        plan = A.yerlesim(tasarim_g, tasarim_y, AYARLAR, [], DURUM)
        A.ciz(cek, plan)
        x0, y0, x1, y1 = _sinirlar(cv)
        assert x0 >= -4, f"sol taşma {x0}"
        assert y0 >= -4, f"üst taşma {y0}"
        assert x1 <= tasarim_g * S + 6, f"sağ taşma {x1} > {tasarim_g * S}"
        assert y1 <= plan["icerik_y"] * S + 8, f"alt taşma {y1}"
    finally:
        kok.destroy()


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
