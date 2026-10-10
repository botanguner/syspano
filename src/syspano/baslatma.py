"""Panoyu başlatma yöntemi: oturum açılışı, systemd kullanıcı servisi ya da elle.

Ayar ekranındaki **BAŞLATMA** bölümü bu modülü kullanır: geçerli yöntemi ve
servisin durumunu gösterir, servis kurulu değilse kurmayı, kuruluysa
başlatmayı/durdurmayı/yeniden başlatmayı sağlar.

Durum sorgusu `systemctl --user` çağırır (süreç başlatır), bu yüzden
`SORGU_ARALIK` boyunca önbelleğe alınır — ayar ekranı saniyede bir çizilse bile
her karede systemctl çağrılmaz.
"""

import os
import subprocess
import time

SORGU_ARALIK = 5.0        # saniye; systemctl durumu bu aralıkta tazelenir
BIRIM_ADI = "syspano.service"

_onbellek = {"zaman": 0.0, "sonuc": {}}


def _calistir(komut, zaman=8):
    try:
        c = subprocess.run(komut, capture_output=True, text=True, timeout=zaman)
        return c.returncode, (c.stdout or "").strip()
    except Exception:
        return 1, ""


def _ev():
    return os.path.expanduser("~")


def birim_yolu():
    return os.path.join(_ev(), ".config/systemd/user", BIRIM_ADI)


def oturum_girdisi():
    """Oturum açılışı girdisinin yolu (XDG masaüstü) ya da None."""
    adaylar = (os.path.join(_ev(), ".config/autostart/syspano.desktop"),)
    for yol in adaylar:
        if os.path.exists(yol):
            return yol
    return None


def labwc_bekci():
    """labwc autostart dosyasında bekçi satırı var mı? (Raspberry Pi düzeni)"""
    yol = os.path.join(_ev(), ".config/labwc/autostart")
    try:
        with open(yol) as f:
            return any("--bekci" in s for s in f)
    except Exception:
        return False


def servis_durum(taze=False):
    """systemd kullanıcı servisinin durumu (önbellekli).

    Dönen: {"kurulu", "etkin", "durum", "pid", "aciklama"}
    """
    simdi = time.monotonic()
    if (not taze and _onbellek["sonuc"]
            and simdi - _onbellek["zaman"] < SORGU_ARALIK):
        return _onbellek["sonuc"]

    kurulu = os.path.exists(birim_yolu())
    if not kurulu:
        # kurulu olmayabilir ama sistem geneli bir birim olabilir
        kod, _ = _calistir(["systemctl", "--user", "cat", BIRIM_ADI])
        kurulu = kod == 0
    durum, pid = "bilinmiyor", None
    if kurulu:
        kod, cikti = _calistir(["systemctl", "--user", "is-active", BIRIM_ADI])
        durum = cikti.splitlines()[0].strip() if cikti else "inactive"
        if durum != "active":
            kod, cikti = _calistir(["systemctl", "--user", "is-failed", BIRIM_ADI])
            if cikti.startswith("failed"):
                durum = "failed"
        kod, cikti = _calistir(["systemctl", "--user", "show", BIRIM_ADI,
                                "-p", "MainPID", "--value"])
        try:
            pid = int(cikti) or None
        except Exception:
            pid = None
    sonuc = {"kurulu": kurulu, "durum": durum, "pid": pid,
             "etkin": durum == "active"}
    _onbellek.update({"zaman": simdi, "sonuc": sonuc})
    return sonuc


def durum_metni():
    """Ayar ekranındaki durum satırı: (metin, renk anahtarı, eylemler)."""
    servis = servis_durum()
    girdi = oturum_girdisi()
    bekci = labwc_bekci()

    if servis["kurulu"]:
        renk = {"active": "yesil", "failed": "kirmizi"}.get(servis["durum"], "sari")
        ek = f" · pid {servis['pid']}" if servis.get("pid") else ""
        metin = f"Başlatma: systemd kullanıcı servisi · {servis['durum']}{ek}"
        eylemler = ["servis_yeniden"]
        eylemler.append("servis_durdur" if servis["etkin"] else "servis_baslat")
        return metin, renk, eylemler

    if girdi or bekci:
        nerede = "oturum açılışı" + (" + bekçi" if bekci else "")
        return (f"Başlatma: {nerede} (masaüstü)", "yesil", ["servis_kur"])
    return ("Başlatma: elle — otomatik başlatma kurulu değil", "soluk", ["servis_kur"])


def birim_icerigi(komut=None, bekci=False):
    """systemd kullanıcı birim dosyasının içeriği.

    `komut` verilmezse bu Python yorumlayıcısıyla `-m syspano` kullanılır
    (pip/pipx kurulumunda da, depodan çalıştırmada da doğru olan yol).
    """
    import sys as _sys
    calistir = komut or f"{_sys.executable} -m syspano"
    if bekci and "--bekci" not in calistir:
        calistir += " --bekci"
    return (f"[Unit]\n"
            f"Description=SysPano sistem ve kaynak izleme panosu\n"
            f"Documentation=https://github.com/botanguner/syspano\n"
            f"After=graphical-session.target\n"
            f"PartOf=graphical-session.target\n\n"
            f"[Service]\n"
            f"Type=simple\n"
            f"ExecStart={calistir}\n"
            f"Restart=on-failure\n"
            f"RestartSec=5\n\n"
            f"[Install]\n"
            f"WantedBy=graphical-session.target\n")


def pi_mi():
    try:
        with open("/proc/device-tree/model") as f:
            return "raspberry" in f.read().lower()
    except Exception:
        return False


def servis_kur(komut=None):
    """Birimi yazar, etkinleştirir ve başlatır: (basarili, mesaj).

    Oturum açılışı girdisi varsa (**çift pano olmasın** diye) kapatılır.
    """
    yol = birim_yolu()
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w") as f:
            f.write(birim_icerigi(komut, bekci=pi_mi()))
    except Exception as hata:
        return False, f"birim yazılamadı: {hata}"
    # çift başlatmayı önle
    girdi = oturum_girdisi()
    if girdi:
        try:
            with open(girdi) as f:
                icerik = f.read()
            if "Hidden=false" in icerik:
                with open(girdi, "w") as f:
                    f.write(icerik.replace("Hidden=false", "Hidden=true"))
        except Exception:
            pass
    kod, _ = _calistir(["systemctl", "--user", "daemon-reload"])
    kod2, _ = _calistir(["systemctl", "--user", "enable", "--now", BIRIM_ADI], 20)
    _onbellek["zaman"] = 0.0
    if kod2 == 0:
        return True, "Servis kuruldu ve başlatıldı"
    return False, ("Birim yazıldı ama servis başlatılamadı "
                   "(journalctl --user -u syspano)")


def servis_eylemi(eylem):
    """`baslat` · `durdur` · `yeniden` · `kapat` — systemctl --user çağrısı."""
    esleme = {"baslat": "start", "durdur": "stop", "yeniden": "restart"}
    if eylem not in esleme:
        return False, f"bilinmeyen eylem: {eylem}"
    komut = ["systemctl", "--user", esleme[eylem], BIRIM_ADI]
    if eylem == "durdur":
        komut += ["--no-block"]      # bizi öldürecek olsa da komut dönsün
    kod, cikti = _calistir(komut, 20)
    _onbellek["zaman"] = 0.0
    if kod == 0:
        return True, {"baslat": "Servis başlatıldı",
                      "durdur": "Servis durduruldu",
                      "yeniden": "Servis yeniden başlatıldı"}[eylem]
    return False, f"systemctl hatası: {cikti[:80] or 'bilinmiyor'}"
