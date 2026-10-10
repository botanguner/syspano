"""Sistem tepsisi simgesi (isteğe bağlı, PySide6 gerekir).

Panoyu yönetir: göster/gizle, pano ↔ terminal görünümü, terminal yazı boyutu,
kaydırma ve çıkış. Panoyla **dosya üzerinden** konuşur (komut/durum), böylece
Qt ve Tk aynı süreçte olmak zorunda kalmaz:

    <çalışma dizini>/komut      → tepsi yazar, pano okur
    <çalışma dizini>/durum.json → pano yazar, tepsi okur

Çalıştırma:  python -m syspano.tepsi   (pano kendiliğinden başlatır)
"""

import json
import os
import subprocess
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import ortam

CALISMA = ortam.emin_ol(ortam.durum_dizini())
KOMUT_YOLU = os.path.join(CALISMA, "komut")
DURUM_YOLU = os.path.join(CALISMA, "durum.json")


def _cmdline(pid):
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
            return [x.decode("utf-8", "replace")
                    for x in f.read().split(b"\0") if x]
    except Exception:
        return []


def tepsi_pid(haric=()):
    """Çalışan başka bir tepsi sürecinin PID'i (yoksa None)."""
    haric = set(haric) | {os.getpid()}
    try:
        pidler = sorted(int(p) for p in os.listdir("/proc") if p.isdigit())
    except Exception:
        return None
    for pid in pidler:
        if pid in haric:
            continue
        if any(a.endswith("syspano.tepsi") or a == "syspano.tepsi"
               for a in _cmdline(pid)):
            return pid
    return None


def sahipsiz_mi(ilk_ebeveyn, simdiki_ebeveyn):
    """Pano (ebeveyn) kapandı mı? (saf fonksiyon: /proc testi gerektirmez)"""
    return bool(ilk_ebeveyn) and int(simdiki_ebeveyn) != int(ilk_ebeveyn)


def komut_gonder(metin):
    try:
        with open(KOMUT_YOLU + ".tmp", "w") as f:
            f.write(metin)
        os.replace(KOMUT_YOLU + ".tmp", KOMUT_YOLU)
    except Exception as hata:
        print("komut yazılamadı:", hata, flush=True)


def durum_oku():
    try:
        with open(DURUM_YOLU) as f:
            d = json.load(f)
        if time.time() - d.get("zaman", 0) > 15:
            return None
        return d
    except Exception:
        return None


def simge_ciz():
    """Küçük bir izleme panosu simgesi."""
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor("#0f1116"))
    p.setBrush(QColor("#3daee9"))
    p.drawRoundedRect(3, 7, 58, 42, 7, 7)
    p.setBrush(QColor("#0f1116"))
    p.drawRoundedRect(9, 13, 46, 30, 4, 4)
    p.setBrush(QColor("#27ae60"))
    p.drawRect(14, 28, 7, 11)
    p.setBrush(QColor("#f0c040"))
    p.drawRect(25, 22, 7, 17)
    p.setBrush(QColor("#da4453"))
    p.drawRect(36, 18, 7, 21)
    p.setBrush(QColor("#8b93a7"))
    p.drawRect(26, 50, 12, 5)
    p.end()
    return pm


