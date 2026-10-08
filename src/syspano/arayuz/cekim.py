"""Canvas çizim yardımcıları: ölçek, kaydırma ve büyüteç dönüşümü.

Tüm çizim "tasarım birimi"nde yapılır; ekrana dönüştürme burada olur:

    ekran_x = v * S

Dikey kaydırma ve büyüteç (mercek) varsa araya bir dönüşüm girer:

    ekran_x = (v*S - odak_x) * zoom + merkez_x

Büyüteç açıkken her öğe daireye kırpılır (Sutherland–Hodgman); kırpma sayesinde
daire dışındaki öğeler hiç oluşturulmaz, bu da çizimi hızlı tutar.
"""

import math

from tkinter import font as tkfont


# ─── geometri yardımcıları (saf) ─────────────────────────────────────────────
def cember_kenarlari(cx, cy, yaricap, dilim=32):
    kenarlar = []
    for i in range(dilim):
        a1 = 2 * math.pi * i / dilim
        a2 = 2 * math.pi * (i + 1) / dilim
        kenarlar.append((cx + yaricap * math.cos(a1), cy + yaricap * math.sin(a1),
                         cx + yaricap * math.cos(a2), cy + yaricap * math.sin(a2)))
    return kenarlar


def _kenar_kesisim(p, q, ax, ay, nx, ny, yon):
    payda = yon * (nx * (q[0] - p[0]) + ny * (q[1] - p[1]))
    if abs(payda) < 1e-9:
        return q
    t = -(yon * (nx * (p[0] - ax) + ny * (p[1] - ay))) / payda
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))


def cokgen_kirp(noktalar, kenarlar, ic_x, ic_y):
    """Kapalı çokgeni dışbükey bölgeye kırpar (Sutherland–Hodgman)."""
    cikti = list(noktalar)
    for (ax, ay, bx, by) in kenarlar:
        if not cikti:
            return []
        nx, ny = (by - ay), -(bx - ax)
        yon = 1 if (nx * (ic_x - ax) + ny * (ic_y - ay)) >= 0 else -1
        girdi, cikti = cikti, []
        onceki = girdi[-1]
        onceki_ic = yon * (nx * (onceki[0] - ax) + ny * (onceki[1] - ay)) >= 0
        for simdiki in girdi:
            simdi_ic = yon * (nx * (simdiki[0] - ax) + ny * (simdiki[1] - ay)) >= 0
            if simdi_ic:
                if not onceki_ic:
                    cikti.append(_kenar_kesisim(onceki, simdiki, ax, ay, nx, ny, yon))
                cikti.append(simdiki)
            elif onceki_ic:
                cikti.append(_kenar_kesisim(onceki, simdiki, ax, ay, nx, ny, yon))
            onceki, onceki_ic = simdiki, simdi_ic
    return cikti


def parca_kirp(x1, y1, x2, y2, cx, cy, r):
    """Doğru parçasını çembere kırpar; görünmüyorsa None.

    Önemli: doğru çemberi hiç kesmiyorsa (parça tamamen dışarıda) None döner.
    Aksi hâlde büyüteç açıkken daire dışına taşan çizgiler çizilirdi.
    """
    dx, dy = x2 - x1, y2 - y1
    a = dx * dx + dy * dy
    if a < 1e-9:
        return (x1, y1, x2, y2) if (x1 - cx) ** 2 + (y1 - cy) ** 2 <= r * r else None
    fx, fy = x1 - cx, y1 - cy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    t0, t1 = 0.0, 1.0
    ayrim = b * b - 4 * a * c
    if ayrim > 0:
        kok = math.sqrt(ayrim)
        ta, tb = (-b - kok) / (2 * a), (-b + kok) / (2 * a)
        t0, t1 = max(t0, min(ta, tb)), min(t1, max(ta, tb))
    else:
        return None
    if t0 > t1:
        return None
    return (x1 + t0 * dx, y1 + t0 * dy, x1 + t1 * dx, y1 + t1 * dy)


