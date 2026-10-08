"""Çalışma ortamını algılar: oturum tipi, pencere yöneticisi, yollar.

Farklı dağıtımlarda ve masaüstlerinde (KDE, GNOME, Xfce, labwc/sway, saf X11)
doğru davranmak için gereken bilgiler burada toplanır.
"""

import os
import shutil
import subprocess

# ─── komut var mı ────────────────────────────────────────────────────────────
def komut_var(ad):
    return shutil.which(ad) is not None


def komut(cmd, zaman=4):
    """Komutu çalıştırır, stdout döndürür (hata/eksik komutta '')."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=zaman).stdout
    except Exception:
        return ""


def ansi_temizle(metin):
    import re
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", metin or "")


# ─── oturum / masaüstü ───────────────────────────────────────────────────────
def oturum_tipi():
    """'wayland' | 'x11' | 'bilinmiyor'."""
    t = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
    if t in ("wayland", "x11"):
        return t
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "bilinmiyor"


def masaustu():
    """Masaüstü ortamının adı (kde, gnome, xfce, lxqt, sway, labwc, ...)."""
    for d in (os.environ.get("XDG_CURRENT_DESKTOP", ""),
              os.environ.get("XDG_SESSION_DESKTOP", ""),
              os.environ.get("DESKTOP_SESSION", "")):
        if d:
            return d.split(":")[0].strip().lower()
    return ""


def kwin_var():
    """KWin çalışıyor mu (KDE)? Pencere yerleştirme betiği buna bağlı."""
    if masaustu() == "kde":
        return True
    return komut_var("qdbus-qt6") and bool(komut(
        ["qdbus-qt6", "org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure"],
        zaman=2)) or bool(komut(["qdbus-qt6", "org.kde.KWin"], zaman=2))


def xwayland_var():
    """X11 (Xwayland) erişimi var mı? Tkinter bunu gerektirir."""
    return bool(os.environ.get("DISPLAY"))


# ─── yollar ──────────────────────────────────────────────────────────────────
def yapilandirma_dizini():
    return os.environ.get(
        "SYSPANO_YAPILANDIRMA_DIZINI",
        os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                     "syspano"))


def durum_dizini():
    """Geçici çalışma dosyaları (tepsi ↔ pano iletişimi)."""
    kok = os.environ.get("XDG_RUNTIME_DIR")
    if kok and os.path.isdir(kok):
        return os.path.join(kok, "syspano")
    return os.path.join("/tmp", f"syspano-{os.getuid()}")


def veri_dizini():
    return os.path.join(
        os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "syspano")


def emin_ol(yol):
    try:
        os.makedirs(yol, exist_ok=True)
    except Exception:
        pass
    return yol


# ─── sistem bilgisi ──────────────────────────────────────────────────────────
def dagitim():
    """Dağıtım adı: 'Fedora Linux 44', 'Debian GNU/Linux 12', 'Raspberry Pi OS' vb."""
    try:
        with open("/etc/os-release") as f:
            d = {}
            for satir in f:
                if "=" in satir:
                    k, v = satir.rstrip().split("=", 1)
                    d[k] = v.strip('"')
        ad = d.get("NAME") or d.get("ID") or "Linux"
        surum = d.get("VERSION_ID") or ""
        return f"{ad} {surum}".strip()
    except Exception:
        return "Linux"


def makine_modeli():
    """Cihaz modeli: /sys/firmware/devicetree (ARM) veya /sys/class/dmi (x86)."""
    for yol in ("/sys/firmware/devicetree/base/model",
                "/sys/firmware/devicetree/base/compatible"):
        try:
            with open(yol, "rb") as f:
                metin = f.read().decode("utf-8", "ignore").strip("\x00").strip()
            if metin:
                return metin.split("\x00")[0]
        except Exception:
            pass
    for yol in ("/sys/devices/virtual/dmi/id/product_name",
                "/sys/class/dmi/id/product_name"):
        try:
            with open(yol) as f:
                metin = f.read().strip()
            if metin and metin not in ("System Product Name", "To Be Filled By O.E.M."):
                return metin
        except Exception:
            pass
    return ""


def islemci_adi():
    """/proc/cpuinfo'dan okunabilir işlemci adı. Önce 'model name' aranır
    (x86); yoksa ARM/SoC alanları ('Hardware', 'cpu model') denenir."""
    try:
        with open("/proc/cpuinfo") as f:
            satirlar = f.read().splitlines()
    except Exception:
        return ""
    for anahtar in ("model name", "cpu model", "hardware", "processor"):
        for satir in satirlar:
            if satir.lower().startswith(anahtar) and ":" in satir:
                deger = satir.split(":", 1)[1].strip()
                if deger and not deger.isdigit():
                    return deger
    return ""
