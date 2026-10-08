"""Ekran çıktılarını ve geometrisini algılar.

Amaç: hangi monitörde olursak olalım (masaüstü, dizüstü, ikincil küçük ekran,
Raspberry Pi dokunmatik panel) hedef ekranı bulmak ve Tk penceresini oraya
yerleştirmek için piksel koordinatlarını bilmek.

Tkinter X11/Xwayland kullandığı için bakılacak uzay xrandr'ın uzayıdır: sanal
ekran tüm monitörleri kapsar ve her çıkışın kendi konumu vardır. KDE gibi
ortamlarda fiziksel piksel ölçeği farklı olabilir; bu yüzden DPI hesabında
xrandr'ın milimetre bilgisi kullanılır.
"""

import re

from . import ortam


# ─── çıkış modeli ────────────────────────────────────────────────────────────
class Cikis:
    def __init__(self, ad, x, y, g, y_):
        self.ad = ad
        self.x, self.y = int(x), int(y)
        self.g, self.yuk = int(g), int(y_)      # genişlik, yükseklik (X11 pikseli)
        self.birincil = False
        self.mm_g = self.mm_y = 0
        self.bagli = True
        # KWin'in mantıksal uzayı (kscreen-doctor). KWin betiği geometriyi bu
        # uzayda bekler; X11 uzayı kesirli ölçeklemede farklıdır (ör. 1,35×).
        self.kk = None                          # (x, y, w, h)

    @property
    def kwin_geom(self):
        """KWin için geometri: mantıksal varsa o, yoksa X11 değerleri."""
        return self.kk or (self.x, self.y, self.g, self.yuk)

    @property
    def tk_geom(self):
        """Tk penceresi için geometri (X11/Xwayland uzayı)."""
        return (self.x, self.y, self.g, self.yuk)

    @property
    def alan(self):
        return self.g * self.yuk

    @property
    def dpi(self):
        """Köşegen mm'den yaklaşık inç başına piksel."""
        if self.mm_g > 20 and self.mm_y > 20:
            cap_mm = (self.mm_g ** 2 + self.mm_y ** 2) ** 0.5
            cap_px = (self.g ** 2 + self.yuk ** 2) ** 0.5
            if cap_mm > 0:
                return cap_px / (cap_mm / 25.4)
        return 0.0

    @property
    def oran(self):
        return self.g / self.yuk if self.yuk else 1.0

    def __repr__(self):
        return (f"Cikis({self.ad} {self.g}x{self.yuk}+{self.x}+{self.y} "
                f"mm={self.mm_g}x{self.mm_y} dpi={self.dpi:.0f} birincil={self.birincil})")


def _sayi(m):
    return int(m) if m is not None else 0


# ─── xrandr ──────────────────────────────────────────────────────────────────
def _xrandr():
    cikti = ortam.komut(["xrandr", "--query"])
    cikislar = []
    for satir in cikti.splitlines():
        m = re.match(r"^(\S+) connected(|\s+primary)\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", satir)
        if not m:
            continue
        ad, birincil, g, y, x, yy = m.groups()
        c = Cikis(ad, x, yy, g, y)
        c.birincil = bool(birincil.strip())
        mm = re.search(r"(\d+)mm\s*x\s*(\d+)mm", satir)
        if mm:
            c.mm_g, c.mm_y = int(mm.group(1)), int(mm.group(2))
        cikislar.append(c)
    return cikislar


# ─── wlr-randr (saf Wayland, labwc/sway) ─────────────────────────────────────
def _wlr_randr():
    if not ortam.komut_var("wlr-randr"):
        return []
    cikti = ortam.ansi_temizle(ortam.komut(["wlr-randr"]))
    cikislar, mevcut = [], None
    for satir in cikti.splitlines():
        if satir and not satir.startswith(" "):
            mevcut = Cikis(satir.strip(), 0, 0, 0, 1)
            cikislar.append(mevcut)
        elif mevcut is not None:
            m = re.search(r"(\d+)x(\d+)\s+px,\s+(\d+)x(\d+)\s+mm", satir)
            if m:
                mevcut.g, mevcut.yuk = int(m.group(1)), int(m.group(2))
                mevcut.mm_g, mevcut.mm_y = int(m.group(3)), int(m.group(4))
            p = re.search(r"Position:\s*(-?\d+),(-?\d+)", satir)
            if p:
                mevcut.x, mevcut.y = int(p.group(1)), int(p.group(2))
            if "Enabled: yes" in satir:
                mevcut.bagli = True
    return [c for c in cikislar if c.g > 0]


# ─── sway ────────────────────────────────────────────────────────────────────
def _sway():
    if not (ortam.komut_var("swaymsg") and __import__("os").environ.get("SWAYSOCK")):
        return []
    import json
    try:
        veri = json.loads(ortam.komut(["swaymsg", "-t", "get_outputs", "-r"]) or "[]")
    except Exception:
        return []
    cikislar = []
    for o in veri:
        if not o.get("active"):
            continue
        r = o.get("rect") or {}
        c = Cikis(o.get("name", "?"), r.get("x", 0), r.get("y", 0),
                  r.get("width", 0), r.get("height", 1))
        mm = o.get("physical")          # sway bazı sürümlerde vermez
        if isinstance(mm, dict):
            c.mm_g, c.mm_y = mm.get("width", 0), mm.get("height", 0)
        c.bagli = True
        cikislar.append(c)
    return cikislar


