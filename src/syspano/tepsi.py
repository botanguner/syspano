"""Sistem tepsisi simgesi (isteğe bağlı; PySide6 gerekir).

Panoyu yönetir: göster/gizle, görünüm değiştir, terminal yazı boyutu, panoyu
başlat, çıkış. Panoyla iletişim dosya üzerinden olur:

    <durum_dizini>/komut        bu yardımcı yazar, pano okur
    <durum_dizini>/durum.json   pano yazar, bu yardımcı ipucu için okur

Çalıştırma:  python3 -m syspano.tepsi
"""

import json
import os
import subprocess
import sys
import time

from . import ayar as ayar_mod, ortam

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
except Exception:                                     # PySide6 yok
    QApplication = None


def yollar():
    d = ortam.emin_ol(ortam.durum_dizini())
    return os.path.join(d, "komut"), os.path.join(d, "durum.json")


def komut_gonder(metin, komut_yolu=None):
    komut_yolu = komut_yolu or yollar()[0]
    try:
        with open(komut_yolu + ".tmp", "w") as f:
            f.write(metin)
        os.replace(komut_yolu + ".tmp", komut_yolu)
    except Exception as hata:
        print("komut yazılamadı:", hata, flush=True)


def durum_oku(durum_yolu=None):
    durum_yolu = durum_yolu or yollar()[1]
    try:
        with open(durum_yolu) as f:
            d = json.load(f)
        if time.time() - d.get("zaman", 0) > 15:
            return None
        return d
    except Exception:
        return None


def _pano_baslat():
    """Panoyu yeni bir süreçte başlatır."""
    try:
        subprocess.Popen([sys.executable, "-m", "syspano"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception as hata:
        print("başlatılamadı:", hata, flush=True)


def simge_ciz():
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor("#0f1116"))
    p.setBrush(QColor("#3daee9"))
    p.drawRoundedRect(3, 7, 58, 42, 7, 7)
    p.setBrush(QColor("#0f1116"))
    p.drawRoundedRect(9, 13, 46, 30, 4, 4)
    for i, renk in enumerate(("#27ae60", "#f0c040", "#da4453")):
        p.setBrush(QColor(renk))
        p.drawRect(14 + i * 11, 28 - i * 5, 7, 11 + i * 5)
    p.setBrush(QColor("#8b93a7"))
    p.drawRect(26, 50, 12, 5)
    p.end()
    return pm


class Tepsi:
    def __init__(self):
        if QApplication is None:
            raise RuntimeError("PySide6 kurulu değil")
        self.ayar = ayar_mod.oku()
        self.ad = self.ayar.get("uygulama_basligi", "SysPano")
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(self.ad)
        self.app.setQuitOnLastWindowClosed(False)

        self.simge = QSystemTrayIcon(QIcon(simge_ciz()))
        self.simge.setToolTip(f"{self.ad} panosu")

        menu = QMenu()
        self.a_goster = menu.addAction("Panoyu gizle")
        self.a_goster.triggered.connect(lambda: komut_gonder("degistir_gorunurluk"))
        menu.addSeparator()
        self.a_pano = menu.addAction("Sistem panosu")
        self.a_pano.triggered.connect(lambda: komut_gonder("gorunum:pano"))
        self.a_term = menu.addAction("Terminal")
        self.a_term.triggered.connect(lambda: komut_gonder("gorunum:terminal"))
        menu.addSeparator()
        yazi = menu.addMenu("Terminal yazı boyutu")
        yazi.addAction("Büyüt  (Ctrl +)").triggered.connect(lambda: komut_gonder("yazi:+"))
        yazi.addAction("Küçült (Ctrl −)").triggered.connect(lambda: komut_gonder("yazi:-"))
        yazi.addAction("Varsayılan").triggered.connect(lambda: komut_gonder("yazi:0"))
        menu.addSeparator()
        self.a_baslat = menu.addAction("Panoyu başlat")
        self.a_baslat.triggered.connect(_pano_baslat)
        menu.addSeparator()
        menu.addAction("Çıkış").triggered.connect(self.cikis)
        self.simge.setContextMenu(menu)
        self.simge.activated.connect(self.tiklandi)
        self.simge.show()

        self.zamanlayici = QTimer()
        self.zamanlayici.timeout.connect(self.durum_guncelle)
        self.zamanlayici.start(2000)
        self.durum_guncelle()

    def tiklandi(self, neden):
        if neden in (QSystemTrayIcon.Trigger, QSystemTrayIcon.MiddleClick):
            komut_gonder("degistir_gorunurluk")

    def durum_guncelle(self):
        d = durum_oku()
        if not d:
            if self.a_goster.text() != "Panoyu başlat":
                try:
                    self.a_goster.triggered.disconnect()
                except Exception:
                    pass
                self.a_goster.setText("Panoyu başlat")
                self.a_goster.triggered.connect(_pano_baslat)
            self.simge.setToolTip(f"{self.ad} panosu çalışmıyor — başlatmak için tıklayın")
            return
        if self.a_goster.text() == "Panoyu başlat":
            try:
                self.a_goster.triggered.disconnect()
            except Exception:
                pass
            self.a_goster.triggered.connect(lambda: komut_gonder("degistir_gorunurluk"))
            self.a_goster.setText("Panoyu gizle")
        self.a_goster.setText("Panoyu gizle" if d.get("gorunur") else "Panoyu göster")
        self.a_pano.setEnabled(d.get("gorunum") != "pano")
        self.a_term.setEnabled(d.get("gorunum") != "terminal")
        self.simge.setToolTip(
            f"{self.ad}\n"
            f"CPU %{d.get('cpu', 0):.0f} · {d.get('sicaklik', 0):.0f}°C · "
            f"bellek %{d.get('bellek', 0):.0f} · pil %{d.get('pil', 0):.0f}\n"
            f"görünüm: {'terminal' if d.get('gorunum') == 'terminal' else 'sistem panosu'}"
            f" · yazı {d.get('yazi', 0)} px")

    def cikis(self):
        komut_gonder("cikis")
        QTimer.singleShot(600, self.app.quit)


def main():
    if QApplication is None:
        print("Hata: tepsi simgesi için PySide6 gerekir.\n"
              "  pip install PySide6    ya da    sudo apt install python3-pyside6.qtwidgets",
              file=sys.stderr)
        return 2
    t = Tepsi()
    return t.app.exec()


if __name__ == "__main__":
    sys.exit(main())
