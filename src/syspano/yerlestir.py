"""Pencerenin hedef ekrana yerleştirilmesi.

Masaüstüne göre üç yol izlenir:

| Ortam | Yöntem |
|---|---|
| KDE (KWin) | KWin betiği: çerçevesiz, görev çubuğunda yok, tam konum, klavye odağı |
| Diğer X11/Xwayland | `overrideredirect` pencere: yöneticisiz, tam konum, en üstte |
| `--pencere` modu | Normal yönetilen pencere (her yerde çalışır) |

Wayland'de istemciler kendi konumlarını belirleyemez; Tkinter zaten Xwayland
üzerinden çalışır, bu yüzden Xwayland'ın sanal ekran koordinatları kullanılır.
"""

import subprocess
import time

from . import ortam


class Yerlestirici:
    def __init__(self, kok, sinif, x, y, w, h, kwin_koord=None, yonetilen=False):
        self.kok = kok
        self.sinif = sinif
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)
        # KWin'in mantıksal koordinatları (varsa); KWin betiği bunları kullanır
        self.kx, self.ky, self.kw, self.kh = (kwin_koord or (x, y, w, h))
        self.kwin = ortam.kwin_var() and ortam.komut_var("qdbus-qt6")
        self.yonetilen = yonetilen
        self.son_deneme = 0.0

    def pencere_hazirla(self):
        """Pencere türünü ayarlar: KWin'de yönetilen, diğerinde yöneticisiz."""
        if self.yonetilen:
            return
        if self.kwin:
            # Yönetilen pencere: klavye odağı alabilmesi için gerekli.
            # KWin onu görev çubuğunda listelemesin diye türü 'utility'.
            try:
                self.kok.attributes("-type", "utility")
            except Exception:
                pass
        else:
            try:
                self.kok.overrideredirect(True)
            except Exception:
                pass
            try:
                self.kok.attributes("-topmost", True)
            except Exception:
                pass
        try:
            self.kok.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")
        except Exception:
            pass

    def uygula(self):
        """Konumu uygular. Başarılıysa True."""
        if self.yonetilen:
            try:
                self.kok.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")
                return True
            except Exception:
                return False
        if self.kwin:
            return self._kwin_betik()
        return self._tk_geometri()

    # ── KWin betiği ──
    def _kwin_betik(self):
        betik = (
            'let b = 0, a = "";\n'
            'try {\n'
            '  const l = workspace.windowList();\n'
            '  for (let i = 0; i < l.length; i++) {\n'
            f'    if (String(l[i].resourceClass || "").toLowerCase() === "{self.sinif}") {{\n'
            f'      l[i].frameGeometry = {{ x: {self.kx}, y: {self.ky}, '
            f'width: {self.kw}, height: {self.kh} }};\n'
            '      l[i].noBorder = true; l[i].keepAbove = true; l[i].skipTaskbar = true;\n'
            '      b++;\n'
            '    }\n'
            '  }\n'
            '} catch (e) { a = " HATA:" + e; }\n'
            'throw new Error("PANO| yerlestirildi=" + b + a);'
        )
        yol = f"/tmp/{self.sinif}-yerlestir.js"
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
        return False

    # ── Tk ile konumlandırma (yöneticisiz pencere) ──
    def _tk_geometri(self):
        try:
            self.kok.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")
            self.kok.lift()
            return True
        except Exception:
            return False

    def gorev_cubugu_koru(self):
        """X11'de skip-taskbar işaretini yerinde tutar (KWin dışı için geçersiz)."""
        if self.kwin or self.yonetilen:
            return
        if not ortam.komut_var("xprop"):
            return
        try:
            wid = hex(self.kok.winfo_id())
            cikti = subprocess.run(["xprop", "-id", wid, "_NET_WM_STATE"],
                                   capture_output=True, text=True, timeout=3).stdout
            if cikti.strip() and "ABOVE" not in cikti:
                subprocess.run(["xprop", "-id", wid, "-f", "_NET_WM_STATE", "32a",
                                "-set", "_NET_WM_STATE",
                                "_NET_WM_STATE_ABOVE,_NET_WM_STATE_SKIP_TASKBAR"],
                               capture_output=True, timeout=3)
        except Exception:
            pass
