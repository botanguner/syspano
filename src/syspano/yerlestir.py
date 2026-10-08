"""Pencere yerleştirme: pencereyi hedef ekrana tam oturtur.

İki yol vardır:

* **KWin (KDE):** pencere "yönetilen" bırakılır (klavye odağı alabilsin) ve
  geometri KWin betiğiyle ayarlanır; çerçevesiz, en üstte ve görev çubuğunda
  görünmez yapılır.
* **Diğer ortamlar (GNOME, Xfce, labwc/sway, saf X11):** pencere yöneticisiz
  (`overrideredirect`) açılır; KWin betiği olmadığı için konum doğrudan Tk
  geometry ile verilir ve "en üstte" özniteliği kullanılır.

X11/Xwayland uzayı kullanıldığı için konumlar doğrudan monitörlerin gerçek
piksel koordinatlarıdır.
"""

import os
import subprocess
import time

from . import ortam


class Yerlesimci:
    def __init__(self, kok, sinif, kwin=False, tk_geom=(0, 0, 100, 100),
                 kwin_geom=None, yonetilen=None, baslik="SysPano"):
        self.kok = kok
        self.sinif = sinif
        self.kwin = kwin
        self.baslik = baslik
        # X11/Xwayland uzayı → Tk penceresinin boyutu
        self.tk = tuple(int(v) for v in tk_geom)
        # KWin mantıksal uzayı → pencere betiğinin geometrisi
        self.kw = tuple(int(v) for v in (kwin_geom or tk_geom))
        # KWin dışında varsayılan yöneticisiz pencere; --yonetilen ile değişir
        self.yonetilen = bool(kwin) if yonetilen is None else bool(yonetilen)

    # ── pencereyi hazırla ──
    def hazirla(self):
        """Pencereyi haritalamadan önce tipini/çerçevesini ayarlar."""
        if self.kwin and self.yonetilen:
            # Tk pencere tipini 'utility' yapar: KWin bunu görev çubuğunda
            # listelemez ama pencere klavye odağı alabilir.
            try:
                self.kok.attributes("-type", "utility")
            except Exception:
                pass
        else:
            try:
                self.kok.overrideredirect(True)
            except Exception:
                pass
            self._en_ustte()

    def _en_ustte(self):
        try:
            self.kok.attributes("-topmost", True)
        except Exception:
            try:
                self.kok.attributes("-topmost", 1)
            except Exception:
                pass

    # ── konumlandır ──
    def yerlestir(self, deneme=3):
        # Tk her zaman X11/Xwayland koordinatlarıyla boyutlanır (piksel birebir)
        x, y, w, h = self.tk
        self.kok.geometry(f"{w}x{h}+{x}+{y}")
        if self.kwin and self.yonetilen:
            return self._kwin_yerlestir(deneme)
        self.kok.lift()
        return True

    # ── KWin betiği ──
    def _kwin_yerlestir(self, deneme=3):
        x, y, w, h = self.kw          # KWin mantıksal koordinatları
        if self.sinif.lower() in ("", "none"):
            return False
        betik = (
            'let b = 0, a = "";\n'
            'try {\n'
            '  const l = workspace.windowList();\n'
            '  for (let i = 0; i < l.length; i++) {\n'
            f'    if (String(l[i].resourceClass || "").toLowerCase() === "{self.sinif.lower()}") {{\n'
            # SIRA ÖNEMLİ: geometri önce. Tersi durumda KWin pencereyi
            # "maximize" durumuna geçirirken istemciye _NET_WM_STATE yazar ve
            # SKIP_TASKBAR işareti silinir.
            f'      l[i].frameGeometry = {{ x: {x}, y: {y}, width: {w}, height: {h} }};\n'
            '      l[i].noBorder = true; l[i].keepAbove = true; l[i].skipTaskbar = true;\n'
            '      b++;\n'
            '    }\n'
            '  }\n'
            '} catch (e) { a = " HATA:" + e; }\n'
            'throw new Error("PANO| yerlestirildi=" + b + a);'
        )
        yol = "/tmp/syspano-yerlestir.js"
        for _ in range(deneme):
            try:
                with open(yol, "w") as f:
                    f.write(betik)
                sid = subprocess.run(
                    ["qdbus-qt6", "org.kde.KWin", "/Scripting",
                     "org.kde.kwin.Scripting.loadScript", yol],
                    capture_output=True, text=True, timeout=5).stdout.strip()
                if sid.isdigit():
                    subprocess.run(["qdbus-qt6", "org.kde.KWin", f"/Scripting/Script{sid}",
                                    "org.kde.kwin.Script.run"], capture_output=True, timeout=5)
                    subprocess.run(["qdbus-qt6", "org.kde.KWin", "/Scripting",
                                    "org.kde.kwin.Scripting.unloadScript", yol],
                                   capture_output=True, timeout=5)
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    # ── görev çubuğu bekçisi (yalnızca KWin) ──
    def gorev_cubugu_denetle(self):
        """SKIP_TASKBAR işareti düşmüşse geri koyar ve yerleştirmeyi yeniler."""
        if not (self.kwin and self.yonetilen):
            return
        try:
            adaylar = set()
            try:
                adaylar.add(hex(self.kok.winfo_id()))
            except Exception:
                pass
            try:
                c = ortam.komut(["wmctrl", "-l"])
                for satir in c.splitlines():
                    if self.baslik in satir:
                        adaylar.add(satir.split()[0])
            except Exception:
                pass
            eksik = False
            for wid in adaylar:
                c = ortam.komut(["xprop", "-id", wid, "_NET_WM_STATE"])
                if c.strip() and "SKIP_TASKBAR" not in c:
                    eksik = True
            if eksik:
                for wid in adaylar:
                    subprocess.run(["xprop", "-id", wid, "-f", "_NET_WM_STATE", "32a",
                                    "-set", "_NET_WM_STATE",
                                    "_NET_WM_STATE_SKIP_TASKBAR,_NET_WM_STATE_ABOVE"],
                                   capture_output=True, timeout=3)
                self._kwin_yerlestir(deneme=1)
        except Exception:
            pass
