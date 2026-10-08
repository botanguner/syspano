#!/usr/bin/env python3
"""Panoya gömülü terminal: PTY + basit VT100 ayrıştırıcı + Tk Canvas çizimi.

Ayrı pencere/uygulama gerekmez. Satır odaklı komutlar (ls, journalctl, dnf, git,
python…) ve temel tam ekran programlar (clear, top -b, htop'a kadar pek çok
program) doğru görünür.

Kullanım (pano içinden):
    t = Terminal(canvas, x, y, w, h, S, calisma_dizini="/home/kullanici")
    t.baslat()          # kabuğu açar
    t.tus(olay)         # klavye olayını iletir
    t.ciz()             # ızgarayı çizer
    t.kapat()
"""

import codecs
import fcntl
import os
import pty
import select
import signal
import struct
import termios
import threading
import time
import tkinter.font as tkfont

from .tema import yazi_ailesi as _yazi_ailesi

VARSAYILAN_YAZI = 20      # terminal yazı boyutu (piksel); pano ölçeğe göre verir

# 16 temel + 8 parlak ANSI rengi (koyu temaya uygun)
RENKLER = [
    "#1c1f26", "#e06c75", "#98c379", "#e5c07b", "#61afef", "#c678dd", "#56b6c2", "#abb2bf",
]
PARLAK = [
    "#5c6370", "#ff7b85", "#b6f0a0", "#ffd68a", "#8ccaff", "#e2a6ff", "#7fe8f5", "#ffffff",
]


