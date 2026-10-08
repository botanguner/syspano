"""GPU: Intel, AMD, NVIDIA ve Raspberry Pi (VideoCore) desteklenir.

Her üretici için farklı sysfs düğümleri vardır:

| Üretici | Kullanım | Frekans | Sıcaklık |
|---|---|---|---|
| Intel   | RC6 sayacı farkı | `gt_cur_freq_mhz` | hwmon (coretemp/pch) |
| AMD     | `gpu_busy_percent` | `pp_dpm_sclk` | `device/hwmon/*/temp1_input` |
| NVIDIA  | `nvidia-smi` | `clocks.sm` | `nvidia-smi` |
| VideoCore (Pi) | — | `v3d` saati | `vcgencmd measure_temp` |

Hiçbir GPU bulunamazsa `{"yok": True}` döner ve arayüz GPU kartını gizler.
"""

import glob
import os
import re
import subprocess

from . import ortak

_URETICI = {
    "0x8086": "Intel", "0x1002": "AMD", "0x10de": "NVIDIA",
    "0x14e4": "Broadcom", "0x1af4": "virtio", "0x106b": "Apple", "0x1234": "QEMU",
}
_ATLA = ("vkms", "vgem", "simpledrm", "virtio_gpu")


def _surucu(yol):
    try:
        return os.path.basename(os.path.realpath(f"{yol}/device/driver"))
    except Exception:
        return ""


def _uretim(yol):
    v = ortak.oku(f"{yol}/device/vendor")
    return _URETICI.get(v, "GPU")


def gpu_kartlari(d):
    """Sysfs'ten bulunan GPU kartları (Intel/AMD/VideoCore)."""
    kartlar = []
    for giris in sorted(os.listdir("/sys/class/drm")):
        m = re.fullmatch(r"card(\d+)", giris)
        if not m:
            continue
        yol = f"/sys/class/drm/{giris}"
        surucu = _surucu(yol)
        if surucu in _ATLA:
            continue
        uretim = _uretim(yol)
        kart = {"ad": giris, "surucu": surucu, "uretim": uretim,
                "kullanim": None, "mhz": 0.0, "maks_mhz": 0.0, "sicaklik": 0.0}

        if uretim == "AMD":
            kart["kullanim"] = ortak.oku_sayi(f"{yol}/device/gpu_busy_percent", -1)
            if kart["kullanim"] < 0:
                kart["kullanim"] = None
            kart["bellek_yuzde"] = ortak.oku_sayi(f"{yol}/device/mem_busy_percent", -1)
            mhz = re.search(r"(\d+)Mhz", ortak.oku(f"{yol}/device/pp_dpm_sclk", "") or "")
            if mhz:
                kart["mhz"] = float(mhz.group(1))
            hw = glob.glob(f"{yol}/device/hwmon/hwmon*/temp1_input")
            if hw:
                kart["sicaklik"] = ortak.oku_sayi(hw[0], 0) / 1000.0
            kart["model"] = f"AMD {surucu}"
        elif uretim == "Intel" or os.path.exists(f"{yol}/gt_cur_freq_mhz"):
            kart["uretim"] = uretim if uretim == "Intel" else (uretim or "Intel")
            kart["mhz"] = ortak.oku_sayi(f"{yol}/gt_cur_freq_mhz")
            kart["maks_mhz"] = (ortak.oku_sayi(f"{yol}/gt_RP0_freq_mhz")
                                or ortak.oku_sayi(f"{yol}/gt_max_freq_mhz"))
            rc6 = ortak.oku_sayi(f"{yol}/power/rc6_residency_ms", -1)
            kart["kullanim"] = _rc6_mesgul(d, giris, rc6)
            kart["model"] = f"Intel {surucu}"
        else:
            # bilinmeyen: devfreq ya da gt_* varsa kullan
            mhz = ortak.oku_sayi(f"{yol}/gt_cur_freq_mhz")
            if mhz:
                kart["mhz"] = mhz
            kart["model"] = f"{uretim or 'GPU'} {surucu}".strip()

        # kartı gerçek sayanlar
        if kart["mhz"] or kart["kullanim"] is not None or kart["sicaklik"]:
            kartlar.append(kart)

    # Raspberry Pi / VideoCore
    if ortam_komut("vcgencmd"):
        v = _vcgencmd()
        if v:
            kartlar.append(v)
    return kartlar