# ─── çizim ───────────────────────────────────────────────────────────────────
class Cekim:
    """Bir Tk Canvas üzerine tasarım biriminde çizen yardımcı."""

    def __init__(self, canvas, olcek, renk, yazi_ailesi="TkFixedFont"):
        self.c = canvas
        self.S = olcek
        self.renk = renk
        self.yazi_ailesi = yazi_ailesi
        self.kaydir = 0.0                    # dikey kaydırma (ekran pikseli)
        self._donusum = (0.0, 0.0, 1.0, 0.0, 0.0)   # ox, oy, zoom, cx, cy
        self._kirp = None                    # (cx, cy, r, kenarlar)
        self._etiket = ""
        self._tipler = {}
        self.ekran_g = 1
        self.ekran_y = 1

    # ── dönüşüm ──
    def s(self, v):
        """Sabit ölçek (dönüşümden bağımsız)."""
        return v * self.S

    def sx(self, v):
        ox, _, z, cx, _ = self._donusum
        return (v * self.S - ox) * z + cx

    def sy(self, v):
        _, oy, z, _, cy = self._donusum
        return (v * self.S - self.kaydir - oy) * z + cy

    def sl(self, v):
        """Uzunluk (punto, çizgi kalınlığı) — konumdan bağımsız."""
        return v * self.S * self._donusum[2]

    def kaydir_ayarla(self, piksel):
        self.kaydir = piksel

    def _et(self):
        return (self._etiket,) if self._etiket else ()

    def _gorunur(self, x0, y0, x1, y1):
        if not self._kirp:
            return True
        cx, cy, r = self._kirp[0], self._kirp[1], self._kirp[2]
        return not (x1 < cx - r or x0 > cx + r or y1 < cy - r or y0 > cy + r)

    # ── temel şekiller ──
    def dik_ekran(self, x0, y0, x1, y1, dolgu, cerceve=""):
        if not self._gorunur(x0, y0, x1, y1):
            return
        if self._kirp:
            cx, cy, r2 = self._kirp[0], self._kirp[1], self._kirp[2] ** 2
            if (min(max(cx, x0), x1) - cx) ** 2 + (min(max(cy, y0), y1) - cy) ** 2 > r2:
                return
            if all((px - cx) ** 2 + (py - cy) ** 2 <= r2
                   for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
                self.c.create_rectangle(x0, y0, x1, y1, fill=dolgu, outline=cerceve,
                                        tags=self._et())
                return
            noktalar = cokgen_kirp([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                                   self._kirp[3], cx, cy)
            if len(noktalar) < 3:
                return
            self.c.create_polygon([k for p in noktalar for k in p], fill=dolgu,
                                  outline=cerceve or "", tags=self._et())
            return
        self.c.create_rectangle(x0, y0, x1, y1, fill=dolgu, outline=cerceve, tags=self._et())

    def dik(self, x0, y0, x1, y1, dolgu, cerceve=""):
        self.dik_ekran(self.sx(x0), self.sy(y0), self.sx(x1), self.sy(y1), dolgu, cerceve)

    def oval_ekran(self, x0, y0, x1, y1, dolgu="", cerceve="", kalinlik=1):
        self.c.create_oval(x0, y0, x1, y1, fill=dolgu, outline=cerceve,
                           width=kalinlik, tags=self._et())

    def oval(self, x0, y0, x1, y1, dolgu="", cerceve="", kalinlik=1):
        """Tasarım biriminde elips — dikdörtgen gibi ölçeklenir.

        (Ham `create_oval` tuval pikseli bekler; tasarım koordinatıyla
        çağrılırsa ölçek uygulanmaz ve daireler yanlış yere düşer.)
        """
        self.oval_ekran(self.sx(x0), self.sy(y0), self.sx(x1), self.sy(y1), dolgu,
                        cerceve, max(1, int(kalinlik * self.S * self._donusum[2])))

    def cokgen(self, noktalar, dolgu, stipple=""):
        xs = [p[0] for p in noktalar]
        ys = [p[1] for p in noktalar]
        if not self._gorunur(min(xs), min(ys), max(xs), max(ys)):
            return
        if self._kirp:
            cx, cy, r2 = self._kirp[0], self._kirp[1], self._kirp[2] ** 2
            if not all((p[0] - cx) ** 2 + (p[1] - cy) ** 2 <= r2 for p in noktalar):
                noktalar = cokgen_kirp(noktalar, self._kirp[3], cx, cy)
                if len(noktalar) < 3:
                    return
        self.c.create_polygon([k for p in noktalar for k in p], fill=dolgu,
                              outline="", stipple=stipple, tags=self._et())

    def cizgi(self, noktalar, renk, kalinlik):
        """Kırpılmış parçalar kesintisiz koşular hâlinde çizilir."""
        if not self._kirp:
            self.c.create_line([k for p in noktalar for k in p], fill=renk,
                               width=kalinlik, smooth=True, tags=self._et())
            return
        cx, cy, r = self._kirp[0], self._kirp[1], self._kirp[2]
        kosu = []
        for i in range(len(noktalar) - 1):
            k = parca_kirp(noktalar[i][0], noktalar[i][1],
                           noktalar[i + 1][0], noktalar[i + 1][1], cx, cy, r)
            if not k:
                if len(kosu) >= 2:
                    self.c.create_line([v for p in kosu for v in p], fill=renk,
                                       width=kalinlik, tags=self._et())
                kosu = []
                continue
            if not kosu:
                kosu = [(k[0], k[1])]
            kosu.append((k[2], k[3]))
        if len(kosu) >= 2:
            self.c.create_line([v for p in kosu for v in p], fill=renk,
                               width=kalinlik, tags=self._et())

    # ── yazı ──
    def _yazi_tipi(self, boyut, kalin):
        anahtar = (max(1, int(self.sl(boyut))), kalin)
        v = self._tipler.get(anahtar)
        if v is None:
            f = tkfont.Font(family=self.yazi_ailesi, size=-anahtar[0],
                            weight="bold" if kalin else "normal")
            v = (f, f.metrics("linespace"), f.measure("M") or 1)
            self._tipler[anahtar] = v
        return v

    @staticmethod
    def _metin_kirp(metin, cap, X, sol, sag, karakter_g):
        n = len(metin)
        if not n:
            return None
        gen = karakter_g * n
        if cap == "e":
            x0 = X - gen
        elif cap == "center":
            x0 = X - gen / 2.0
        else:
            x0 = X
        if x0 + gen <= sol or x0 >= sag:
            return None
        if x0 >= sol and x0 + gen <= sag:
            return X, metin
        bas = max(0, min(n, int(math.ceil((sol - x0) / karakter_g))))
        son = max(0, min(n, int((sag - x0) / karakter_g)))
        if son <= bas:
            return None
        metin = metin[bas:son]
        yeni_x0 = x0 + bas * karakter_g
        if cap == "e":
            return yeni_x0 + len(metin) * karakter_g, metin
        if cap == "center":
            return yeni_x0 + len(metin) * karakter_g / 2.0, metin
        return yeni_x0, metin

    def metin(self, x, y, metin, boyut=11, renk=None, kalin=False, cap="w"):
        if not metin:
            return
        renk = renk or self.renk["yazi"]
        X, Y = self.sx(x), self.sy(y)
        f, satir_yuk, karakter_g = self._yazi_tipi(boyut, kalin)
        if self._kirp:
            cx, cy, r = self._kirp[0], self._kirp[1], self._kirp[2]
            yuk = satir_yuk / 2.0
            dikey = max(abs(Y - yuk - cy), abs(Y + yuk - cy))
            if dikey >= r:
                return
            yari = math.sqrt(r * r - dikey * dikey)
            kirpik = self._metin_kirp(metin, cap, X, cx - yari, cx + yari, karakter_g)
            if kirpik is None:
                return
            X, metin = kirpik
        self.c.create_text(X, Y, text=metin, anchor=cap, fill=renk, font=f, tags=self._et())

    # ── bileşenler ──
    def kart(self, x, y, w, h, baslik=None, arka=None, kenar=None):
        self.dik(x, y, x + w, y + h, arka or self.renk["kart"],
                 kenar or self.renk["kenar"])
        if baslik:
            self.metin(x + 12, y + 15, baslik, 11, self.renk["soluk"], True, "w")

    def yazi(self, x, y, metin, boyut=11, renk=None, kalin=False, cap="w"):
        self.metin(x, y, metin, boyut, renk, kalin, cap)

    def bar(self, x, y, w, h, oran, renk, arka=None):
        self.dik(x, y, x + w, y + h, arka or self.renk["kenar"])
        if oran is None:
            return
        g = max(0.0, min(1.0, oran / 100.0)) * (self.sx(x + w) - self.sx(x))
        if g > 1:
            self.dik_ekran(self.sx(x), self.sy(y), self.sx(x) + g, self.sy(y + h), renk)

    def sparkline(self, x, y, w, h, degerler, renk, maks=None, dolgu=True):
        if len(degerler) < 2 or w <= 0 or h <= 0:
            return
        maks = maks or max(max(degerler), 1)
        x0, x1 = self.sx(x), self.sx(x + w)
        y0, y1 = self.sy(y), self.sy(y + h)
        if not self._gorunur(x0, y0, x1, y1):
            return
        adim = (x1 - x0) / (len(degerler) - 1)
        noktalar = [(x0 + i * adim, y1 - max(0.0, min(1.0, d / maks)) * (y1 - y0))
                    for i, d in enumerate(degerler)]
        if self._kirp:
            cx, r = self._kirp[0], self._kirp[2]
            i0 = max(0, int((cx - r - x0) / adim) - 1)
            i1 = min(len(noktalar), int((cx + r - x0) / adim) + 2)
            noktalar = noktalar[i0:i1]
            if len(noktalar) < 2:
                return
        if dolgu:
            self.cokgen([(noktalar[0][0], y1)] + noktalar + [(noktalar[-1][0], y1)],
                        renk, stipple="gray25")
        self.cizgi(noktalar, renk, max(1, int(self.sl(2))))

    # ── büyüteç ──
    def kirp_baslat(self, cx, cy, r, etiket="mercek"):
        self._etiket = etiket
        self._kirp = (cx, cy, r - 2, cember_kenarlari(cx, cy, r - 2))

    def kirp_bitir(self):
        self._etiket = ""
        self._kirp = None

    def zoom_baslat(self, odak_x, odak_y, zoom, merkez_x, merkez_y):
        self._donusum = (odak_x, odak_y, zoom, merkez_x, merkez_y)

    def zoom_bitir(self):
        self._donusum = (0.0, 0.0, 1.0, 0.0, 0.0)
