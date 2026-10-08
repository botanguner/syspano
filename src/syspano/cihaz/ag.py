"""Ağ: varsayılan arayüz üzerinden indirme/yükleme hızı, yerel IP, arayüz türü.

**Performans notu:** Wi-Fi sinyal gücünü okumak (`/proc/net/wireless`) Raspberry
Pi'de **~1,8 ms** sürüyor — Wi-Fi sürücüsü her okumada firmware'e soruyor ve bu
değer arayüzde hiç gösterilmiyordu. Bu yüzden okuma kaldırıldı; sinyal göstermek
istenirse yavaş sensörlerdeki gibi seyreltilerek eklenmelidir. Aynı gerekçeyle
arayüzün bağlantı hızı (`/sys/class/net/*/speed`) da okunmuyor: saniyede bir
yapılan ve hiç gösterilmeyen bir okumaydı. Kartta yalnızca gösterilen alanlar
toplanır; yeni bir alan eklenirse karta da eklenmelidir.
"""

import fcntl
import os
import socket
import struct

from . import ortak

# panoya hiç girmemesi gereken sanal arayüzler
_SANAL = ("lo", "docker", "veth", "br-", "virbr", "tun", "tap", "wg", "zt", "vboxnet")


def _varsayilan_arayuz():
    """IPv4 varsayılan yolu (en düşük metrik)."""
    en_iyi, metrik = None, 1 << 30
    try:
        with open("/proc/net/route") as f:
            next(f)
            for satir in f:
                p = satir.split()
                if len(p) > 7 and p[1] == "00000000" and int(p[7], 16) & 2:
                    if int(p[6]) < metrik:
                        en_iyi, metrik = p[0], int(p[6])
    except Exception:
        pass
    if en_iyi:
        return en_iyi
    # yönlendirme yok: çalışan ilk gerçek arayüz
    try:
        for ad in sorted(os.listdir("/sys/class/net")):
            if any(ad.startswith(s) for s in _SANAL):
                continue
            if ortak.oku(f"/sys/class/net/{ad}/operstate") in ("up", "unknown"):
                return ad
    except Exception:
        pass
    return None


def _ip(arayuz):
    """SIOCGIFADDR ile IPv4 adresi."""
    if not arayuz:
        return "-"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        paket = struct.pack("256s", arayuz.encode()[:15])
        adres = fcntl.ioctl(s.fileno(), 0x8915, paket)   # SIOCGIFADDR
        return socket.inet_ntoa(adres[20:24])
    except Exception:
        return "-"
    finally:
        s.close()


def oku(d, ayar):
    if not d.ag_arandi:
        d.ag_arayuz = _varsayilan_arayuz()
        d.ag_arandi = True
    arayuz = d.ag_arayuz
    if not arayuz:
        return {"yok": True}

    rx = ortak.oku_sayi(f"/sys/class/net/{arayuz}/statistics/rx_bytes", -1)
    tx = ortak.oku_sayi(f"/sys/class/net/{arayuz}/statistics/tx_bytes", -1)
    if rx < 0:
        return {"yok": True}

    inen = giden = 0.0
    simdi = ortak.zaman()
    if d.ag_onceki:
        onc_rx, onc_tx, onc_zaman = d.ag_onceki
        dt = simdi - onc_zaman
        if dt > 0:
            inen = max(0.0, (rx - onc_rx) / dt / 1024.0)   # KB/sn
            giden = max(0.0, (tx - onc_tx) / dt / 1024.0)
    d.ag_onceki = (rx, tx, simdi)

    tur = "wifi" if (arayuz.startswith(("wl", "wlan")) or
                     os.path.isdir(f"/sys/class/net/{arayuz}/wireless")) else "ethernet"
    return {
        "arayuz": arayuz,
        "inen": inen, "giden": giden,
        "toplam_in": rx, "toplam_out": tx,
        "ip": _ip(arayuz),
        "tur": tur,
    }