# ─── kscreen-doctor (KDE mantıksal uzay — DPI tamamlayıcısı) ─────────────────
def _kscreen():
    """{çıkış adı: (x, y, w, h)} — KWin'in mantıksal uzayı (kscreen-doctor).

    Burada `komut_var()` ile ön denetim yapılmaz: komut kurulu değilse
    `ortam.komut()` boş döner ve ayrıştırma zaten boş sözlük üretir. Böylece
    kscreen-doctor olmayan sistemlerde (GNOME, Xfce, Raspberry Pi OS) ve
    testlerde de aynı yol izlenir.
    """
    cikti = ortam.ansi_temizle(ortam.komut(["kscreen-doctor", "-o"]))
    sonuc = {}
    for blok in re.split(r"Output:\s*\d+\s+", cikti)[1:]:
        parcalar = blok.split()
        ad = parcalar[0] if parcalar else None
        m = re.search(r"Geometry:\s*(-?\d+),(-?\d+)\s+(\d+)x(\d+)", blok)
        if ad and m:
            sonuc[ad] = tuple(int(v) for v in m.groups())
    return sonuc


# ─── birleşik keşif ──────────────────────────────────────────────────────────
def cikislari_bul():
    """Bağlı ekran çıktılarını döndürür (en uygun kaynaktan)."""
    cikislar = _xrandr()
    if not cikislar:
        cikislar = _wlr_randr()
    if not cikislar:
        cikislar = _sway()
    # KWin mantıksal geometrisi varsa ekle (pencere yerleştirme bunu kullanır)
    ks = _kscreen()
    for c in cikislar:
        if c.ad in ks:
            c.kk = ks[c.ad]
    return cikislar


def sanal_ekran():
    """Tüm masaüstünü kaplayan sanal ekran (xrandr Screen satırı ya da birleşim)."""
    cikti = ortam.komut(["xrandr", "--query"])
    m = re.search(r"Screen \d+:.*current\s+(\d+)\s*x\s*(\d+)", cikti)
    if m:
        return int(m.group(1)), int(m.group(2))
    cikislar = cikislari_bul()
    if not cikislar:
        return 0, 0
    sag = max(c.x + c.g for c in cikislar)
    alt = max(c.y + c.yuk for c in cikislar)
    return sag, alt


def ekran_sec(secim, cikislar=None):
    """İstenen ekranı seçer.

    secim: "auto" | "ana" | "primary" | "tumu" | "all" | çıkış adı | sıra ("0","1")
    Dönen: Cikis ya da None (None → tüm masaüstü/sanal ekran kullanılacak).
    """
    cikislar = cikislar if cikislar is not None else cikislari_bul()
    if not cikislar:
        return None
    if secim in ("tumu", "all", "hepsi", None, ""):
        return None

    birincil = next((c for c in cikislar if c.birincil), None)
    if secim in ("auto", "otomatik"):
        # Tipik kullanım: ana ekranın yanındaki küçük ikincil panel
        digerleri = [c for c in cikislar if not c.birincil]
        if len(digerleri) == 1:
            return digerleri[0]
        if len(cikislar) == 1:
            return cikislar[0]
        # birden fazla ekran: en küçük olanı seç (pano için tipik hedef)
        if digerleri:
            return min(digerleri, key=lambda c: c.alan)
        return birincil or cikislar[0]
    if secim in ("ana", "birincil", "primary"):
        return birincil or cikislar[0]
    if isinstance(secim, int) or (isinstance(secim, str) and secim.isdigit()):
        i = int(secim)
        return cikislar[i] if 0 <= i < len(cikislar) else None
    icin = str(secim)
    for c in cikislar:
        if c.ad == icin:
            return c
    for c in cikislar:                 # kısmi eşleşme (HDMI-A-1 ↔ HDMI-1)
        if icin in c.ad or c.ad in icin:
            return c
    return None


def liste_metni(cikislar=None):
    """İnsan okunur ekran listesi (--liste-ekranlar çıktısı)."""
    cikislar = cikislar if cikislar is not None else cikislari_bul()
    if not cikislar:
        return "Ekran bulunamadı (xrandr/wlr-randr/swaymsg yok ya da DISPLAY tanımsız)."
    satirlar = []
    for i, c in enumerate(cikislar):
        etiket = "birincil" if c.birincil else "ikincil"
        dpi = f"{c.dpi:.0f} dpi" if c.dpi else "dpi ?"
        satirlar.append(
            f"  [{i}] {c.ad:<12} {c.g}x{c.yuk}+{c.x}+{c.y}  "
            f"{c.mm_g}x{c.mm_y}mm  {dpi}  ({etiket})")
    return "Ekranlar:\n" + "\n".join(satirlar)
