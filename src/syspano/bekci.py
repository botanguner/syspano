"""Pano bekçisi: donan ya da ölen panoyu kendiliğinden geri getirir.

Gözetimsiz çalışan panolarda (Raspberry Pi kiosk gibi) pano donabilir — ekran
kımıldamaz, süreç yaşıyordur — ya da çökebilir. Bekçi üç iş yapar:

1. **Pano yoksa başlatır.** Açılışta Xwayland/Tk henüz hazır değilse pano
   ölebilir; bekçi her turda yeniden dener, bu yüzden yarış koşullarına dayanır.
2. **Kalp atışı bayatlarsa öldürür.** Pano 3 saniyede bir
   `$XDG_RUNTIME_DIR/syspano/durum.json` yazar (tepsi iletişimi için zaten
   yazıyor). Bu dosyanın yaşı `--bekci-esik` saniyeyi geçtiyse pano donmuş
   sayılır ve `SIGTERM` → (gerekirse) `SIGKILL` ile öldürülür; bir sonraki turda
   yeniden başlatılır.
3. **Öldürmeden önce tanı kaydı yazar** (süreç durumu, beklediği çekirdek
   fonksiyonu, kalp yaşı) — böylece donma sonradan incelenebilir.

Kullanım::

    syspano --bekci                     # aralık 20 sn, eşik 90 sn
    syspano --bekci --bekci-esik 45     # daha sabırsız bekçi
    syspano --bekci --bekci-kuru        # hiçbir şey başlatmaz/öldürmez, yalnız yazar

Raspberry Pi'de oturum açılışına eklemek için `~/.config/labwc/autostart`
dosyasına şu satır yeterlidir::

    /home/botan/.local/bin/syspano --bekci &
"""

import os
import signal
import subprocess
import sys
import time

from . import ortam

VARSAYILAN_ARALIK = 20.0
VARSAYILAN_ESIK = 90.0
KALP_ARALIK = 3.0          # pano bu aralıkta yazar (bkz. pano._durum_yaz)
BASLANGIC_TOLERANS = 15.0  # yeni başlayan panoya tanınan süre (ilk kalp atışı için)


def kalp_yolu():
    return os.path.join(ortam.durum_dizini(), "durum.json")


def gunluk_yolu():
    """Pano ve bekçi günlüğü (kalıcı durum dizininde)."""
    return os.path.join(ortam.kalici_durum_dizini(), "pano.log")


def kalp_yasi(simdi=None):
    """Kalp atışı dosyasının yaşı (saniye); dosya yoksa None."""
    simdi = time.time() if simdi is None else simdi
    try:
        return max(0.0, simdi - os.path.getmtime(kalp_yolu()))
    except OSError:
        return None


def karar(surec_var, kalp_yasi_sn, esik=None, surec_yasi_sn=None, tolerans=None):
    """Bekçinin kararı: `"baslat"` | `"oldur"` | `"bekle"` (saf fonksiyon).

    `surec_yasi_sn` verilirse ve süreç `tolerans` saniyeden gençse **öldürülmez**:
    yeni başlayan pano henüz ilk kalp atışını yazmamış olabilir. Bu tolerans
    olmadan bekçi, eski kalp atışını görüp yeni panoyu hemen öldürüyordu
    (Raspberry Pi'de denendi: 1 saniyelik pano "donmuş" sayıldı).
    """
    esik = VARSAYILAN_ESIK if esik is None else float(esik)
    tolerans = BASLANGIC_TOLERANS if tolerans is None else float(tolerans)
    if not surec_var:
        return "baslat"
    if surec_yasi_sn is not None and float(surec_yasi_sn) < tolerans:
        return "bekle"
    if kalp_yasi_sn is not None and float(kalp_yasi_sn) > esik:
        return "oldur"
    return "bekle"


def surec_yasi(pid, simdi=None):
    """Sürecin yaşı (saniye): /proc/<pid>/stat alan 22 + /proc/uptime."""
    try:
        with open(f"/proc/{int(pid)}/stat") as f:
            icerik = f.read()
        alanlar = icerik.rsplit(") ", 1)[1].split()      # comm'u ayır
        baslangic_tik = int(alanlar[19])                 # alan 22
        with open("/proc/uptime") as f:
            sistem_yasi = float(f.read().split()[0])
        hz = os.sysconf("SC_CLK_TCK") or 100
        return max(0.0, sistem_yasi - baslangic_tik / hz)
    except Exception:
        return None


