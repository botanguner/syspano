"""Disk: kök dosya sisteminin doluluğu ve kök disk üzerindeki okuma/yazma hızı."""

import os
import shutil

from . import ortak


def kok_disk():
    """Kök dosya sisteminin bulunduğu diski (NVMe/SSD/MMC) bulur.

    İki yol denenir: (1) /proc/self/mountinfo → major:minor → /sys/dev/block,
    (2) mountinfo'nun aygıt alanı (/dev/nvme0n1p6 gibi) → bölüm adından tam disk.
    Böylece nvme0n1, sda, mmcblk0 gibi her cihazda ve btrfs gibi sanal
    major:minor kullanan dosya sistemlerinde de doğru çalışır.
    """
    try:
        with open("/proc/self/mountinfo") as f:
            for satir in f:
                p = satir.split()
                if len(p) <= 4 or p[4] != "/":
                    continue
                # (1) major:minor → gerçek aygıt
                maj, mi = p[2].split(":")
                bag = f"/sys/dev/block/{maj}:{mi}"
                if os.path.exists(bag):
                    yol = os.path.realpath(bag)
                    if "/block/" in yol and yol != bag:
                        return yol.split("/block/")[1].split("/")[0]
                # (2) aygıt dosyası (/dev/nvme0n1p6) → tam disk adı
                if " - " in satir:
                    sonrasi = satir.split(" - ", 1)[1].split()
                    if len(sonrasi) >= 2 and sonrasi[1].startswith("/dev/"):
                        return _tam_disk(os.path.basename(sonrasi[1]))
    except Exception:
        pass
    return None


def _tam_disk(ad):
    """Bölüm adını tam disk adına çevirir: nvme0n1p6→nvme0n1, sda3→sda."""
    if not ad:
        return None
    if os.path.exists(f"/sys/block/{ad}"):
        return ad
    kesik = ad
    while kesik and kesik[-1].isdigit():
        kesik = kesik[:-1]
    if kesik.endswith("p") and os.path.exists(f"/sys/block/{kesik[:-1]}"):
        return kesik[:-1]
    return kesik if os.path.exists(f"/sys/block/{kesik}") else (ad or None)


def _model(disk):
    for yol in (f"/sys/block/{disk}/device/model", f"/sys/block/{disk}/device/name"):
        m = ortak.oku(yol)
        if m:
            return m
    return disk or "disk"


def oku(d, ayar):
    if not d.kok_disk_arandi:
        d.kok_disk = kok_disk()
        d.kok_disk_arandi = True

    try:
        alan = shutil.disk_usage("/")
    except Exception:
        return {"yok": True}

    okuma = yazma = 0.0
    anlik = None
    disk = d.kok_disk
    if disk:
        try:
            with open("/proc/diskstats") as f:
                for satir in f:
                    p = satir.split()
                    if len(p) > 9 and p[2] == disk:
                        anlik = {"okuma": int(p[5]), "yazma": int(p[9])}
                        break
        except Exception:
            anlik = None

    simdi = ortak.zaman()
    if anlik and d.disk_onceki:
        dt = simdi - d.disk_onceki[1]
        if dt > 0:
            okuma = max(0.0, (anlik["okuma"] - d.disk_onceki[0]["okuma"]) * 512 / dt / 1e6)
            yazma = max(0.0, (anlik["yazma"] - d.disk_onceki[0]["yazma"]) * 512 / dt / 1e6)
    if anlik:
        d.disk_onceki = (anlik, simdi)

    return {
        "okuma": okuma, "yazma": yazma,
        "dolu": 100.0 * alan.used / alan.total,
        "bos_gb": alan.free / 1e9,
        "toplam_gb": alan.total / 1e9,
        "aygit": disk or "-",
        "model": _model(disk),
    }