class Tepsi:
    def __init__(self):
        # Tek kopya: başka bir tepsi çalışıyorsa çık (her pano yeniden
        # başlatmasında yeni bir simge birikiyordu — kullanıcı bildirdi).
        baska = tepsi_pid()
        if baska:
            print(f"başka bir tepsi zaten çalışıyor (pid {baska}) — çıkılıyor",
                  flush=True)
            raise SystemExit(0)
        # Yetim denetimi: pano kapanırsa tepsi de kapansın (SIGKILL'de bile).
        self.ebeveyn = os.getppid()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("SysPano")
        self.app.setQuitOnLastWindowClosed(False)

        self.simge = QSystemTrayIcon(QIcon(simge_ciz()))
        self.simge.setToolTip("SysPano panosu")

        menu = QMenu()
        self.a_goster = menu.addAction("Panoyu gizle")
        self.a_goster.triggered.connect(lambda: komut_gonder("degistir_gorunurluk"))
        menu.addSeparator()
        self.a_pano = menu.addAction("Sistem panosu")
        self.a_pano.triggered.connect(lambda: komut_gonder("gorunum:pano"))
        self.a_term = menu.addAction("Terminal")
        self.a_term.triggered.connect(lambda: komut_gonder("gorunum:terminal"))
        menu.addSeparator()
        kaydir = menu.addMenu("Kaydır")
        kaydir.addAction("Yukarı").triggered.connect(lambda: komut_gonder("kaydir:-"))
        kaydir.addAction("Aşağı").triggered.connect(lambda: komut_gonder("kaydir:+"))
        yazi = menu.addMenu("Terminal yazı boyutu")
        yazi.addAction("Büyüt  (Ctrl +)").triggered.connect(lambda: komut_gonder("yazi:+"))
        yazi.addAction("Küçült  (Ctrl −)").triggered.connect(lambda: komut_gonder("yazi:-"))
        yazi.addAction("Varsayılan").triggered.connect(lambda: komut_gonder("yazi:0"))
        menu.addSeparator()
        self.a_baslat = menu.addAction("Panoyu başlat")
        self.a_baslat.triggered.connect(self.pano_baslat)
        menu.addSeparator()
        menu.addAction("Çıkış").triggered.connect(self.cikis)
        self.simge.setContextMenu(menu)
        self.simge.activated.connect(self.tiklandi)
        self.simge.show()

        self.zamanlayici = QTimer()
        self.zamanlayici.timeout.connect(self.durum_guncelle)
        self.zamanlayici.start(2000)
        self.durum_guncelle()

    def pano_baslat(self):
        try:
            subprocess.Popen([sys.executable, "-m", "syspano"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except Exception as hata:
            print("başlatılamadı:", hata, flush=True)

    def tiklandi(self, neden):
        if neden in (QSystemTrayIcon.Trigger, QSystemTrayIcon.MiddleClick):
            komut_gonder("degistir_gorunurluk")

    def durum_guncelle(self):
        if sahipsiz_mi(self.ebeveyn, os.getppid()):
            print("pano kapandı — tepsi kapanıyor", flush=True)
            self.app.quit()
            return
        d = durum_oku()
        if not d:
            self.a_goster.setText("Panoyu başlat")
            try:
                self.a_goster.triggered.disconnect()
            except Exception:
                pass
            self.a_goster.triggered.connect(self.pano_baslat)
            self.simge.setToolTip("SysPano panosu çalışmıyor — başlatmak için tıklayın")
            return
        if self.a_goster.text() == "Panoyu başlat":
            try:
                self.a_goster.triggered.disconnect()
            except Exception:
                pass
            self.a_goster.triggered.connect(lambda: komut_gonder("degistir_gorunurluk"))
        self.a_goster.setText("Panoyu gizle" if d.get("gorunur") else "Panoyu göster")
        self.a_pano.setEnabled(d.get("gorunum") != "pano")
        self.a_term.setEnabled(d.get("gorunum") != "terminal")
        self.simge.setToolTip(
            f"SysPano\n"
            f"CPU %{d.get('cpu', 0):.0f} · {d.get('sicaklik', 0):.0f}°C · "
            f"bellek %{d.get('bellek', 0):.0f} · pil %{d.get('pil', 0):.0f}\n"
            f"görünüm: {'terminal' if d.get('gorunum') == 'terminal' else 'sistem panosu'}"
            f" · yazı {d.get('yazi', 0)} px")

    def cikis(self):
        komut_gonder("cikis")
        QTimer.singleShot(600, self.app.quit)


def main():
    t = Tepsi()
    sys.exit(t.app.exec())


if __name__ == "__main__":
    main()
