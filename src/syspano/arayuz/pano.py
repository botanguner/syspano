"""SysPano ana penceresi: veriyi toplar, yerleşimi hesaplar, tuvalı çizer.

Uyarlanabilirlik üç yerden gelir:

1. **Ölçek (S)** hedef ekranın DPI'ından hesaplanır (yapılandırmayla ezilebilir).
2. **Tasarım uzayı** pencerenin piksel boyutundan türetilir; en-boy oranına göre
   1–4 sütunlu düzen kurulur (bkz. `arayuz/yerlesim.py`).
3. **Kartlar** verilen dikdörtgene uyar; yer darsa düşük öncelikli kartlar
   gizlenir, gerekirse dikey kaydırma devreye girer.
"""

import json
import os
import threading
import time
import tkinter as tk
from collections import deque

from .. import ayar as ayar_modul
from .. import ortam
from ..toplayici import Toplayici
from ..yerlestir import Yerlestirici
from . import kartlar as kartlar_modul
from . import tema
from . import yerlesim
from .cekim import Cekim
from .terminal import Terminal

# ─── büyüteç (mercek) ayarları ───────────────────────────────────────────────
MERCEK_ZOOM = 2.6
MERCEK_BEKLEME = 0.4        # imleç bu kadar saniye durunca belirir
MERCEK_TOLERANS = 6         # bu kadar pikselden fazla oynarsa gizlenir
MERCEK_UST_SINIR = 52       # bu tasarım yüksekliğinin üstünde gizlenir (düğmeler)
GECMIS_UZUNLUK = 240