def _cmdline(pid):
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
            return [p.decode("utf-8", "replace")
                    for p in f.read().split(b"\0") if p]
    except Exception:
        return []


def eslesme(argumanlar):
    """Bu komut satırı bir **pano** süreci mi? (saf fonksiyon)"""
    if not argumanlar:
        return False
    if any("bekci" in a or a.endswith("syspano.tepsi") or a.endswith("tepsi.py")
           for a in argumanlar):
        return False                       # bekçinin kendisi ya da tepsi
    for a in argumanlar:
        if a == "syspano" or a.endswith("/syspano") or a.endswith("syspano/__main__.py"):
            return True
    return False


def pano_pid(haric=()):
    """Çalışan pano sürecinin PID'i (yoksa None). /proc taranır."""
    haric = set(haric) | {os.getpid()}
    try:
        pidler = sorted(int(p) for p in os.listdir("/proc") if p.isdigit())
    except Exception:
        return None
    for pid in pidler:
        if pid in haric:
            continue
        if eslesme(_cmdline(pid)):
            return pid
    return None


def _log(satir, yol=None):
    yol = yol or gunluk_yolu()
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} bekçi: {satir}\n")
    except Exception:
        pass


def baslat(yol=None):
    """Panoyu ayrı bir oturumda başlatır (bekçi ölse de pano yaşasın)."""
    hedef = os.path.expanduser(yol or gunluk_yolu())
    try:
        os.makedirs(os.path.dirname(hedef), exist_ok=True)
        kayit = open(hedef, "a")
    except Exception:
        kayit = None
    try:
        surec = subprocess.Popen([sys.executable, "-m", "syspano"],
                                 stdout=kayit or subprocess.DEVNULL,
                                 stderr=subprocess.STDOUT if kayit else subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        return surec.pid
    except Exception as hata:
        _log(f"pano başlatılamadı: {hata}")
        return None


def tani(pid):
    """Donan süreç için kısa tanı: durum, beklediği yer, son kalp yaşı."""
    parcalar = [f"pid {pid}"]
    try:
        with open(f"/proc/{pid}/status") as f:
            for satir in f:
                if satir.startswith(("State:", "Threads:")):
                    parcalar.append(satir.strip())
    except Exception:
        pass
    try:
        with open(f"/proc/{pid}/wchan") as f:
            parcalar.append("wchan " + f.read().strip())
    except Exception:
        pass
    yas = kalp_yasi()
    parcalar.append(f"kalp yaşı {yas:.0f} sn" if yas is not None else "kalp yok")
    return " · ".join(parcalar)


def oldur(pid, zaman_asimi=8.0):
    """Donmuş panoyu nazikçe sonlandırır; gerekirse zorlar."""
    _log(f"pano donmuş görünüyor → sonlandırılıyor · {tani(pid)}")
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception as hata:
        _log(f"SIGTERM gönderilemedi: {hata}")
        return False
    bitis = time.time() + zaman_asimi
    while time.time() < bitis:
        if not os.path.exists(f"/proc/{pid}"):
            _log("pano kapandı (SIGTERM)")
            return True
        time.sleep(0.3)
    try:
        os.kill(pid, signal.SIGKILL)
        _log("pano SIGKILL ile kapatıldı")
        return True
    except Exception as hata:
        _log(f"SIGKILL gönderilemedi: {hata}")
        return False


def dongu(aralik=None, esik=None, kuru=False, tur_sayisi=None):
    """Bekçi döngüsü. `tur_sayisi` verilirse o kadar tur döner (test için)."""
    aralik = VARSAYILAN_ARALIK if aralik is None else float(aralik)
    esik = VARSAYILAN_ESIK if esik is None else float(esik)
    tur = 0
    son_karar = "bekle"
    while tur_sayisi is None or tur < tur_sayisi:
        tur += 1
        pid = pano_pid()
        son_karar = karar(pid is not None, kalp_yasi(), esik,
                          surec_yasi(pid) if pid else None)
        if son_karar == "baslat":
            if kuru:
                _log("pano yok (kuru çalıştırma: başlatılmadı)")
            else:
                yeni = baslat()
                _log(f"pano başlatıldı (pid {yeni})" if yeni else "pano başlatılamadı")
        elif son_karar == "oldur":
            if kuru:
                _log(f"pano donmuş (kuru çalıştırma: öldürülmedi) · {tani(pid)}")
            else:
                oldur(pid)
        if tur_sayisi is not None:
            break
        time.sleep(aralik)
    return son_karar
