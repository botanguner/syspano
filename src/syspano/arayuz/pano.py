"""Ana pencere: çizim döngüsü, üst şerit, büyüteç, kaydırma ve terminal geçişi."""

import json
import os
import threading
import time

import tkinter as tk

from .. import ekran, ortam
from ..toplayici import Toplayici
from ..yerlestir import Yerlesimci
from . import kartlar, tema, yerlesim
from .cekim import Cekim
from .terminal import Terminal

UST = yerlesim.UST

# büyüteç (mercek)
MERCEK_YARICAP = 170
MERCEK_ZOOM = 2.6
MERCEK_UST_SINIR = 52
MERCEK_BEKLEME = 0.4
MERCEK_TOLERANS = 6

GECMIS_UZUNLUK = 240


class Pano:
    def __init__(self, ayar, cikis=None, mod=None, test=False, kwin=None):
        self.ayar = ayar
        self.baslik = ayar.get("uygulama_basligi", "SysPano")
        self.sinif = "syspano"
        self.test = test

        cikis = cikis if cikis is not None else ekran.ekran_sec(ayar.get("ekran", "auto"))
        self.cikis = cikis
        mod = mod or ayar.get("mod", "ekran")
        if mod not in ("ekran", "pencere", "tam-ekran"):
            mod = "ekran"
        self.mod = mod

        x, y, w, h = self._geometri(cikis, mod)
        self.ekran_g, self.ekran_y = w, h
        self.tk_geom = (x, y, w, h)
        self.kwin_geom = self._kwin_geometri(cikis, x, y, w, h)

        # ── ölçek: tasarım uzayı ~1600x800 kalsın diye çözünürlüğe göre ──
        taban = min(w / 1600.0, h / 800.0)
        carpan = float(ayar.get("olcek") or 1.0)
        self.S = max(0.85, min(3.0, taban * carpan))
        self.TG = int(round(w / self.S))     # tasarım genişliği
        self.TY = int(round(h / self.S))     # tasarım yüksekliği
        self.dpi = cikis.dpi if cikis else 0.0

        self.renk = tema.tema_sec(ayar.get("tema", "koyu"))

        # ── pencere ──
        self.kok = tk.Tk(className=self.sinif)
        self.kok.title(self.baslik)
        self.kok.configure(bg=self.renk["arka"])
        self._yerlesimci = None

        self.c = tk.Canvas(self.kok, width=w, height=h, bg=self.renk["arka"],
                           highlightthickness=0)
        self.c.pack()
        self.ck = Cekim(self.c, self.S, self.renk, tema.yazi_ailesi(self.kok))
        self.ck.ekran_g, self.ck.ekran_y = w, h

        # ── yerleşim ──
        self.aktif_kartlar = [k for k in (ayar.get("kartlar") or list(yerlesim.KART_BILGI))
                              if k in yerlesim.KART_BILGI]
        self.plan = yerlesim.planla(self.TG, self.TY, self.aktif_kartlar,
                                    otomatik=ayar.get("otomatik_kart", True))
        self.gizli_kartlar = self.plan.get("gizli", [])
        self.icerik_y = self.plan["icerik_y"]

        # ── durum ──
        self.gorunum = "pano"
        self.gorunur = True
        self.kaydir = 0.0
        self.terminal = None
        self.terminal_etkin = bool(ayar.get("terminal", True))
        self.terminal_yazi = int(ayar.get("terminal_yazi")
                                 or self._terminal_yazi_otomatik())
        self.bildiri = ""
        self.bildiri_zaman = 0.0
        self.baslangic = time.monotonic()
        self._basili = None

        # büyüteç
        self.buyutec = bool(ayar.get("buyutec", True))
        self.mercek = None
        self.mercek_yer = None
        self.mercek_zaman = 0.0
        self._fare_bas = None

        # geçmiş
        from collections import deque
        self.gecmis = {k: deque(maxlen=GECMIS_UZUNLUK) for k in
                       ("cpu", "bellek", "sicaklik", "pil", "gpu", "dgpu", "ag_in", "ag_out")}

        # tepsi ↔ pano iletişimi
        self.durum_dizin = ortam.emin_ol(ortam.durum_dizini())
        self.komut_yolu = os.path.join(self.durum_dizin, "komut")
        self.durum_yolu = os.path.join(self.durum_dizin, "durum.json")

        # ── toplayıcı ──
        self.t = Toplayici(ayar)
        threading.Thread(target=self.t.dongu, daemon=True).start()

        # ── olaylar ──
        self.c.bind("<Button-1>", self.tiklama)
        self.c.bind("<ButtonRelease-1>", self.birakma)
        self.c.bind("<B1-Motion>", self.surukle)
        self.c.bind("<Key>", self.tus)
        self.c.bind("<Motion>", self.fare)
        self.c.bind("<Leave>", self.fare_cikti)
        for tus in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.c.bind(tus, self.tekerlek)
        self.kok.bind("<Key>", self.tus)
        self.kok.protocol("WM_DELETE_WINDOW", self.kapat)
        for t in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.kok.bind(t, self.yazi_buyut); self.c.bind(t, self.yazi_buyut)
        for t in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.kok.bind(t, self.yazi_kucult); self.c.bind(t, self.yazi_kucult)
        for t in ("<Control-Key-0>", "<Control-KP_0>"):
            self.kok.bind(t, self.yazi_sifirla); self.c.bind(t, self.yazi_sifirla)

        # ── planlanan görevler ──
        if test:
            self.kok.after(9000, self.kapat)
        self.kok.after(150, self._yerlestir)
        self.kok.after(500, self._komut_isle)
        self.kok.after(1500, self._durum_yaz)
        self.kok.after(4000, self._gorev_cubugu_denetle)
        self.kok.after(600, self._mercek_denetle)
        self.ciz()

    # ── geometri ──
    def _geometri(self, cikis, mod):
        if mod == "pencere":
            pw, ph = self.ayar.get("pencere", [1280, 720])
            pw, ph = int(pw), int(ph)
            if cikis:
                x = cikis.x + max(0, (cikis.g - pw) // 2)
                y = cikis.y + max(0, (cikis.yuk - ph) // 2)
            else:
                x, y = 40, 40
            return x, y, pw, ph
        if cikis:
            return cikis.x, cikis.y, cikis.g, cikis.yuk
        sg, sy = ekran.sanal_ekran()          # tüm masaüstü
        return 0, 0, sg or 1280, sy or 720

    def _terminal_yazi_otomatik(self):
        """Yazı boyutu: ölçek ile DPI'ın büyüğünden; okunabilir aralığa sıkıştırılır."""
        dpi_orani = (self.dpi / 96.0) if self.dpi else 1.0
        return max(12, min(40, int(round(9 * max(self.S, dpi_orani)))))

    def _kwin_geometri(self, cikis, x, y, w, h):
        """Pencerenin KWin mantıksal uzayındaki dikdörtgeni.

        Kesirli ölçeklemede (ör. 1,35×) X11 uzayı ile KWin'in mantıksal uzayı
        farklıdır; KWin betiği geometriyi mantıksal uzayda bekler.
        """
        if not (cikis and cikis.kk) or not cikis.kk[2]:
            return (x, y, w, h)
        s = cikis.g / cikis.kk[2]              # X11 pikseli / mantıksal birim
        if s <= 0:
            return (x, y, w, h)
        return (int(round(cikis.kk[0] + (x - cikis.x) / s)),
                int(round(cikis.kk[1] + (y - cikis.y) / s)),
                int(round(w / s)), int(round(h / s)))

    # ── yerleştirme ──
    def _yerlestir(self):
        kwin = ortam.kwin_var()
        self._yerlesimci = Yerlesimci(
            self.kok, self.sinif, kwin=kwin, tk_geom=self.tk_geom,
            kwin_geom=self.kwin_geom,
            yonetilen=self.ayar.get("yonetilen_pencere"), baslik=self.baslik)
        self._yerlesimci.hazirla()
        self._yerlesimci.yerlestir(deneme=2)
        for gecikme, deneme in ((250, 1), (900, 2), (2600, 2)):
            self.kok.after(gecikme, lambda g=deneme: self._yerlesimci.yerlestir(deneme=g))
        self.kok.focus_force()
        self.c.focus_set()

    # ── düğmeler ──
    def dugme_yerleri(self, w):
        yerler = {}
        x = w - 14
        x -= 44
        yerler["kapat"] = (x, 5, 44, 36)
        if self.terminal_etkin:
            x -= 14 + 200
            yerler["terminal"] = (x, 5, 200, 36)
        x -= 14 + 176
        yerler["pano"] = (x, 5, 176, 36)
        return yerler

    # ── olaylar ──
    def tiklama(self, olay):
        self._fare_bas = (olay.x, olay.y)
        self._basili = None

    def surukle(self, olay):
        """Sürükleme: içerik kaydırılabilirse kaydırır (dokunmatik paneller için)."""
        if not self._kaydirilir() or self._fare_bas is None:
            return
        dy = olay.y - self._fare_bas[1]
        if self._basili is None:
            if abs(dy) <= 8:
                return
            self._basili = True
        self._kaydir_ayarla(self.kaydir - dy)
        self._fare_bas = (olay.x, olay.y)

    def birakma(self, olay):
        if self._basili:
            self._fare_bas = None
            self._basili = None
            return
        self._fare_bas = None
        s = self.S
        dx, dy = olay.x / s, olay.y / s
        for ad, (bx, by, bw, bh) in self.dugme_yerleri(self.TG).items():
            if bx <= dx <= bx + bw and by <= dy <= by + bh:
                if ad == "kapat":
                    self.kapat()
                else:
                    self.gorunum_degistir(ad)
                return
        if self.gorunum == "terminal" and self.terminal and not self.terminal.calisiyor:
            self.terminal_baslat()
        self.kok.focus_force()
        self.c.focus_set()

    def tus(self, olay):
        if olay.state & 0x4:
            k = olay.keysym
            if k in ("plus", "equal", "KP_Add"):
                return self.yazi_buyut()
            if k in ("minus", "underscore", "KP_Subtract"):
                return self.yazi_kucult()
            if k in ("0", "KP_0"):
                return self.yazi_sifirla()
        if self.gorunum == "terminal" and self.terminal:
            return self.terminal.tus(olay)
        return None

    def tekerlek(self, olay):
        if self.gorunum == "terminal" and self.terminal:
            return self.terminal.tekerlek(olay)
        if self._kaydirilir():
            num = getattr(olay, "num", 0)
            yon = 1 if (getattr(olay, "delta", 0) > 0 or num == 4) else -1
            self._kaydir_ayarla(self.kaydir - yon * self.S * 60)
            return "break"
        return None

    def _kaydirilir(self):
        return self.icerik_y * self.S > self.ekran_y + 1

    def _kaydir_ayarla(self, deger):
        ust = 0.0
        alt = max(0.0, self.icerik_y * self.S - self.ekran_y)
        yeni = max(ust, min(alt, deger))
        if abs(yeni - self.kaydir) > 0.5:
            self.kaydir = yeni
            self.ciz()

    def _kart_gorunur(self, y, h):
        y0 = y * self.S - self.kaydir
        return y0 + h * self.S >= 0 and y0 <= self.ekran_y

    # ── terminal ──
    def terminal_baslat(self):
        self.terminal = Terminal(self.c, 0, self.ck.s(UST), self.ekran_g,
                                 self.ekran_y - self.ck.s(UST), self.S,
                                 calisma_dizini=os.path.expanduser("~"),
                                 yazi_boyut=self.terminal_yazi)
        self.terminal.baslat()

    def _yazi_uygula(self, yeni):
        if self.terminal:
            sonuc = self.terminal.yazi_boyut_degistir(yeni)
            if sonuc != -1:
                self.terminal_yazi = sonuc
                self.bildiri = f"Terminal yazı boyutu: {sonuc} px"
                self.bildiri_zaman = time.monotonic()
        else:
            self.terminal_yazi = max(12, min(96, int(yeni)))
        self.ciz()

    def yazi_buyut(self, olay=None):
        self._yazi_uygula(self.terminal_yazi + 4); return "break"

    def yazi_kucult(self, olay=None):
        self._yazi_uygula(self.terminal_yazi - 4); return "break"

    def yazi_sifirla(self, olay=None):
        self._yazi_uygula(self._terminal_yazi_otomatik()); return "break"

    def gorunum_degistir(self, yeni):
        if yeni == "terminal" and not self.terminal_etkin:
            return
        self.gorunum = yeni
        if yeni == "terminal":
            if self.terminal is None:
                self.terminal_baslat()
            else:
                self.terminal.boyut_ayarla(self.ekran_g, self.ekran_y - self.ck.s(UST))
                self.terminal.kirli = True
        self.kok.focus_force()
        self.c.focus_set()
        self.ciz()

    # ── büyüteç ──
    def fare(self, olay):
        yeni = (olay.x, olay.y)
        if self.mercek is not None and (
                abs(yeni[0] - self.mercek[0]) + abs(yeni[1] - self.mercek[1]) > MERCEK_TOLERANS):
            self._mercek_gizle()
        self.mercek_yer = yeni
        self.mercek_zaman = time.monotonic()

    def fare_cikti(self, _olay=None):
        self.mercek_yer = None
        self._mercek_gizle()

    def _mercek_gizle(self):
        if self.mercek is not None:
            self.mercek = None
            self.c.delete("mercek")

    def _mercek_denetle(self):
        yer = self.mercek_yer
        uygun = (self.buyutec and self.gorunum == "pano" and yer is not None
                 and self.ekran_y - yer[1] > self.ck.s(MERCEK_UST_SINIR)
                 and time.monotonic() - self.mercek_zaman >= MERCEK_BEKLEME)
        if uygun:
            if self.mercek is None:
                self.mercek = yer
                self.mercek_ciz()
        else:
            self._mercek_gizle()
        self.kok.after(100, self._mercek_denetle)

    def mercek_ciz(self, v=None):
        self.c.delete("mercek")
        if self.mercek is None or self.gorunum != "pano":
            return
        if v is None:
            v = self.t.al()
        if not v:
            return
        mx, my = self.mercek
        r = MERCEK_YARICAP * self.S
        cx = min(max(mx, r), self.ekran_g - r)
        cy = min(max(my, r), self.ekran_y - r)

        self.c.create_oval(cx - r, cy - r, cx + r, cy + r,
                           fill=self.renk["arka"], outline="", tags="mercek")
        self.ck.kaydir_ayarla(self.kaydir)
        self.ck.zoom_baslat(mx, my, MERCEK_ZOOM, cx, cy)
        self.ck.kirp_baslat(cx, cy, r, "mercek")
        try:
            self._kartlari_ciz(v)
        finally:
            self.ck.kirp_bitir()
            self.ck.zoom_bitir()
            self.ck.kaydir_ayarla(0)
        self.c.create_oval(cx - r, cy - r, cx + r, cy + r,
                           outline=self.renk["mavi"], width=max(2, int(2 * self.S)),
                           tags="mercek")

    # ── çizim ──
    def _gecmise_ekle(self, v):
        for ad, deger in (("cpu", (v.get("cpu") or {}).get("yuzde")),
                          ("bellek", (v.get("bellek") or {}).get("yuzde")),
                          ("sicaklik", (v.get("sicaklik") or {}).get("paket")),
                          ("pil", (v.get("pil") or {}).get("yuzde")),
                          ("gpu", ((v.get("gpu") or {}).get("kartlar") or [{}])[0].get("kullanim")
                           if (v.get("gpu") or {}).get("kartlar") else 0.0),
                          ("dgpu", ((v.get("gpu") or {}).get("nvidia") or {}).get("yuzde")),
                          ("ag_in", (v.get("ag") or {}).get("inen")),
                          ("ag_out", (v.get("ag") or {}).get("giden"))):
            self.gecmis[ad].append(float(deger if deger is not None else 0.0))

    def _kartlari_ciz(self, v):
        for ad, (x, y, w, h) in self.plan["kartlar"].items():
            if not self._kart_gorunur(y, h):
                continue
            cizim = kartlar.CIZIM.get(ad)
            if cizim:
                cizim(self.ck, x, y, w, h, v, self.gecmis)

    def ciz(self):
        v = self.t.al()
        if not v:
            self.kok.after(200, self.ciz)
            return
        self._gecmise_ekle(v)
        self.c.delete("all")

        # üst şerit her zaman sabit (kaydırmadan etkilenmez)
        self.ck.kaydir_ayarla(0)
        self._ust_ciz(v)

        if self.gorunum == "terminal":
            if self.terminal:
                self.terminal.ciz(zorla=True)
            self.kok.after(500, self.ciz)
            return

        self.ck.kaydir_ayarla(self.kaydir)
        self._kartlari_ciz(v)
        self.ck.kaydir_ayarla(0)
        self._kaydirma_gostergesi()
        self.mercek_ciz(v)
        self.kok.after(max(200, int(self.ayar.get("guncelleme_ms", 1000))), self.ciz)

    def _ust_ciz(self, v):
        w = self.TG
        self.ck.dik(0, 0, w, UST, self.renk["ustluk"])
        etiket = ("▣  SİSTEM PANOSU" if self.gorunum == "pano" else "▶  TERMİNAL")
        self.ck.yazi(18, UST / 2, etiket, 12, self.renk["mavi"], True)

        s = v.get("sistem") or {}
        ad = s.get("ad", "-")
        saat = time.strftime("%H:%M:%S")
        self.ck.yazi(w / 2, UST / 2 - 6, f"{ad}   ·   {saat}", 12, self.renk["yazi"],
                     True, "center")
        ust = int(time.monotonic() - self.baslangic)
        alt = f"açık {ust // 3600}sa {(ust % 3600) // 60}dk"
        if self.dpi:
            alt += f"  ·  {self.dpi:.0f} dpi"
        self.ck.yazi(w / 2, UST / 2 + 10, alt, 10, self.renk["cok_soluk"], False, "center")

        if self.bildiri and time.monotonic() - self.bildiri_zaman < 2.5:
            self.ck.yazi(w / 2, UST + 12, self.bildiri, 12, self.renk["mavi"],
                         True, "center")

        for ad_, (bx, by, bw, bh) in self.dugme_yerleri(w).items():
            secili = (ad_ == self.gorunum)
            arka = self.renk["mavi"] if secili else self.renk["dugme"]
            on = self.renk["arka"] if secili else self.renk["yazi"]
            self.ck.dik(bx, by, bx + bw, by + bh, arka, self.renk["kenar"])
            yazi = {"pano": "▤ Pano", "terminal": "⌨ Terminal", "kapat": "✕"}[ad_]
            self.ck.yazi(bx + bw / 2, by + bh / 2 + 1, yazi, 11, on, secili, "center")

    def _kaydirma_gostergesi(self):
        if not self._kaydirilir():
            return
        toplam = self.icerik_y * self.S
        oran = self.ekran_y / toplam
        yuk = max(30, oran * self.ekran_y)
        ust = (self.kaydir / max(1.0, toplam - self.ekran_y)) * (self.ekran_y - yuk)
        x = self.ekran_g - 6
        self.c.create_rectangle(x, ust, x + 4, ust + yuk,
                                fill=self.renk["soluk"], outline="", tags="kaydirma")

    # ── tepsi iletişimi ──
    def _komut_isle(self):
        try:
            if os.path.exists(self.komut_yolu):
                with open(self.komut_yolu) as f:
                    komut = f.read().strip()
                os.remove(self.komut_yolu)
                if komut:
                    self._komut_calistir(komut)
        except Exception:
            pass
        self.kok.after(500, self._komut_isle)

    def _komut_calistir(self, komut):
        if komut == "goster":
            self.goster()
        elif komut == "gizle":
            self.gizle()
        elif komut == "degistir_gorunurluk":
            self.gizle() if self.gorunur else self.goster()
        elif komut.startswith("gorunum:"):
            hedef = komut.split(":", 1)[1]
            if hedef in ("pano", "terminal"):
                self.goster()
                self.gorunum_degistir(hedef)
        elif komut == "gorunum_degistir":
            self.goster()
            self.gorunum_degistir("terminal" if self.gorunum == "pano" else "pano")
        elif komut == "yazi:+":
            self._yazi_uygula(self.terminal_yazi + 4)
        elif komut == "yazi:-":
            self._yazi_uygula(self.terminal_yazi - 4)
        elif komut == "yazi:0":
            self._yazi_uygula(self._terminal_yazi_otomatik())
        elif komut == "cikis":
            self.kapat()

    def goster(self):
        self.kok.deiconify()
        self.kok.lift()
        self.gorunur = True
        if self._yerlesimci:
            self.kok.after(250, lambda: self._yerlesimci.yerlestir(deneme=2))

    def gizle(self):
        self.kok.withdraw()
        self.gorunur = False

    def _durum_yaz(self):
        try:
            v = self.t.al() or {}
            d = {
                "zaman": time.time(),
                "gorunum": self.gorunum,
                "gorunur": self.gorunur,
                "yazi": self.terminal_yazi,
                "cpu": (v.get("cpu") or {}).get("yuzde", 0),
                "bellek": (v.get("bellek") or {}).get("yuzde", 0),
                "sicaklik": (v.get("sicaklik") or {}).get("paket", 0),
                "pil": (v.get("pil") or {}).get("yuzde", 0),
            }
            with open(self.durum_yolu + ".tmp", "w") as f:
                json.dump(d, f)
            os.replace(self.durum_yolu + ".tmp", self.durum_yolu)
        except Exception:
            pass
        self.kok.after(3000, self._durum_yaz)

    def _gorev_cubugu_denetle(self):
        if self._yerlesimci:
            self._yerlesimci.gorev_cubugu_denetle()
        self.kok.after(4000, self._gorev_cubugu_denetle)

    def kapat(self):
        for yol in (self.komut_yolu, self.durum_yolu):
            try:
                os.remove(yol)
            except Exception:
                pass
        if self.terminal:
            self.terminal.kapat()
        try:
            self.kok.destroy()
        except Exception:
            pass

    def calistir(self):
        self.kok.mainloop()