class Pano:
    def __init__(self, ayarlar, cikis=None, mod="ekran"):
        self.ayarlar = ayarlar
        self.cikis = cikis
        self.mod = mod
        self.sinif = "syspano"
        self.R = tema.tema_sec(ayarlar.get("tema", "koyu"))

        # ── geometri (X11/Xwayland piksel uzayı) ──
        if cikis is not None:
            self.x, self.y, self.w, self.h = cikis.tk_geom
            self.kwin_koord = cikis.kwin_geom
        else:
            from ..ekran import sanal_ekran
            sw, sh = sanal_ekran()
            self.x, self.y, self.w, self.h = 0, 0, sw or 1280, sh or 720
            self.kwin_koord = None
        if mod == "pencere":
            pw, ph = [int(v) for v in ayarlar.get("pencere", [1280, 720])]
            self.x += max(0, (self.w - pw) // 2)
            self.y += max(0, (self.h - ph) // 2)
            self.w, self.h = pw, ph
            self.kwin_koord = None

        self.S = self._olcek_hesapla()
        self.tasarim_g = max(320, int(round(self.w / self.S)))
        self.tasarim_y = max(240, int(round(self.h / self.S)))

        # ── durum ──
        self.gorunum = "pano"                 # "pano" | "terminal"
        self.terminal = None
        self.gorunur = True
        self.kaydir = 0.0
        self._max_kaydir = 0.0
        self._tiklama = None
        self._son_plan = None
        self._son_imza = None
        self.bildiri = ""
        self.bildiri_zaman = 0.0
        self.t = Toplayici(ayarlar)
        self.gecmis = {k: deque(maxlen=GECMIS_UZUNLUK) for k in
                       ("cpu", "bellek", "sicaklik", "pil", "gpu", "dgpu",
                        "ag_in", "ag_out")}

        # mercek
        self.mercek = None
        self.mercek_yer = None
        self.mercek_zaman = 0.0
        self._fare_son = None            # son görülen imleç yeri (ekran pikseli)
        self._gercek_hareket = False     # pencere açıldığından beri gerçekten oynadı mı

        # tepsi iletişimi
        calisma = ortam.emin_ol(ortam.durum_dizini())
        self.komut_yolu = os.path.join(calisma, "komut")
        self.durum_yolu = os.path.join(calisma, "durum.json")

        # terminal yazı boyutu
        self.terminal_yazi = self._terminal_varsayilan()

        # ── pencere ──
        self.kok = tk.Tk(className=self.sinif)
        self.kok.title(ayarlar.get("uygulama_basligi", "SysPano"))
        self.kok.configure(bg=self.R["arka"])
        self.c = tk.Canvas(self.kok, width=self.w, height=self.h, bg=self.R["arka"],
                           highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.cek = Cekim(self.c, self.S, self.R, tema.yazi_ailesi(self.kok))
        self.cek.ekran_g, self.cek.ekran_y = self.w, self.h
        self.buyutec, self.buyutec_neden = self._buyutec_karar()

        self.yer = Yerlestirici(self.kok, self.sinif, self.x, self.y, self.w, self.h,
                                kwin_koord=self.kwin_koord,
                                yonetilen=(mod == "pencere"
                                           or bool(ayarlar.get("yonetilen_pencere"))))
        self.yer.pencere_hazirla()

        # ── olaylar ──
        self.c.bind("<ButtonPress-1>", self._basildi)
        self.c.bind("<B1-Motion>", self._surukle)
        self.c.bind("<ButtonRelease-1>", self._birakildi)
        self.c.bind("<Motion>", self._fare)
        self.c.bind("<Leave>", self._fare_cikti)
        self.c.bind("<Button-4>", self._tekerlek)
        self.c.bind("<Button-5>", self._tekerlek)
        self.c.bind("<MouseWheel>", self._tekerlek)
        self.kok.bind("<Key>", self._tus)
        self.c.bind("<Key>", self._tus)
        for t in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.kok.bind(t, lambda e: self._yazi_degistir(+2))
            self.c.bind(t, lambda e: self._yazi_degistir(+2))
        for t in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.kok.bind(t, lambda e: self._yazi_degistir(-2))
            self.c.bind(t, lambda e: self._yazi_degistir(-2))
        for t in ("<Control-Key-0>", "<Control-KP_0>"):
            self.kok.bind(t, lambda e: self._yazi_sifirla())
            self.c.bind(t, lambda e: self._yazi_sifirla())
        self.kok.protocol("WM_DELETE_WINDOW", self.kapat)

        # ── zamanlayıcılar ──
        self._kapali = False
        for gecikme in (250, 900, 2600):
            self.kok.after(gecikme, self.yer.uygula)
        threading.Thread(target=self.t.dongu, daemon=True).start()
        self.kok.after(300, self._komut_oku)
        self.kok.after(2000, self._durum_yaz)
        self.kok.after(600, self._mercek_denetle)
        if ayarlar.get("test_suresi"):
            self.kok.after(int(ayarlar["test_suresi"]) * 1000, self.kapat)
        self.ciz()

    # ── ölçek ──
    def _olcek_hesapla(self):
        if self.ayarlar.get("olcek"):
            S = float(self.ayarlar["olcek"])
        else:
            dpi = self.cikis.dpi if self.cikis is not None else 0.0
            S = dpi / 96.0 if dpi > 30 else (min(self.w / 1600.0, self.h / 800.0) or 1.0)
        S = max(0.7, min(3.0, S))
        # çok küçük ekranlarda ölçeği düşür ki tasarım uzayı kullanılabilir kalsın
        S = min(S, max(0.75, self.w / 460.0), max(0.75, self.h / 320.0))
        return max(0.55, S)

    def _terminal_varsayilan(self):
        yazi = self.ayarlar.get("terminal_yazi")
        if yazi:
            return int(yazi)
        return int(max(13, min(34, 14 * self.S)))

    # ── hangi kartlar gösterilecek ──
    def _aktif_kartlar(self, v):
        hazir = []
        istenen = self.ayarlar.get("kartlar") or list(yerlesim.KART_BILGI)
        for k in istenen:
            if k not in yerlesim.KART_BILGI:
                continue
            if k == "pil" and (v.get("pil") or {}).get("yok"):
                continue
            if k == "gpu" and (v.get("gpu") or {}).get("yok"):
                continue
            if k == "yedek" and (v.get("yedek") or {}).get("yok"):
                continue
            if k == "sicaklik" and not (v.get("sicaklik") or {}).get("sensor_var"):
                continue
            hazir.append(k)
        return hazir or ["cpu", "bellek"]

    def _plan(self, v):
        kartlar = self._aktif_kartlar(v)
        otomatik = bool(self.ayarlar.get("otomatik_kart", True))
        imza = (tuple(kartlar), self.tasarim_g, self.tasarim_y, otomatik)
        if imza != self._son_imza:
            self._son_plan = yerlesim.planla(self.tasarim_g, self.tasarim_y, kartlar,
                                             otomatik=otomatik)
            self._son_imza = imza
        return self._son_plan

    # ── düğmeler (üst şeritte sabit) ──
    def _dugmeler(self, TG):
        kg = min(44.0, max(30.0, TG * 0.08))
        kapat = (TG - 14 - kg, 5, kg, 36)
        bt = min(200.0, max(60.0, TG * 0.24))
        terminal = (kapat[0] - 8 - bt, 5, bt, 36)
        bp = min(176.0, max(56.0, TG * 0.22))
        pano_d = (terminal[0] - 8 - bp, 5, bp, 36)
        return {"pano": pano_d, "terminal": terminal, "kapat": kapat}

    # ── ana çizim döngüsü ──
    def ciz(self):
        if self._kapali:
            return
        v = self.t.al()
        if not v:
            self.kok.after(300, self.ciz)
            return
        for ad, deger in (("cpu", (v.get("cpu") or {}).get("yuzde")),
                          ("bellek", (v.get("bellek") or {}).get("yuzde")),
                          ("sicaklik", (v.get("sicaklik") or {}).get("paket")),
                          ("pil", (v.get("pil") or {}).get("yuzde")),
                          ("gpu", self._igpu_kullanim(v)),
                          ("dgpu", ((v.get("gpu") or {}).get("nvidia") or {}).get("yuzde")),
                          ("ag_in", (v.get("ag") or {}).get("inen")),
                          ("ag_out", (v.get("ag") or {}).get("giden"))):
            try:
                self.gecmis[ad].append(float(deger if deger is not None else 0.0))
            except Exception:
                pass

        self.c.delete("all")
        plan = self._plan(v) if self.gorunum == "pano" else None
        self._icerik_ciz(v, plan)
        if self.gorunum == "terminal":
            if self.terminal:
                self.terminal.ciz(zorla=True)
            self.kok.after(500, self.ciz)
        else:
            self._mercek_ciz(v)
            self.kok.after(max(200, int(self.ayarlar.get("guncelleme_ms", 1000))), self.ciz)

    @staticmethod
    def _igpu_kullanim(v):
        for k in ((v.get("gpu") or {}).get("kartlar") or []):
            if k.get("kullanim") is not None:
                return k["kullanim"]
        return None

    def _icerik_ciz(self, v, plan):
        c = self.cek
        # kaydırma sınırları
        if plan:
            self._max_kaydir = max(0.0, plan["icerik_y"] * self.S - self.h)
        else:
            self._max_kaydir = 0.0
        self.kaydir = max(0.0, min(self.kaydir, self._max_kaydir))

        # kartlar (kaydırmalı)
        c.kaydir_ayarla(self.kaydir)
        if plan:
            for kid, (x, y, w, h) in plan["kartlar"].items():
                # ekran dışında kalan kartı hiç çizme (kaydırmada hız kazancı)
                if (y + h) * self.S - self.kaydir < 0 or y * self.S - self.kaydir > self.h:
                    continue
                fonk = kartlar_modul.CIZIM.get(kid)
                if fonk:
                    try:
                        fonk(c, x, y, w, h, v, self.gecmis)
                    except Exception as hata:
                        c.yazi(x + 14, y + h / 2, f"kart hatası: {hata}"[:44], 10,
                               c.renk["kirmizi"])
        # üst şerit ve alt bilgi kaydırmadan etkilenmez
        c.kaydir_ayarla(0.0)
        self._ustluk_ciz(v)
        self._altbilgi_ciz(v, plan)
        self._bildiri_ciz()
        self._kaydirma_gostergesi()

    def _kaydirma_gostergesi(self):
        """İçerik ekrana sığmıyorsa sağ kenarda ince bir kaydırma çubuğu."""
        if self._max_kaydir <= 1:
            return
        oran = self.h / (self.h + self._max_kaydir)
        yuk = max(30.0, oran * self.h)
        ust = (self.kaydir / self._max_kaydir) * (self.h - yuk)
        self.cek.dik_ekran(self.w - 7, ust, self.w - 3, ust + yuk, self.R["soluk"])

    def _metin_gen(self, metin, boyut, kalin=False):
        """Metnin tasarım birimi cinsinden genişliği (üst şerit kaydırmasız)."""
        try:
            f = self.cek._yazi_tipi(boyut, kalin)[0]
            return f.measure(str(metin)) / self.cek.S
        except Exception:
            return len(str(metin)) * boyut * 0.62

    def _ustluk_ciz(self, v):
        c, R = self.cek, self.R
        TG = self.tasarim_g
        c.dik(0, 0, TG, 46, R["ustluk"])
        c.dik(0, 46, TG, 46.8, R["kenar"])
        s = v.get("sistem") or {}
        up = int(s.get("uptime_sn", 0))
        baslik = "▣  SYSPANO" if self.gorunum == "pano" else "▶  TERMINAL"
        c.yazi(18, 23, baslik, 12, R["mavi"], True)

        # orta bilgi: düğmelere çarpmayacak en uzun sürüm seçilir
        dugmeler = self._dugmeler(TG)
        sol, sag = 132.0, dugmeler["pano"][0] - 12.0
        adaylar = [
            f"{s.get('ad', '?')}  ·  {time.strftime('%H:%M:%S')}  ·  "
            f"açık {up // 3600}sa {(up % 3600) // 60}dk",
            f"{s.get('ad', '?')}  ·  {time.strftime('%H:%M:%S')}",
            time.strftime("%H:%M:%S"),
        ]
        for metin in adaylar:
            if sag - sol > 40 and self._metin_gen(metin, 11.5, True) <= sag - sol:
                c.yazi(sol, 23, metin, 11.5, R["yazi"], True, "w")
                break

        for ad, (dx, dy, dw, dh) in dugmeler.items():
            secili = (ad == self.gorunum)
            c.dik(dx, dy, dx + dw, dy + dh, R["mavi"] if secili else R["dugme"], R["kenar"])
            etiket = {"pano": "▤ Pano", "terminal": "⌨ Terminal", "kapat": "✕"}[ad]
            if dw < 74:
                etiket = {"pano": "▤", "terminal": "⌨", "kapat": "✕"}[ad]
            c.yazi(dx + dw / 2, dy + dh / 2 + 1, etiket, 11,
                   R["arka"] if secili else R["yazi"], secili, "center")

    def _bildiri_ciz(self):
        if not (self.bildiri and time.monotonic() - self.bildiri_zaman < 2.5):
            return
        c, R = self.cek, self.R
        g = self._metin_gen(self.bildiri, 12, True)
        bx, by = self.tasarim_g / 2.0, self.tasarim_y - 34
        c.dik(bx - g / 2 - 14, by - 12, bx + g / 2 + 14, by + 12, R["dugme"], R["mavi"])
        c.yazi(bx, by, self.bildiri, 12, R["yazi"], True, "center")

    def _altbilgi_ciz(self, v, plan):
        c, R = self.cek, self.R
        ekran = self.cikis.ad if self.cikis else "tüm ekran"
        parcalar = [f"{self.w}x{self.h} ({ekran})", f"ölçek {self.S:.2f}"]
        if plan and self.tasarim_g > 620:
            parcalar.append(f"{plan['sutun']} sütun")
            if plan["gizli"]:
                parcalar.append(f"gizli {len(plan['gizli'])}")
            if plan["kaydirilir"] or self._max_kaydir > 1:
                parcalar.append("kaydırılabilir")
        c.yazi(14, self.tasarim_y - 6, "  ·  ".join(parcalar), 10, R["cok_soluk"],
               False, "sw")
        # sağdaki uzun metin yalnızca yer varsa (çakışmasın)
        if self.tasarim_g > 1000:
            c.yazi(self.tasarim_g - 14, self.tasarim_y - 6,
                   f"{os.uname().release[:20]}  ·  SysPano", 10, R["cok_soluk"], False, "se")
        elif self.tasarim_g > 620:
            c.yazi(self.tasarim_g - 14, self.tasarim_y - 6, "SysPano", 10,
                   R["cok_soluk"], False, "se")

    # ── büyüteç ──
    def _buyutec_karar(self):
        """Büyüteç açık mı? (durum, gerekçe) döndürür.

        `auto`: yalnızca fare/dokunmatik yüzey varsa ve ekran yeterince genişse
        açılır. Dokunmatik panelde büyüteç belirip kaybolmadığı için ekranı
        kalıcı olarak kapatıyordu; orada kendiliğinden kapalıdır.
        """
        secim = self.ayarlar.get("buyutec", "auto")
        if secim is True:
            return True, "elle açık"
        if secim is False:
            return False, "elle kapalı"
        if not ortam.goreli_isaretci_var():
            return False, "fare yok (dokunmatik ekran)"
        if self.tasarim_g < 640 or self.tasarim_y < 320:
            return False, "ekran küçük"
        return True, "fare var"

    def _fare(self, olay):
        yeni = (olay.x, olay.y)
        # Pencere imlecin altında açıldığında kendiliğinden bir hareket olayı
        # gelir; büyütecin belirmesi için imleç gerçekten oynamalı.
        if self._fare_son is not None and (
                abs(yeni[0] - self._fare_son[0]) + abs(yeni[1] - self._fare_son[1]) >= 3):
            self._gercek_hareket = True
        self._fare_son = yeni
        if self.mercek is not None and (
                abs(yeni[0] - self.mercek[0]) + abs(yeni[1] - self.mercek[1]) > MERCEK_TOLERANS):
            self._mercek_gizle()
        self.mercek_yer = yeni
        self.mercek_zaman = time.monotonic()

    def _fare_cikti(self, _olay=None):
        self.mercek_yer = None
        self._fare_son = None
        self._gercek_hareket = False
        self._mercek_gizle()

    def _mercek_gizle(self):
        if self.mercek is not None:
            self.mercek = None
            self.c.delete("mercek")

    def _mercek_denetle(self):
        if self._kapali:
            return
        yer = self.mercek_yer
        uygun = (self.buyutec and self._gercek_hareket and self.gorunum == "pano"
                 and yer is not None and yer[1] >= self.cek.s(MERCEK_UST_SINIR)
                 and time.monotonic() - self.mercek_zaman >= MERCEK_BEKLEME)
        if uygun:
            if self.mercek is None:
                self.mercek = yer
                self._mercek_ciz(self.t.al())
        else:
            self._mercek_gizle()
        self.kok.after(100, self._mercek_denetle)

    def _mercek_ciz(self, v):
        c = self.cek
        if self.mercek is None or self.gorunum != "pano" or not v:
            return
        mx, my = self.mercek
        r = min(170.0, self.tasarim_g * 0.22) * self.S
        cx = min(max(mx, r), self.w - r)
        cy = min(max(my, r), self.h - r)
        c.c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.R["arka"],
                        outline="", tags="mercek")
        c.kaydir_ayarla(self.kaydir)
        c.zoom_baslat(mx, my, MERCEK_ZOOM, cx, cy)
        c.kirp_baslat(cx, cy, r)
        try:
            plan = self._plan(v)
            for kid, (x, y, w, h) in plan["kartlar"].items():
                fonk = kartlar_modul.CIZIM.get(kid)
                if fonk:
                    fonk(c, x, y, w, h, v, self.gecmis)
        finally:
            c.kirp_bitir()
            c.zoom_bitir()
            c.kaydir_ayarla(0.0)
        c.c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=self.R["mavi"],
                        width=max(2, int(2 * self.S)), tags="mercek")

    # ── fare / tıklama / kaydırma ──
    def _basildi(self, olay):
        self._tiklama = (olay.x, olay.y, self.kaydir)
        # Dokunma/tıklama büyüteci getirmesin: yeniden gerçek hareket gereksin
        self._gercek_hareket = False
        self._mercek_gizle()

    def _surukle(self, olay):
        if self._tiklama is None or self._max_kaydir <= 0:
            return
        self.kaydir = max(0.0, min(self._max_kaydir,
                                   self._tiklama[2] - (olay.y - self._tiklama[1])))
        self._mercek_gizle()
        self.ciz()

    def _birakildi(self, olay):
        if self._tiklama is None:
            return
        bx, by, _ = self._tiklama
        self._tiklama = None
        if abs(olay.x - bx) + abs(olay.y - by) > 8:
            return
        dx, dy = olay.x / self.S, olay.y / self.S      # üst şerit kaydırmasız
        for ad, (qx, qy, qw, qh) in self._dugmeler(self.tasarim_g).items():
            if qx <= dx <= qx + qw and qy <= dy <= qy + qh:
                if ad == "kapat":
                    self.kapat()
                else:
                    self.gorunum_degistir(ad)
                return
        if self.gorunum == "terminal" and self.terminal and not self.terminal.calisiyor:
            self.terminal_baslat()
            self.kok.focus_force()
            self.c.focus_set()
            return
        self.kok.focus_force()
        self.c.focus_set()

    def _tekerlek(self, olay):
        if self.gorunum == "terminal" and self.terminal:
            return self.terminal.tekerlek(olay)
        num = getattr(olay, "num", 0)
        yukari = (getattr(olay, "delta", 0) > 0) or num == 4
        adim = self.h * 0.18
        self.kaydir = max(0.0, min(self._max_kaydir,
                                   self.kaydir - (adim if yukari else -adim)))
        self._mercek_gizle()
        self.ciz()

    def _tus(self, olay):
        if olay.state & 0x4:
            k = olay.keysym
            if k in ("plus", "equal", "KP_Add"):
                self._yazi_degistir(+2)
                return "break"
            if k in ("minus", "underscore", "KP_Subtract"):
                self._yazi_degistir(-2)
                return "break"
            if k in ("0", "KP_0"):
                self._yazi_sifirla()
                return "break"
        if self.gorunum == "terminal" and self.terminal:
            return self.terminal.tus(olay)
        return None

    # ── görünüm ──
    def gorunum_degistir(self, yeni):
        if yeni == "terminal" and not self.ayarlar.get("terminal", True):
            self.bildiri = "terminal kapalı (yapılandırma)"
            self.bildiri_zaman = time.monotonic()
            return
        self.gorunum = yeni
        if yeni == "terminal":
            if self.terminal is None:
                self.terminal_baslat()
            else:
                self.terminal.boyut_ayarla(self.w, self.h - int(46 * self.S))
                self.terminal.kirli = True
        self._mercek_gizle()
        self.kok.focus_force()
        self.c.focus_set()
        self.ciz()

    def terminal_baslat(self):
        self.terminal = Terminal(self.c, 0, int(46 * self.S), self.w,
                                 self.h - int(46 * self.S), self.S,
                                 calisma_dizini=os.path.expanduser("~"),
                                 yazi_boyut=self.terminal_yazi,
                                 yazi_ailesi=self.cek.yazi_ailesi)
        self.terminal.baslat()

    def _yazi_degistir(self, fark):
        if not self.terminal:
            self.bildiri = "önce terminali açın"
            self.bildiri_zaman = time.monotonic()
            if self.gorunum == "pano":
                self.ciz()
            return "break"
        yeni = max(12, min(96, self.terminal_yazi + fark * 2))
        sonuc = self.terminal.yazi_boyut_degistir(yeni)
        if sonuc != -1:
            self.terminal_yazi = sonuc
            self.ayarlar["terminal_yazi"] = sonuc
            try:
                # yalnızca değişen anahtar yazılır; varsayılanlar dosyaya düşmez
                ayar_modul.guncelle({"terminal_yazi": sonuc})
            except Exception:
                pass
            self.bildiri = f"terminal yazı boyutu: {sonuc} px"
            self.bildiri_zaman = time.monotonic()
            self.ciz()
        return "break"

    def _yazi_sifirla(self):
        if self.terminal:
            self.ayarlar.pop("terminal_yazi", None)
            self.terminal_yazi = self._terminal_varsayilan()
            self.terminal.yazi_boyut_degistir(self.terminal_yazi)
            try:
                ayar_modul.guncelle(sil=("terminal_yazi",))
            except Exception:
                pass
            self.bildiri = f"terminal yazı boyutu: {self.terminal_yazi} px"
            self.bildiri_zaman = time.monotonic()
            self.ciz()
        return "break"

    # ── tepsi iletişimi ──
    def _komut_oku(self):
        if self._kapali:
            return
        try:
            if os.path.exists(self.komut_yolu):
                with open(self.komut_yolu) as f:
                    komut = f.read().strip()
                os.remove(self.komut_yolu)
                self._komut_calistir(komut)
        except Exception:
            pass
        self.kok.after(500, self._komut_oku)

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
            self._yazi_degistir(2)
        elif komut == "yazi:-":
            self._yazi_degistir(-2)
        elif komut == "yazi:0":
            self._yazi_sifirla()
        elif komut == "kaydir:+":
            self.kaydir = min(self._max_kaydir, self.kaydir + self.h * 0.2)
            self.ciz()
        elif komut == "kaydir:-":
            self.kaydir = max(0.0, self.kaydir - self.h * 0.2)
            self.ciz()
        elif komut == "cikis":
            self.kapat()

    def goster(self):
        self.kok.deiconify()
        self.kok.lift()
        self.gorunur = True
        self.kok.after(250, self.yer.uygula)

    def gizle(self):
        self.kok.withdraw()
        self.gorunur = False

    def _durum_yaz(self):
        if self._kapali:
            return
        try:
            v = self.t.al() or {}
            durum = {
                "zaman": time.time(),
                "gorunum": self.gorunum,
                "gorunur": self.gorunur,
                "yazi": self.terminal_yazi,
                "cpu": (v.get("cpu") or {}).get("yuzde", 0),
                "bellek": (v.get("bellek") or {}).get("yuzde", 0),
                "sicaklik": (v.get("sicaklik") or {}).get("paket", 0),
                "pil": (v.get("pil") or {}).get("yuzde", 0),
            }
            gecici = self.durum_yolu + ".tmp"
            with open(gecici, "w") as f:
                json.dump(durum, f)
            os.replace(gecici, self.durum_yolu)
        except Exception:
            pass
        self.kok.after(3000, self._durum_yaz)

    def kapat(self):
        self._kapali = True
        for yol in (self.komut_yolu, self.durum_yolu):
            try:
                os.remove(yol)
            except Exception:
                pass
        if self.terminal:
            try:
                self.terminal.kapat()
            except Exception:
                pass
        try:
            self.kok.destroy()
        except Exception:
            pass

    def calistir(self):
        self.kok.mainloop()
