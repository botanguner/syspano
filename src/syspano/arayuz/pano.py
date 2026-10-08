"""SysPano ana penceresi: veriyi toplar, yerleşimi hesaplar, tuvalı çizer.

Uyarlanabilirlik üç yerden gelir:

1. **Ölçek (S)** hedef ekranın DPI'ından hesaplanır (yapılandırmayla ezilebilir).
2. **Tasarım uzayı** pencerenin piksel boyutundan türetilir; en-boy oranına göre
   1–4 sütunlu düzen kurulur (bkz. `arayuz/yerlesim.py`).
3. **Kartlar** verilen dikdörtgene uyar; yer darsa düşük öncelikli kartlar
   gizlenir, gerekirse dikey kaydırma devreye girer.
"""

import json
import math
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections import deque

from .. import ayar as ayar_modul
from .. import ortam
from ..cihaz import loglar as loglar_modul
from ..cihaz import servisler as servis_modul
from ..toplayici import Toplayici
from ..yerlestir import Yerlestirici
from . import ayar_ekrani
from . import kartlar as kartlar_modul
from . import tema
from . import yerlesim


def _kirp_yol(yol, azami=46):
    """Uzun yolu baştan kısaltır: '…/storage/logs/laravel.log'."""
    yol = str(yol)
    return yol if len(yol) <= azami else "…" + yol[-(azami - 1):]
from .cekim import Cekim
from .terminal import Terminal

# ─── büyüteç (mercek) ayarları ───────────────────────────────────────────────
MERCEK_ZOOM = 2.6
MERCEK_BEKLEME = 0.4        # imleç bu kadar saniye durunca belirir
MERCEK_TOLERANS = 6         # bu kadar pikselden fazla oynarsa gizlenir
MERCEK_UST_SINIR = 52       # bu tasarım yüksekliğinin üstünde gizlenir (düğmeler)
GECMIS_UZUNLUK = 240

# Kare etiketleri. Tk'de `delete` sonrası çizim ~8 kat pahalıdır; bu yüzden
# yeni kare, eskisi henüz tuvalde dururken çizilir ve eskisi sonra silinir:
#   çiz → KARE_YENİ etiketiyle → ekrandaki eski kareyi (KARE) sil → yeniyi KARE yap
KARE = "kare"               # ekranda duran kare
KARE_YENI = "kare-yeni"     # çizilmekte olan kare
ICERIK = "icerik"           # kaydırmada `canvas.move` ile taşınan bölüm