def _rc6_mesgul(d, ad, rc6):
    """Intel GPU meşguliyeti: RC6 (boşta) sayacı farkından."""
    simdi = ortak.zaman()
    mesgul = None
    if rc6 >= 0 and d.rc6_onceki.get(ad):
        onc, zaman = d.rc6_onceki[ad]
        dr, dt = rc6 - onc, (simdi - zaman) * 1000
        if dt > 0:
            mesgul = max(0.0, min(100.0, 100.0 * (1 - dr / dt)))
    if rc6 >= 0:
        d.rc6_onceki[ad] = (rc6, simdi)
    return mesgul


def ortam_komut(ad):
    import shutil
    return shutil.which(ad) is not None


def _vcgencmd():
    try:
        mhz = subprocess.run(["vcgencmd", "measure_clock", "v3d"],
                             capture_output=True, text=True, timeout=3).stdout
        t = subprocess.run(["vcgencmd", "measure_temp"],
                           capture_output=True, text=True, timeout=3).stdout
        m = re.search(r"=(\d+)", mhz)
        tt = re.search(r"([\d.]+)", t)
        return {"ad": "v3d", "surucu": "v3d", "uretim": "Broadcom",
                "kullanim": None,
                "mhz": (int(m.group(1)) / 1e6) if m else 0.0,
                "maks_mhz": 0.0,
                "sicaklik": float(tt.group(1)) if tt else 0.0,
                "model": "VideoCore (RPi)"}
    except Exception:
        return None


# ─── NVIDIA (nvidia-smi) ─────────────────────────────────────────────────────
def nvidia_oku(d):
    """NVIDIA'nın gerçek durumunu okur; yoksa None.

    Anlık kullanım çoğu zaman %0 olduğu için son 30 saniyenin tepesi ve pstate
    (P8 boşta, P0 tam hız) de tutulur. kartta açık tutulan küçük 'tutamak'
    süreçleri (>= 8 MiB) sayılmaz.
    """
    if not ortam_komut("nvidia-smi"):
        return None
    simdi = ortak.zaman()
    alanlar = ("utilization.gpu,utilization.memory,memory.used,memory.total,"
               "temperature.gpu,power.draw,pstate,clocks.sm,name")
    try:
        c = subprocess.run(["nvidia-smi", f"--query-gpu={alanlar}",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3)
    except Exception:
        return None
    if c.returncode != 0 or not c.stdout.strip():
        return None
    p = [x.strip() for x in c.stdout.strip().splitlines()[0].split(",")]
    if len(p) < 9:
        return None

    if simdi - d.nvidia_surec_zaman >= 3.0:
        d.nvidia_surec_zaman = simdi
        kul = []
        try:
            c2 = subprocess.run(["nvidia-smi",
                                 "--query-compute-apps=pid,process_name,used_memory",
                                 "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=3)
            for satir in c2.stdout.strip().splitlines():
                q = [x.strip() for x in satir.split(",")]
                if len(q) >= 3 and ortak.sayi(q[2]) is not None:
                    kul.append((os.path.basename(q[1]), float(q[2])))
        except Exception:
            pass
        d.nvidia_surecler = [s for s in sorted(kul, key=lambda s: -s[1]) if s[1] >= 8.0]

    yuzde = ortak.sayi(p[0]) or 0.0
    if yuzde > d.nvidia_tepe or simdi - d.nvidia_tepe_zaman > 30:
        d.nvidia_tepe = yuzde
        d.nvidia_tepe_zaman = simdi
    if yuzde >= 1.0 or d.nvidia_surecler:
        d.nvidia_son_kullanim = simdi
        durum = "kullanılıyor"
    elif d.nvidia_tepe >= 5.0:
        durum = "yeni kullanıldı"
    else:
        durum = "boşta"

    return {"yuzde": yuzde, "bellek_yuzde": ortak.sayi(p[1]) or 0.0,
            "vram": ortak.sayi(p[2]) or 0.0, "vram_toplam": ortak.sayi(p[3]) or 0.0,
            "sicaklik": ortak.sayi(p[4]) or 0.0, "guc": ortak.sayi(p[5]),
            "pstate": p[6], "mhz": ortak.sayi(p[7]) or 0.0, "model": p[8],
            "surecler": d.nvidia_surecler, "durum": durum, "tepe": d.nvidia_tepe,
            "son_kullanim": (simdi - d.nvidia_son_kullanim) if d.nvidia_son_kullanim else None}


def oku(d, ayar):
    kartlar = gpu_kartlari(d)
    if ortam_komut("nvidia-smi"):
        simdi = ortak.zaman()
        if simdi - d.nvidia_zaman >= 1.0:
            d.nvidia_zaman = simdi
            d.nvidia = nvidia_oku(d)
    else:
        d.nvidia = None

    nv = d.nvidia
    sonuc = {"kartlar": kartlar, "nvidia": nv}
    if not kartlar and not nv:
        sonuc["yok"] = True
    return sonuc