class Terminal:
    """PTY'ye bağlı, Tk Canvas üzerine çizen basit terminal."""

    def __init__(self, canvas, x, y, w, h, S, calisma_dizini=None, kabuk=None,
                 yazi_boyut=None, yazi_ailesi=None):
        self.c = canvas
        self.x, self.y, self.w, self.h = x, y, w, h
        self.S = S
        self.calisma_dizini = calisma_dizini or os.path.expanduser("~")
        self.kabuk = kabuk or os.environ.get("SHELL", "/bin/bash")
        self.yazi_ailesi = yazi_ailesi or YAZI

        # yazı boyutu (piksel). Yüksek yoğunluklu panellerde okunabilirlik
        # için pano ölçeğe göre daha büyük bir değer verir.
        self.yazi_boyut = max(12, min(96, int(yazi_boyut or VARSAYILAN_YAZI)))
        self.imlec_satir = self.imlec_kolon = 0
        self._font_ve_izgara()
        self.fg, self.bg, self.stil = None, None, 0
        self.kayitli_imlec = (0, 0)
        self.imlec_gorunur = True
        self.veri_kilit = threading.Lock()
        self.kirli = True
        self.calisiyor = False
        self.pid = None
        self.fd = None
        self.kaydirma = 0                # kullanıcı kaydırma konumu (0 = en altta)
        self.gecmis = []                 # kaydırılan satırlar
        self._cozucu = codecs.getincrementaldecoder("utf-8")("replace")
        self._durum = "normal"
        self.alt_ekran = None          # TUI programları için alternatif tampon
        self.alt_kayitli_imlec = (0, 0)

    # ── yardımcılar ─────────────────────────────────────────────────────────
    def _bos_hucre(self):
        return (" ", None, None, 0)

    def _font_ve_izgara(self, koru=False):
        """Yazı boyutuna göre fontu, hücre ölçülerini ve ızgarayı kurar.

        koru=True: ekrandaki metin ve geçmiş korunur (satırlar yeni genişliğe uyarlanır).
        """
        eski_ekran = getattr(self, "ekran", None)
        eski_gecmis = list(getattr(self, "gecmis", []) or [])
        self.hucre_h = max(10, min(120, int(self.yazi_boyut)))
        self.font = tkfont.Font(family=self.yazi_ailesi, size=-self.hucre_h)
        self.hucre_g = max(4, self.font.measure("M"))
        self.satir_h = max(6, self.font.metrics("linespace"))
        self.kolon = max(20, int(self.w // self.hucre_g))
        self.satir = max(5, int(self.h // self.satir_h))

        def uyarla(satir):
            if len(satir) < self.kolon:
                return list(satir) + [self._bos_hucre() for _ in range(self.kolon - len(satir))]
            return list(satir[:self.kolon])

        if koru and eski_ekran:
            yeni = [uyarla(r) for r in eski_ekran[:self.satir]]
            while len(yeni) < self.satir:
                yeni.append([self._bos_hucre() for _ in range(self.kolon)])
            self.ekran = yeni
            self.gecmis = [uyarla(r) for r in eski_gecmis]
        else:
            self.ekran = [[self._bos_hucre() for _ in range(self.kolon)] for _ in range(self.satir)]
            self.gecmis = []
        self.kaydirma_ust, self.kaydirma_alt = 0, self.satir - 1
        self.imlec_satir = max(0, min(getattr(self, "imlec_satir", 0), self.satir - 1))
        self.imlec_kolon = max(0, min(getattr(self, "imlec_kolon", 0), self.kolon - 1))
        self.kirli = True

    def _pty_boyut(self):
        """PTY'ye yeni satır/kolon sayısını bildirir."""
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                            struct.pack("HHHH", self.satir, self.kolon, 0, 0))
            except Exception:
                pass
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGWINCH)
            except Exception:
                pass

    def boyut_ayarla(self, w, h):
        """Pencere boyutu değişince ızgarayı ve PTY pencere boyutunu günceller."""
        onceki = (self.kolon, self.satir)
        self.w, self.h = w, h
        with self.veri_kilit:
            self._font_ve_izgara(koru=True)
        if (self.kolon, self.satir) == onceki:
            return
        self._pty_boyut()

    def yazi_boyut_degistir(self, yeni):
        """Yazı boyutunu değiştirir (piksel). Aynı boyut verilirse -1 döner."""
        yeni = max(12, min(96, int(yeni)))
        if yeni == self.yazi_boyut:
            return -1
        self.yazi_boyut = yeni
        with self.veri_kilit:
            self._font_ve_izgara(koru=True)      # ekrandaki metin korunur
        self._pty_boyut()
        if self.calisiyor:
            self.gonder("\n")          # kabuk yeni boyutta istem satırını yazsın
        self.kirli = True
        return yeni

    # ── PTY ─────────────────────────────────────────────────────────────────
    def baslat(self):
        if self.calisiyor:
            return
        self.pid, self.fd = pty.fork()
        if self.pid == 0:                                  # çocuk: kabuk
            try:
                os.chdir(self.calisma_dizini)
            except Exception:
                pass
            os.environ["TERM"] = "xterm-256color"
            os.environ["COLORTERM"] = "truecolor"
            os.environ["LANG"] = os.environ.get("LANG", "tr_TR.UTF-8")
            os.environ["PS1"] = "\\[\\e[38;5;39m\\]pano\\[\\e[0m\\]:\\w\\$ "
            try:
                os.execvp(self.kabuk, [self.kabuk, "-i"])
            except Exception:
                os._exit(127)
        self.calisiyor = True
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", self.satir, self.kolon, 0, 0))
        threading.Thread(target=self._okuyucu, daemon=True).start()

    def _okuyucu(self):
        fd = self.fd
        while self.calisiyor and fd is not None:
            try:
                hazir, _, _ = select.select([fd], [], [], 0.2)
                if not hazir:
                    continue
                ham = os.read(fd, 65536)
            except Exception:
                break
            if not ham:
                break
            metin = self._cozucu.decode(ham)
            if metin:
                with self.veri_kilit:
                    self._isle(metin)
                self.kirli = True
        self.calisiyor = False
        self.kirli = True

    def gonder(self, metin):
        if self.fd is None or not self.calisiyor:
            return
        try:
            os.write(self.fd, metin.encode("utf-8", "replace"))
        except Exception:
            pass

    def kapat(self):
        self.calisiyor = False
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGHUP)
                os.waitpid(self.pid, os.WNOHANG)
            except Exception:
                pass
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
        self.pid = self.fd = None

    # ── VT ayrıştırıcı ──────────────────────────────────────────────────────
    def _isle(self, metin):
        i = 0
        n = len(metin)
        while i < n:
            ch = metin[i]
            if self._durum == "esc":
                if ch == "[":
                    self._durum, self._param, self._ara = "csi", "", ""
                elif ch == "]":
                    self._durum = "osc"
                elif ch in "()#%":
                    self._durum, self._atla = "charset", 1
                else:
                    self._durum = "normal"
                i += 1
                continue
            if self._durum == "charset":
                self._atla -= 1
                if self._atla <= 0:
                    self._durum = "normal"
                i += 1
                continue
            if self._durum == "osc":
                if ch == "\x07":
                    self._durum = "normal"
                elif ch == "\x1b":
                    self._durum = "osc_esc"
                i += 1
                continue
            if self._durum == "osc_esc":
                self._durum = "normal" if ch == "\\" else "osc"
                i += 1
                continue
            if self._durum == "csi":
                if "\x40" <= ch <= "\x7e":
                    self._csi(self._param, ch)
                    self._durum = "normal"
                else:
                    self._param += ch
                i += 1
                continue

            if ch == "\x1b":
                self._durum = "esc"
            elif ch == "\n":
                self._satir_ileri()
            elif ch == "\r":
                self.imlec_kolon = 0
            elif ch == "\b":
                self.imlec_kolon = max(0, self.imlec_kolon - 1)
            elif ch == "\t":
                self.imlec_kolon = min(self.kolon - 1, (self.imlec_kolon // 8 + 1) * 8)
            elif ch == "\x07":
                pass
            elif ch >= " ":
                self._yaz(ch)
            i += 1

    def _parametreler(self, param, varsayilan=1):
        param = param.lstrip("?").lstrip(">")
        if not param:
            return [varsayilan]
        return [int(p) if p.isdigit() else varsayilan for p in param.split(";")]

    def _csi(self, param, final):
        p = self._parametreler(param)
        if final == "A":
            self.imlec_satir = max(self.kaydirma_ust, self.imlec_satir - p[0])
        elif final == "B":
            self.imlec_satir = min(self.kaydirma_alt, self.imlec_satir + p[0])
        elif final == "C":
            self.imlec_kolon = min(self.kolon - 1, self.imlec_kolon + p[0])
        elif final == "D":
            self.imlec_kolon = max(0, self.imlec_kolon - p[0])
        elif final in "Hf":
            satir = (p[0] if p else 1) - 1
            kolon = (p[1] - 1) if len(p) > 1 else 0
            self.imlec_satir = max(0, min(self.satir - 1, satir))
            self.imlec_kolon = max(0, min(self.kolon - 1, kolon))
        elif final == "J":
            self._sil_ekran(p[0] if p else 0)
        elif final == "K":
            self._sil_satir(p[0] if p else 0)
        elif final == "m":
            self._sgr(param)
        elif final == "L":
            self._satir_ekle(p[0])
        elif final == "M":
            self._satir_sil(p[0])
        elif final == "P":
            self._karakter_sil(p[0])
        elif final == "@":
            self._karakter_ekle(p[0])
        elif final == "S":
            for _ in range(p[0]):
                self._kaydir_yukari()
        elif final == "T":
            for _ in range(p[0]):
                self._kaydir_asagi()
        elif final == "r":
            self.kaydirma_ust = max(0, (p[0] if p else 1) - 1)
            self.kaydirma_alt = min(self.satir - 1, (p[1] if len(p) > 1 else self.satir) - 1)
            self.imlec_satir = self.imlec_kolon = 0
        elif final == "s":
            self.kayitli_imlec = (self.imlec_satir, self.imlec_kolon)
        elif final == "u":
            self.imlec_satir, self.imlec_kolon = self.kayitli_imlec
        elif final in "hl":
            kod = param.lstrip("?")
            if kod.startswith("25"):
                self.imlec_gorunur = final == "h"
            elif kod.startswith(("1049", "47", "1047")):
                if final == "h":
                    self.alt_ekran = [row[:] for row in self.ekran]
                    self.alt_kayitli_imlec = (self.imlec_satir, self.imlec_kolon)
                    self.ekran = [[self._bos_hucre() for _ in range(self.kolon)] for _ in range(self.satir)]
                    self.imlec_satir = self.imlec_kolon = 0
                else:
                    if self.alt_ekran is not None:
                        self.ekran = self.alt_ekran
                        self.alt_ekran = None
                    self.imlec_satir, self.imlec_kolon = self.alt_kayitli_imlec
            elif kod.startswith("1048"):        # imleci kaydet / geri yükle
                if final == "h":
                    self.kayitli_imlec = (self.imlec_satir, self.imlec_kolon)
                else:
                    self.imlec_satir, self.imlec_kolon = self.kayitli_imlec

    def _sgr(self, param):
        kodlar = [int(x) for x in param.split(";") if x.isdigit()] or [0]
        i = 0
        while i < len(kodlar):
            k = kodlar[i]
            if k == 0:
                self.fg = self.bg = None
                self.stil = 0
            elif k == 1:
                self.stil |= 1
            elif k == 22:
                self.stil &= ~1
            elif k == 3:
                self.stil |= 4
            elif k == 23:
                self.stil &= ~4
            elif k == 4:
                self.stil |= 2
            elif k == 24:
                self.stil &= ~2
            elif k == 7:
                self.stil |= 8
            elif k == 27:
                self.stil &= ~8
            elif k == 9:
                self.stil |= 16
            elif k == 29:
                self.stil &= ~16
            elif 30 <= k <= 37:
                self.fg = RENKLER[k - 30]
            elif 90 <= k <= 97:
                self.fg = PARLAK[k - 90]
            elif k == 39:
                self.fg = None
            elif 40 <= k <= 47:
                self.bg = RENKLER[k - 40]
            elif 100 <= k <= 107:
                self.bg = PARLAK[k - 100]
            elif k == 49:
                self.bg = None
            elif k in (38, 48) and i + 2 < len(kodlar):        # 256 renk / truecolor
                hedef_fg = k == 38
                mod = kodlar[i + 1]
                if mod == 5:
                    renk = self._256(kodlar[i + 2])
                    i += 2
                elif mod == 2 and i + 4 < len(kodlar):
                    renk = "#%02x%02x%02x" % (kodlar[i + 2] & 255, kodlar[i + 3] & 255, kodlar[i + 4] & 255)
                    i += 4
                else:
                    renk = None
                if hedef_fg:
                    self.fg = renk
                else:
                    self.bg = renk
            i += 1

    def _256(self, n):
        if n < 16:
            return (RENKLER + PARLAK)[n]
        if n < 232:
            n -= 16
            r, g, b = n // 36, (n % 36) // 6, n % 6
            basamak = [0, 95, 135, 175, 215, 255]
            return "#%02x%02x%02x" % (basamak[r], basamak[g], basamak[b])
        g = 8 + (n - 232) * 10
        return "#%02x%02x%02x" % (g, g, g)

    # ── ekran işlemleri ─────────────────────────────────────────────────────
    def _yaz(self, ch):
        if self.imlec_kolon >= self.kolon:
            self.imlec_kolon = 0
            self._satir_ileri()
        self.ekran[self.imlec_satir][self.imlec_kolon] = (ch, self.fg, self.bg, self.stil)
        self.imlec_kolon += 1

    def _satir_ileri(self):
        if self.imlec_satir >= self.kaydirma_alt:
            self._kaydir_yukari()
        else:
            self.imlec_satir += 1

    def _kaydir_yukari(self):
        self.gecmis.append(self.ekran[self.kaydirma_ust])
        if len(self.gecmis) > 2000:
            self.gecmis.pop(0)
        self.ekran.pop(self.kaydirma_ust)
        self.ekran.insert(self.kaydirma_alt, [self._bos_hucre() for _ in range(self.kolon)])
        if self.kaydirma == 0:
            pass

    def _kaydir_asagi(self):
        self.ekran.pop(self.kaydirma_alt)
        self.ekran.insert(self.kaydirma_ust, [self._bos_hucre() for _ in range(self.kolon)])

    def _satir_ekle(self, adet):
        for _ in range(adet):
            self.ekran.pop(self.kaydirma_alt)
            self.ekran.insert(self.imlec_satir, [self._bos_hucre() for _ in range(self.kolon)])

    def _satir_sil(self, adet):
        for _ in range(adet):
            self.ekran.pop(self.imlec_satir)
            self.ekran.insert(self.kaydirma_alt, [self._bos_hucre() for _ in range(self.kolon)])

    def _karakter_sil(self, adet):
        satir = self.ekran[self.imlec_satir]
        for _ in range(adet):
            if self.imlec_kolon < len(satir):
                satir.pop(self.imlec_kolon)
        while len(satir) < self.kolon:
            satir.append(self._bos_hucre())

    def _karakter_ekle(self, adet):
        satir = self.ekran[self.imlec_satir]
        for _ in range(adet):
            satir.insert(self.imlec_kolon, self._bos_hucre())
            satir.pop()

    def _sil_satir(self, kip):
        satir = self.ekran[self.imlec_satir]
        if kip == 0:
            aralik = range(self.imlec_kolon, self.kolon)
        elif kip == 1:
            aralik = range(0, min(self.imlec_kolon + 1, self.kolon))
        else:
            aralik = range(0, self.kolon)
        for k in aralik:
            satir[k] = self._bos_hucre()

    def _sil_ekran(self, kip):
        if kip == 2:
            for r in range(self.satir):
                self.ekran[r] = [self._bos_hucre() for _ in range(self.kolon)]
            self.gecmis.clear()
        elif kip == 0:
            self._sil_satir(0)
            for r in range(self.imlec_satir + 1, self.satir):
                self.ekran[r] = [self._bos_hucre() for _ in range(self.kolon)]
        elif kip == 1:
            self._sil_satir(1)
            for r in range(0, self.imlec_satir):
                self.ekran[r] = [self._bos_hucre() for _ in range(self.kolon)]

    # ── girdi ───────────────────────────────────────────────────────────────
    def tus(self, olay):
        """Tk klavye olayını PTY'ye iletir."""
        k = olay.keysym
        esleme = {
            "Return": "\r", "KP_Enter": "\r", "BackSpace": "\x7f", "Tab": "\t",
            "Escape": "\x1b", "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C", "Left": "\x1b[D",
            "Home": "\x1b[H", "End": "\x1b[F", "Prior": "\x1b[5~", "Next": "\x1b[6~",
            "Delete": "\x1b[3~", "Insert": "\x1b[2~",
        }
        if k in esleme:
            self.gonder(esleme[k])
            return "break"
        if k.startswith("F") and k[1:].isdigit():
            n = int(k[1:])
            if 1 <= n <= 12:
                self.gonder("\x1b[%d~" % (10 + n) if n < 5 else "\x1b[%d~" % (11 + n))
                return "break"
        if olay.char:
            if olay.state & 0x4 and olay.char.isalpha():      # Ctrl+harf
                self.gonder(chr(ord(olay.char.lower()) - 96))
            else:
                self.gonder(olay.char)
            return "break"
        if len(k) == 1 and k.isprintable():                   # char boşsa keysym'den türet
            self.gonder(k if not (olay.state & 0x4) else chr(ord(k.lower()) - 96))
            return "break"
        if k == "space":
            self.gonder(" ")
            return "break"
        return None

    def tekerlek(self, olay):
        """Kaydırma tekerleği: geçmişe bak."""
        adim = -3 if olay.delta > 0 else 3
        self.kaydirma = max(0, min(len(self.gecmis), self.kaydirma + adim))
        self.kirli = True
        return "break"

    # ── çizim ───────────────────────────────────────────────────────────────
    def ciz(self, zorla=False):
        """Izgarayı canvas'a çizer. zorla=True ise değişmese de yeniden çizer."""
        if not zorla and not self.kirli:
            return
        self.kirli = False
        c, S = self.c, self.S
        etiket = "terminal"
        c.delete(etiket)
        g, sh = self.hucre_g, self.satir_h

        # arka plan
        c.create_rectangle(self.x, self.y, self.x + self.w, self.y + self.h,
                           fill="#0b0d12", outline="", tags=etiket)

        gorunur = self.satir if self.kaydirma == 0 else self.satir
        fark = self.kaydirma
        for r in range(gorunur):
            kaynak = r - fark
            if kaynak >= 0:
                satir = self.ekran[kaynak] if kaynak < self.satir else None
            else:
                indeks = len(self.gecmis) + kaynak
                satir = self.gecmis[indeks] if 0 <= indeks < len(self.gecmis) else None
            if not satir:
                continue
            y = self.y + r * sh
            # arka planı ve metni renk gruplarına göre çiz
            i = 0
            while i < self.kolon:
                _, fg, bg, stil = satir[i]
                j = i
                while j < self.kolon and satir[j][1:4] == (fg, bg, stil):
                    j += 1
                parca = "".join(satir[k][0] for k in range(i, j))
                on, arka = fg, bg
                if stil & 8:                       # ters video
                    on, arka = (arka or "#0b0d12"), (on or "#d7dbe3")
                if arka:
                    c.create_rectangle(self.x + i * g, y, self.x + j * g, y + sh,
                                       fill=arka, outline="", tags=etiket)
                if parca.strip():
                    bicim = []
                    if stil & 1: bicim.append("bold")
                    if stil & 4: bicim.append("italic")
                    if stil & 2: bicim.append("underline")
                    if stil & 16: bicim.append("overstrike")
                    c.create_text(self.x + i * g, y, text=parca, anchor="nw", tags=etiket,
                                  fill=on or "#d7dbe3",
                                  font=(self.yazi_ailesi, -self.hucre_h, " ".join(bicim) if bicim else "normal"))
                i = j

        # imleç (yalnızca en altta ve görünürken)
        if self.imlec_gorunur and self.kaydirma == 0:
            y = self.y + self.imlec_satir * sh
            x = self.x + self.imlec_kolon * g
            if int(time.time() * 1.5) % 2 == 0:
                c.create_rectangle(x, y, x + g, y + sh, fill="#3daee9", outline="", tags=etiket)
        c.tag_raise(etiket)
        if not self.calisiyor:
            c.create_text(self.x + self.w / 2, self.y + self.h / 2,
                          text="kabuk kapandı — tıklayıp 'Yeniden başlat' düğmesini kullanın",
                          fill="#8b93a7", font=(self.yazi_ailesi, -int(16 * S)), tags=etiket)