class Pano:
    def __init__(self, ayarlar, cikis=None, mod="ekran", cikislar=None, demo=False):
        self.ayarlar = ayarlar
        self.cikis = cikis
        self.mod = mod
        self.demo = demo
        self.cikislar = list(cikislar or ([cikis] if cikis else []))
        self.sinif = "syspano"
        self._baslangic_argv = list(sys.argv[1:])   # yeniden başlatmada aynı seçenekler
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
        self.gorunum = "pano"                 # "pano" | "terminal" | "ayar" | "log"
        if ayarlar.get("baslangic_gorunumu") in ("pano", "terminal", "ayar"):
            self.gorunum = ayarlar["baslangic_gorunumu"]
        # günlük görüntüleyici
        self.log_birim = None
        self.log_tip = "birim"                # "birim" (systemd) | "dosya" (log dosyası)
        self.log_ozet = {"hata": 0, "uyari": 0}
        self.log_suz = False                  # yalnızca hata/uyarı satırları
        self.log_metin = ""
        self.log_kaynak = ""
        self.log_zaman = 0.0
        self.log_yenileme = 0.0
        self.log_sonuna = False
        self.terminal = None
        self.gorunur = True
        self.kaydir = 0.0
        self._max_kaydir = 0.0
        self._tiklama = None
        self._son_plan = None
        self._son_imza = None
        self._ayar_plan = None                # ayar ekranının son yerleşimi
        self._kaydirici = None                # sürüklenen kaydırıcı (id, ...)
        self._dongu_id = None                 # bekleyen çizim zamanlayıcısı
        self._son_cizim = 0.0                 # son tam çizimin zamanı
        self._son_gorunum = None              # görünüm değişimini yakalamak için
        self._guncelleme_var = False          # önbellekteki denetim sonucu
        self._guncelleme_kontrol = 0.0
        self.bildiri = ""
        self.bildiri_zaman = 0.0
        if demo:
            from ..demo import DemoToplayici      # uydurma veri, sistem okunmaz
            self.t = DemoToplayici(ayarlar)
        else:
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
        # güncelleme denetimi: önbellek eskimişse arka planda bir kez
        if ayarlar.get("guncelleme_denetimi", True) and not demo:
            self.kok.after(9000, self._guncelleme_denetimi)
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
            if k == "servisler" and (v.get("servisler") or {}).get("yok"):
                continue
            if k == "loglar" and (v.get("loglar") or {}).get("yok"):
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
        kg = min(44.0, max(28.0, TG * 0.08))
        kapat = (TG - 14 - kg, 5, kg, 36)
        ayar = (kapat[0] - 8 - kg, 5, kg, 36)
        bt = min(200.0, max(54.0, TG * 0.22))
        terminal = (ayar[0] - 8 - bt, 5, bt, 36)
        bp = min(176.0, max(50.0, TG * 0.20))
        pano_d = (terminal[0] - 8 - bp, 5, bp, 36)
        return {"pano": pano_d, "terminal": terminal, "ayar": ayar, "kapat": kapat}

    # ── ana çizim döngüsü ──
    # ── ana çizim döngüsü ──
    def ciz(self):
        """Çizer ve bir sonraki çizimi planlar.

        Bekleyen zamanlayıcı önce **iptal edilir**: kaydırma, ayar değişikliği
        gibi elle tetiklenen çizimler aksi hâlde her seferinde kalıcı bir döngü
        başlatır ve kısa sürede onlarca çizim üst üste binip panoyu kilitler.
        """
        if self._kapali:
            return
        self._dongu_iptal()
        gecikme = self._ciz_govde()
        self._dongu_id = self.kok.after(max(100, int(gecikme)), self.ciz)

    def _dongu_iptal(self):
        if self._dongu_id is not None:
            try:
                self.kok.after_cancel(self._dongu_id)
            except Exception:
                pass
            self._dongu_id = None

    def _ciz_govde(self):
        """Bir kare çizer ve sonraki kareye kadar geçecek ms'yi döndürür."""
        self._son_cizim = time.monotonic()
        v = self.t.al()
        if not v:
            return 300
        if not self.gorunur:
            # Pencere gizli (tepsiden saklandı): çizmeye gerek yok, veri
            # toplanmaya devam etsin.
            self.gorunmez_gecen = time.monotonic()
            return 1000
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

        # görünüm değiştiyse tuvali tamamen temizle (nadir; terminal kalıntısı kalmasın)
        if self.gorunum != self._son_gorunum:
            self.c.delete("all")
            self._son_gorunum = self.gorunum

        # güncelleme noktası: önbelleği yarım dakikada bir tazele (ağa çıkmaz)
        if time.monotonic() - self._guncelleme_kontrol > 30:
            self._guncelleme_kontrol = time.monotonic()
            self._guncelleme_var_guncelle()
        plan = self._plan(v) if self.gorunum == "pano" else None

        self.cek.etiket(KARE_YENI)
        try:
            self._icerik_ciz(v, plan)
            if self.gorunum == "pano":
                self._mercek_ciz(v)          # kendi "mercek" etiketini kullanır
        finally:
            self.cek.etiket("")
            self._kare_degistir()            # yeni kare çizildi; eskisi şimdi silinir

        if self.gorunum == "terminal":
            if self.terminal:
                self.terminal.ciz(zorla=True)
            return 500                       # imleç yanıp sönsün diye daha sık
        if self.gorunum == "log" and self.log_birim:
            # görüntüleyici açıkken günlüğü kendiliğinden tazele
            if time.monotonic() - self.log_zaman >= self.LOG_ARALIK:
                self.log_yenile()
            return max(300, int(self.ayarlar.get("guncelleme_ms", 1000)))
        return max(200, int(self.ayarlar.get("guncelleme_ms", 1000)))

    def _kare_degistir(self):
        """Yeni kareyi eskisi dururken çizdikten sonra eskisini siler.

        Tk'de `delete("all")` sonrası öğe oluşturmak — her öğe için "hasarlı
        bölge" hesabı yüzünden — çok daha pahalıdır. Ölçüm (1400x880, 178 öğe):
        `delete all` + çiz 23,6 ms, bu yöntemle 2,8 ms.
        """
        self.c.delete(KARE)                     # ekrandaki eski kare
        self.c.addtag_withtag(KARE, KARE_YENI)  # yeni kare artık "kare"
        self.c.dtag(KARE, KARE_YENI)

    @staticmethod
    def _igpu_kullanim(v):
        for k in ((v.get("gpu") or {}).get("kartlar") or []):
            if k.get("kullanim") is not None:
                return k["kullanim"]
        return None

    def _icerik_ciz(self, v, plan):
        c = self.cek
        durum = None
        # kaydırma sınırları
        if self.gorunum == "log":
            self._max_kaydir = max(0.0, self._log_icerik_y() * self.S - self.h)
        elif self.gorunum == "ayar":
            durum = self._ayar_durumu()
            self._ayar_plan = ayar_ekrani.yerlesim(
                self.tasarim_g, self.tasarim_y, self.ayarlar, self.cikislar, durum)
            self._max_kaydir = max(0.0, self._ayar_plan["icerik_y"] * self.S - self.h)
        elif plan:
            self._max_kaydir = max(0.0, plan["icerik_y"] * self.S - self.h)
        else:
            self._max_kaydir = 0.0
        self.kaydir = max(0.0, min(self.kaydir, self._max_kaydir))
        if self.gorunum == "log" and getattr(self, "log_sonuna", False):
            self.kaydir = self._max_kaydir          # günlükte en yeni satırlar
            self.log_sonuna = False

        # içerik (kaydırmalı) — hem "kare" hem "icerik" etiketi alır
        kartlar_modul.TIKLANABILIR.clear()
        if self.gorunum == "log":
            # başlık sabit (üst şerit gibi), satırlar kaydırılır
            c.etiket(KARE_YENI)
            c.kaydir_ayarla(0.0)
            self._log_baslik_ciz()
            c.etiket((KARE_YENI, ICERIK))
            c.kaydir_ayarla(self.kaydir)
            self._log_satirlari_ciz()
        else:
            c.kaydir_ayarla(self.kaydir)
            c.etiket((KARE_YENI, ICERIK))
            if self.gorunum == "ayar":
                ayar_ekrani.ciz(c, self._ayar_plan, durum)
            elif plan:
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
        c.etiket(KARE_YENI)
        # üst şerit, alt bilgi ve çubuklar kaydırmadan etkilenmez
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

    # ── günlük görüntüleyici ──
    LOG_BASLIK_Y = 70.0      # başlık satırı (üst şeridin ALTINDA)
    LOG_UST = 90.0           # ilk günlük satırının tasarım yüksekliği
    LOG_SATIR_Y = 15.0       # satır aralığı (tasarım birimi)
    LOG_ARALIK = 8.0         # saniye; görüntüleyici açıkken kendiliğinden yenileme

    def log_ac(self, birim):
        """Bir servisin günlüğünü açar (SERVİSLER kartındaki satıra dokununca)."""
        if not birim:
            return
        self.log_birim = birim
        self.log_tip = "birim"
        self.log_sonuna = True
        self.log_yenile(ilk=True)
        self.gorunum_degistir("log")

    def log_ac_dosya(self, yol):
        """Bir günlük dosyasını açar (GÜNLÜKLER kartındaki satıra dokununca)."""
        if not yol:
            return
        self.log_birim = os.path.expanduser(str(yol))
        self.log_tip = "dosya"
        self.log_sonuna = True
        self.log_yenile(ilk=True)
        self.gorunum_degistir("log")

    def log_yenile(self, ilk=False):
        if not self.log_birim:
            return
        satir = int(self.ayarlar.get("servis_log_satir") or 200)
        try:
            if self.log_tip == "dosya":
                metin, kaynak = loglar_modul.gunluk(self.log_birim, satir)
            else:
                metin, kaynak = servis_modul.gunluk(self.log_birim, satir, self.ayarlar)
        except Exception as hata:
            metin, kaynak = f"(günlük okunamadı: {hata})", "hata"
        self.log_metin = metin
        self.log_kaynak = kaynak
        self.log_ozet = loglar_modul.ozet(metin)
        self.log_zaman = time.monotonic()
        if ilk:
            self.log_sonuna = True

    def _log_satirlar(self):
        return loglar_modul.suz(self.log_metin, self.log_suz).splitlines()

    def _log_icerik_y(self):
        return self.LOG_UST + len(self._log_satirlar()) * self.LOG_SATIR_Y + 24

    def _log_baslik_ciz(self):
        """Sabit başlık: kaynak adı, özet, süzgeç ve yenile düğmesi (kaydırmaz)."""
        c, R = self.cek, self.R
        x0 = 14.0
        yb = self.LOG_BASLIK_Y
        baslik = os.path.basename(self.log_birim) if self.log_tip == "dosya" else str(self.log_birim)
        c.yazi(x0, yb, baslik, 12, R["mavi"], True)
        yas = int(time.monotonic() - self.log_zaman) if self.log_zaman else 0
        ozet = self.log_ozet or {}
        ayrinti = (f"{self.log_kaynak} · {yas} sn önce")
        if ozet.get("hata") or ozet.get("uyari"):
            ayrinti += f" · {ozet.get('hata', 0)} hata · {ozet.get('uyari', 0)} uyarı"
        if self.log_tip == "dosya":
            ayrinti = _kirp_yol(self.log_birim, 46) + " · " + ayrinti
        c.yazi(x0 + self._metin_gen(baslik, 12, True) + 14, yb, ayrinti, 10, R["cok_soluk"])
        # süzgeç düğmesi + yenile
        dug = (self.tasarim_g - 14 - 92, yb - 14, 92, 28)
        c.dik(dug[0], dug[1], dug[0] + dug[2], dug[1] + dug[3], R["dugme"], R["kenar"])
        c.yazi(dug[0] + dug[2] / 2, dug[1] + dug[3] / 2 + 1, "⟳ Yenile", 11,
               R["yazi"], True, "center")
        kartlar_modul.TIKLANABILIR.append((("yenile", None), dug))
        suz = (dug[0] - 8 - 116, yb - 14, 116, 28)
        c.dik(suz[0], suz[1], suz[0] + suz[2], suz[1] + suz[3], R["dugme"], R["kenar"])
        c.yazi(suz[0] + suz[2] / 2, suz[1] + suz[3] / 2 + 1,
               ("Yalnız hata" if not self.log_suz else "Tümü"), 11,
               R["sari"] if self.log_suz else R["soluk"], True, "center")
        kartlar_modul.TIKLANABILIR.append((("log_suz", None), suz))

    def _log_satirlari_ciz(self):
        """Kaydırılan günlük satırları (yalnızca görünenler çizilir)."""
        c, R = self.cek, self.R
        x0 = 14.0
        gen = self.tasarim_g - 28.0
        satirlar = self._log_satirlar()
        if not satirlar:
            c.yazi(x0, self.LOG_UST, "(günlük boş)", 11, R["soluk"])
            return
        satir_px = self.LOG_SATIR_Y * self.S
        # Satırlar başlığın ALTINDAKİ bantta görünür; kaydırmaya göre hangi
        # satırların çizileceğini hesaplarız (üstte başlığa taşmasın).
        ilk = max(0, int(math.ceil(self.kaydir / satir_px)))
        son = min(len(satirlar),
                  int((self.kaydir + self.h - self.LOG_UST * self.S) / satir_px) + 2)
        for i in range(ilk, son):
            metin = satirlar[i]
            dusuk = metin.lower()
            if "error" in dusuk or "fail" in dusuk or "hata" in dusuk:
                renk = R["kirmizi"]
            elif "warn" in dusuk or "uyarı" in dusuk:
                renk = R["sari"]
            else:
                renk = R["yazi"] if i >= len(satirlar) - 30 else R["soluk"]
            c.yazi(x0, self.LOG_UST + i * self.LOG_SATIR_Y,
                   kartlar_modul._kirp(c, metin, 10.5, gen), 10.5, renk)

    # ── ayar ekranı ──
    def _bildir(self, metin):
        self.bildiri = metin
        self.bildiri_zaman = time.monotonic()

    def _guncelleme_var_guncelle(self):
        try:
            from .. import guncelleme
            self._guncelleme_var = guncelleme.yeni_surum_var()
        except Exception:
            self._guncelleme_var = False

    def _ayar_durumu(self):
        from .. import guncelleme
        kart_bilgi = {ad: yerlesim.KART_BILGI[ad]["baslik"]
                      for ad in sorted(yerlesim.KART_BILGI,
                                       key=lambda k: yerlesim.KART_BILGI[k]["oncelik"],
                                       reverse=True)}
        self._guncelleme_var_guncelle()
        return {"kart_bilgi": kart_bilgi,
                "surum_metni": f"SysPano {guncelleme.yerel_surum()} · {guncelleme.metin_ozet()}"}

    def _ayar_kutusu(self, kid):
        if not self._ayar_plan:
            return None
        for k in self._ayar_plan["kutular"]:
            if k.get("id") == kid:
                return k
        return None

    def _ayar_isle(self, kid, eylem, deger):
        if eylem in ("sec", "anahtar"):
            self._ayar_uygula(kid, deger)
        elif eylem == "kaydirici_adim":
            kutu = self._ayar_kutusu(kid)
            if kutu:
                yeni = kutu["deger"] + deger * kutu["adim"] * 4
                self._ayar_uygula(kid, max(kutu["alt"], min(kutu["ust"], round(yeni, 4))))
        elif eylem == "kaydirici_basla":
            self._ayar_uygula(kid, deger)
        elif eylem == "dugme":
            self._dugme_isle(kid)
        self._son_imza = None
        self.ciz()

    def _dugme_isle(self, kid):
        if kid == "kapat":
            self.gorunum_degistir("pano")
        elif kid == "olcek_oto":
            self._ayar_uygula("olcek_oto", None)
        elif kid == "guncelle_denetle":
            self._bildir("Güncelleme denetleniyor…")
            self._guncelleme_denetimi(zorla=True)
        elif kid == "guncelle_uygula":
            self._guncellemeyi_baslat()
        elif kid == "yeniden_baslat":
            self._yeniden_baslat()
        elif kid == "sifirla":
            self._ayarlari_sifirla()

    def _ayar_uygula(self, kid, deger):
        a = self.ayarlar
        degisim = None
        if kid == "tema":
            a["tema"] = deger
            self.R = tema.tema_sec(deger)
            self.cek.renk = self.R
            self.kok.configure(bg=self.R["arka"])
            self.c.configure(bg=self.R["arka"])
            degisim = {"tema": deger}
        elif kid == "buyutec":
            a["buyutec"] = {"auto": "auto", "acik": True, "kapali": False}.get(deger, "auto")
            self.buyutec, self.buyutec_neden = self._buyutec_karar()
            degisim = {"buyutec": a["buyutec"]}
        elif kid == "aralik":
            a["guncelleme_ms"] = int(deger)
            self.t.aralik = max(0.25, int(deger) / 1000.0)
            degisim = {"guncelleme_ms": int(deger)}
        elif kid == "ekran":
            a["ekran"] = deger
            degisim = {"ekran": deger}
            self._bildir("Hedef ekran kaydedildi — yeniden başlatınca uygulanır")
        elif kid == "olcek":
            a["olcek"] = round(float(deger), 3)
            self._olcek_uygula()
            degisim = {"olcek": a["olcek"]}
        elif kid == "olcek_oto":
            a["olcek"] = None
            self._olcek_uygula()
            degisim = {"olcek": None}
            self._bildir("Ölçek: ekran DPI'ına göre otomatik")
        elif kid == "terminal":
            a["terminal"] = bool(deger)
            degisim = {"terminal": bool(deger)}
        elif kid == "tepsi":
            a["tepsi"] = bool(deger)
            degisim = {"tepsi": bool(deger)}
            self._bildir("Tepsi ayarı — yeniden başlatınca uygulanır")
        elif kid == "otomatik_kart":
            a["otomatik_kart"] = bool(deger)
            degisim = {"otomatik_kart": bool(deger)}
        elif kid and kid.startswith("kart:"):
            ad = kid.split(":", 1)[1]
            secili = set(a.get("kartlar") or list(yerlesim.KART_BILGI))
            if deger:
                secili.add(ad)
            else:
                secili.discard(ad)
            if not secili:
                secili = {"cpu"}
            a["kartlar"] = [k for k in yerlesim.KART_BILGI if k in secili]
            degisim = {"kartlar": a["kartlar"]}
        if degisim:
            try:
                ayar_modul.guncelle(degisim)
            except Exception:
                pass
        self._son_imza = None

    def _olcek_uygula(self):
        """Ölçek değiştiğinde tasarım uzayını ve bağımlı değerleri tazeler."""
        self.S = self._olcek_hesapla()
        self.tasarim_g = max(320, int(round(self.w / self.S)))
        self.tasarim_y = max(240, int(round(self.h / self.S)))
        self.cek.S = self.S
        self.cek.ekran_g, self.cek.ekran_y = self.w, self.h
        self.buyutec, self.buyutec_neden = self._buyutec_karar()
        self._son_imza = None
        self._ayar_plan = None

    def _guncelleme_denetimi(self, zorla=False):
        """Yeni sürüm var mı? Ağa çıkan iş ayrı bir süreçte yapılır."""
        if self._kapali:
            return
        try:
            from .. import guncelleme
            if not zorla and not guncelleme.denetim_bayati(24):
                self._guncelleme_var_guncelle()
                return
            subprocess.Popen([sys.executable, "-m", "syspano", "--guncelle-denetle"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except Exception:
            pass
        self.kok.after(8000, self._guncelleme_var_guncelle)

    def _guncellemeyi_baslat(self):
        from .. import guncelleme
        if not guncelleme.kayit_oku():
            self._bildir("Kurulum kaydı yok — ./install.sh ile kurun")
            return
        try:
            yol = os.path.join(guncelleme.durum_dizini(), "guncelleme.log")
            with open(yol, "a") as kayit:
                kayit.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} güncelleme ===\n")
                kayit.flush()
                subprocess.Popen([sys.executable, "-m", "syspano", "--guncelle"],
                                 stdout=kayit, stderr=kayit, start_new_session=True)
            self._bildir("Güncelleme arka planda başladı — bitince yeniden başlatın")
        except Exception as hata:
            self._bildir(f"Güncelleme başlatılamadı: {hata}")

    def _yeniden_baslat(self):
        self._bildir("Yeniden başlatılıyor…")
        self._kapali = True
        try:
            if self.terminal:
                self.terminal.kapat()
        except Exception:
            pass
        try:
            os.execv(sys.executable,
                     [sys.executable, "-m", "syspano", *self._baslangic_argv])
        except Exception as hata:
            self._kapali = False
            self._bildir(f"Yeniden başlatılamadı: {hata}")

    def _ayarlari_sifirla(self):
        from .. import guncelleme  # noqa: F401  (paket içe aktarımı sırası için)
        try:
            os.remove(ayar_modul.yol())
        except Exception:
            pass
        self.ayarlar.clear()
        self.ayarlar.update(ayar_modul.oku())
        self.R = tema.tema_sec(self.ayarlar.get("tema", "koyu"))
        self.cek.renk = self.R
        self.kok.configure(bg=self.R["arka"])
        self.c.configure(bg=self.R["arka"])
        self.t.aralik = max(0.25, self.ayarlar.get("guncelleme_ms", 1000) / 1000.0)
        self._olcek_uygula()
        self.terminal_yazi = self._terminal_varsayilan()
        self.kaydir = 0.0
        self._bildir("Ayarlar varsayılana döndü")

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
        baslik = {"pano": "▣  SYSPANO", "terminal": "▶  TERMINAL",
                  "ayar": "⚙  AYARLAR", "log": "≡  GÜNLÜK"}.get(self.gorunum, "▣  SYSPANO")
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
            etiket = {"pano": "▤ Pano", "terminal": "⌨ Terminal",
                      "ayar": "⚙ Ayarlar", "kapat": "✕"}[ad]
            if dw < 74:
                etiket = {"pano": "▤", "terminal": "⌨", "ayar": "⚙", "kapat": "✕"}[ad]
            c.yazi(dx + dw / 2, dy + dh / 2 + 1, etiket, 11,
                   R["arka"] if secili else R["yazi"], secili, "center")
            # güncelleme varsa ⚙ üzerinde küçük bir uyarı noktası
            if ad == "ayar" and self._guncelleme_var:
                r = 4.0
                c.c.create_oval(dx + dw - r - 3, dy + 3, dx + dw + r - 3, dy + 3 + 2 * r,
                                fill=R["sari"], outline=R["ustluk"])

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
        cekirdek = (v.get("sistem") or {}).get("cekirdek") or os.uname().release
        if self.tasarim_g > 1000:
            c.yazi(self.tasarim_g - 14, self.tasarim_y - 6,
                   f"{cekirdek[:20]}  ·  SysPano", 10, R["cok_soluk"], False, "se")
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
        uygun = (self.buyutec and self.gorunur and self._gercek_hareket
                 and self.gorunum == "pano"
                 and yer is not None and yer[1] >= self.cek.s(MERCEK_UST_SINIR)
                 and time.monotonic() - self.mercek_zaman >= MERCEK_BEKLEME)
        if uygun:
            if self.mercek is None:
                self.mercek = yer
                self._mercek_ciz(self.t.al())
        else:
            self._mercek_gizle()
        # büyüteç kapalıysa sık denetlemeye gerek yok (uyanma sayısını azaltır)
        self.kok.after(100 if self.buyutec else 400, self._mercek_denetle)

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
        self._kaydirici = None
        # ayar ekranında kaydırıcıya basıldıysa sürükleme onu ayarlar
        if self.gorunum == "ayar" and self._ayar_plan:
            dx, dy = olay.x / self.S, (olay.y + self.kaydir) / self.S
            isaret = ayar_ekrani.isabet(self._ayar_plan, dx, dy)
            if isaret and isaret[1] == "kaydirici_basla":
                self._kaydirici = isaret[0]

    def _surukle(self, olay):
        # kaydırıcı sürüklemesi (dokunmatikte çubuğu parmakla kaydırma)
        if self._kaydirici is not None:
            kutu = self._ayar_kutusu(self._kaydirici)
            if kutu:
                self._ayar_uygula(self._kaydirici,
                                  ayar_ekrani._kaydirici_deger(kutu, olay.x / self.S))
                self.ciz()
            return
        if (self.gorunum == "terminal" or self._tiklama is None
                or self._max_kaydir <= 0):
            return
        yeni = max(0.0, min(self._max_kaydir,
                            self._tiklama[2] - (olay.y - self._tiklama[1])))
        # Parmak takip etsin: içeriği yeniden çizmek yerine tuval öğelerini
        # kaydır. Tam çizim seyrek yapılır (kaydırmada zaten pahalı olan adım).
        kayma = self.kaydir - yeni          # `self.kaydir` = son çizimdeki konum
        if abs(kayma) >= 0.5:
            self.c.move("icerik", 0, kayma)
            self.kaydir = yeni
            self._mercek_gizle()
        if time.monotonic() - self._son_cizim >= 0.15:
            self.ciz()

    def _birakildi(self, olay):
        if self._tiklama is None:
            return
        bx, by, _ = self._tiklama
        self._tiklama = None
        kaydirici_vardi = self._kaydirici is not None
        self._kaydirici = None
        if abs(olay.x - bx) + abs(olay.y - by) > 8:
            # sürükleme bitti: içeriği tam çizimle tazele (kaydırma çubuğu vb.)
            self.ciz()
            return
        # düğmeler üst şeritte ve kaydırmadan etkilenmez
        dx, dy = olay.x / self.S, olay.y / self.S
        for ad, (qx, qy, qw, qh) in self._dugmeler(self.tasarim_g).items():
            if qx <= dx <= qx + qw and qy <= dy <= qy + qh:
                if ad == "kapat":
                    self.kapat()
                else:
                    self.gorunum_degistir(ad)
                return
        if self.gorunum == "ayar":
            if kaydirici_vardi:
                return                   # kaydırıcıya dokunuldu, değer zaten ayarlandı
            dx, dy = olay.x / self.S, (olay.y + self.kaydir) / self.S
            isaret = ayar_ekrani.isabet(self._ayar_plan, dx, dy)
            if isaret:
                self._ayar_isle(*isaret)
            return
        if self.gorunum == "log":
            dx, dy = olay.x / self.S, (olay.y + self.kaydir) / self.S
            for eylem, (qx, qy, qw, qh) in kartlar_modul.TIKLANABILIR:
                if qx <= dx <= qx + qw and qy <= dy <= qy + qh:
                    if eylem[0] == "yenile":
                        self.log_yenile()
                    elif eylem[0] == "log_suz":
                        self.log_suz = not self.log_suz
                        self.kaydir = 0.0
                    self.ciz()
                    return
            return
        if self.gorunum == "pano":
            # servis satırına dokunulduysa günlüğünü aç
            dx, dy = olay.x / self.S, (olay.y + self.kaydir) / self.S
            for eylem, (qx, qy, qw, qh) in kartlar_modul.TIKLANABILIR:
                if qx <= dx <= qx + qw and qy <= dy <= qy + qh:
                    if eylem[0] == "log":
                        self.log_ac(eylem[1])
                    elif eylem[0] == "log_dosya":
                        self.log_ac_dosya(eylem[1])
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
        yeni = max(0.0, min(self._max_kaydir,
                            self.kaydir - (adim if yukari else -adim)))
        kayma = self.kaydir - yeni
        if abs(kayma) >= 0.5:
            self.c.move("icerik", 0, kayma)
            self.kaydir = yeni
            self._mercek_gizle()
        if time.monotonic() - self._son_cizim >= 0.10:
            self.ciz()

    def _tus(self, olay):
        if olay.keysym == "Escape" and self.gorunum in ("ayar", "log"):
            self.gorunum_degistir("pano")
            return "break"
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
        if yeni not in ("pano", "terminal", "ayar", "log"):
            return
        self.gorunum = yeni
        if yeni in ("ayar", "log"):
            self.kaydir = 0.0
            self._ayar_plan = None
        if yeni == "log" and self.log_birim is None:
            yeni = "pano"                     # açılacak günlük yoksa panoya dön
            self.gorunum = "pano"
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
