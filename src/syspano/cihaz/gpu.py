"""GPU: Intel, AMD, NVIDIA ve Raspberry Pi (VideoCore) desteklenir.

| Üretici | Kullanım | Frekans | Sıcaklık |
|---|---|---|---|
| Intel   | RC6 sayacı farkı | `gt_cur_freq_mhz` | hwmon |
| AMD     | `gpu_busy_percent` | `pp_dpm_sclk` | `device/hwmon/*/temp1_input` |
| NVIDIA  | `nvidia-smi` | `clocks.sm` | `nvidia-smi` |
| VideoCore (Pi) | — | `v3d` saati | `vcgencmd measure_temp` |

**Performans:** hangi kartların var olduğu ve okunacak dosya yolları **bir kez**
bulunur (`_kart_bul`), her ölçümde yalnızca o dosyalar okunur. `which()` sonucu
ve `vcgencmd` çıktısı önbelleğe alınır; `vcgencmd`/`nvidia-smi` gibi süreç
başlatan çağrılar 2–3 saniyede bire seyreltilir.
"""

import glob
import os
import re
import shutil
import subprocess

from . import ortak

_URETICI = {
    "0x8086": "Intel", "0x1002": "AMD", "0x10de": "NVIDIA",
    "0x14e4": "Broadcom", "0x1af4": "virtio", "0x106b": "Apple", "0x1234": "QEMU",
}
_ATLA = ("vkms", "vgem", "simpledrm", "virtio_gpu")

KART_OMRU = 60.0        # saniye; sysfs kart listesi bu sürede bir taranır
VCGENCMD_ARALIK = 3.0   # saniye; vcgencmd süreç başlatır
NVIDIA_BOSTA_ARALIK = 2.0    # saniye; nvidia-smi ~30 ms sürer, boştayken seyrek sor
NVIDIA_AKTIF_ARALIK = 1.0    # kart çalışırken her saniye
NVIDIA_SUREC_ARALIK = 6.0    # saniye; süreç listesi daha da yavaş değişir

_komut_onbellek = {}


def ortam_komut(ad):
    """`which` sonucu önbelleğe alınır (her saniye PATH taranmasın)."""
    var = _komut_onbellek.get(ad)
    if var is None:
        var = shutil.which(ad) is not None
        _komut_onbellek[ad] = var
    return var


# ─── kart keşfi (bir kez) ────────────────────────────────────────────────────
def _kart_bul():
    """Sysfs'ten GPU kartlarını ve okunacak dosya yollarını bulur."""
    kartlar = []
    try:
        girdiler = sorted(os.listdir("/sys/class/drm"))
    except Exception:
        return kartlar
    for giris in girdiler:
        if not re.fullmatch(r"card(\d+)", giris):
            continue
        yol = f"/sys/class/drm/{giris}"
        try:
            surucu = os.path.basename(os.path.realpath(f"{yol}/device/driver"))
        except Exception:
            surucu = ""
        if surucu in _ATLA:
            continue
        uretim = _URETICI.get(ortak.oku(f"{yol}/device/vendor"), "GPU")

        k = {"ad": giris, "surucu": surucu, "uretim": uretim,
             "tur": "diger", "kullanim_dosya": None, "mhz_dosya": None,
             "maks_dosya": None, "rc6_dosya": None, "sicaklik_dosya": None,
             "bellek_dosya": None}

        if uretim == "AMD":
            k["tur"] = "amd"
            k["kullanim_dosya"] = f"{yol}/device/gpu_busy_percent"
            k["bellek_dosya"] = f"{yol}/device/mem_busy_percent"
            k["sclk_dosya"] = f"{yol}/device/pp_dpm_sclk"
            hw = glob.glob(f"{yol}/device/hwmon/hwmon*/temp1_input")
            k["sicaklik_dosya"] = hw[0] if hw else None
            k["model"] = f"AMD {surucu}"
        elif uretim == "Intel" or os.path.exists(f"{yol}/gt_cur_freq_mhz"):
            k["tur"] = "intel"
            k["uretim"] = uretim if uretim == "Intel" else (uretim or "Intel")
            k["mhz_dosya"] = f"{yol}/gt_cur_freq_mhz"
            for aday in (f"{yol}/gt_RP0_freq_mhz", f"{yol}/gt_max_freq_mhz"):
                if os.path.exists(aday):
                    k["maks_dosya"] = aday
                    break
            k["rc6_dosya"] = f"{yol}/power/rc6_residency_ms"
            k["model"] = f"Intel {surucu}"
        else:
            mhz = f"{yol}/gt_cur_freq_mhz"
            if os.path.exists(mhz):
                k["mhz_dosya"] = mhz
            k["model"] = f"{uretim} {surucu}".strip()

        # gerçek bir kart mı? (yolu olan bir şey olmalı)
        if any(k[x] for x in ("kullanim_dosya", "mhz_dosya", "sicaklik_dosya")):
            kartlar.append(k)
    return kartlar


def _kart_degerleri(k, d):
    """Önbellekteki yollardan anlık değerleri okur."""
    sonuc = {"ad": k["ad"], "surucu": k["surucu"], "uretim": k["uretim"],
             "model": k.get("model", k["uretim"]), "kullanim": None,
             "mhz": 0.0, "maks_mhz": 0.0, "sicaklik": 0.0}
    if k["tur"] == "amd":
        deger = ortak.oku_sayi(k["kullanim_dosya"], -1)
        sonuc["kullanim"] = deger if deger >= 0 else None
        sonuc["bellek_yuzde"] = ortak.oku_sayi(k["bellek_dosya"], -1)
        if k["sicaklik_dosya"]:
            sonuc["sicaklik"] = ortak.oku_sayi(k["sicaklik_dosya"], 0) / 1000.0
        metin = ortak.oku(k.get("sclk_dosya"), "") or ""
        for satir in metin.splitlines():          # '*' işaretli satır = geçerli saat
            if "*" in satir:
                esle = re.search(r"(\d+)Mhz", satir)
                if esle:
                    sonuc["mhz"] = float(esle.group(1))
                break
    elif k["tur"] == "intel":
        sonuc["mhz"] = ortak.oku_sayi(k["mhz_dosya"])
        sonuc["maks_mhz"] = ortak.oku_sayi(k["maks_dosya"]) if k["maks_dosya"] else 0.0
        rc6 = ortak.oku_sayi(k["rc6_dosya"], -1) if k["rc6_dosya"] else -1
        sonuc["kullanim"] = _rc6_mesgul(d, k["ad"], rc6)
    else:
        if k["mhz_dosya"]:
            sonuc["mhz"] = ortak.oku_sayi(k["mhz_dosya"])
    return sonuc


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


def gpu_kartlari(d):
    simdi = ortak.zaman()
    onbellek = d.gpu_kart_onbellek
    if onbellek is None or simdi - d.gpu_kart_zaman > KART_OMRU:
        onbellek = d.gpu_kart_onbellek = _kart_bul()
        d.gpu_kart_zaman = simdi
    return [_kart_degerleri(k, d) for k in onbellek]


# ─── Raspberry Pi / VideoCore ────────────────────────────────────────────────
def _vcgencmd(d):
    """`vcgencmd` süreç başlatır; sonuç VCGENCMD_ARALIK boyunca saklanır."""
    simdi = ortak.zaman()
    if d.vcgencmd_sonuc is not None and simdi - d.vcgencmd_zaman < VCGENCMD_ARALIK:
        return d.vcgencmd_sonuc
    sonuc = None
    try:
        mhz = subprocess.run(["vcgencmd", "measure_clock", "v3d"],
                             capture_output=True, text=True, timeout=3).stdout
        t = subprocess.run(["vcgencmd", "measure_temp"],
                           capture_output=True, text=True, timeout=3).stdout
        m = re.search(r"=(\d+)", mhz)
        tt = re.search(r"([\d.]+)", t)
        sonuc = {"ad": "v3d", "surucu": "v3d", "uretim": "Broadcom",
                 "kullanim": None,
                 "mhz": (int(m.group(1)) / 1e6) if m else 0.0,
                 "maks_mhz": 0.0,
                 "sicaklik": float(tt.group(1)) if tt else 0.0,
                 "model": "VideoCore (RPi)"}
    except Exception:
        sonuc = None
    d.vcgencmd_sonuc = sonuc
    d.vcgencmd_zaman = simdi
    return sonuc


# ─── NVIDIA (nvidia-smi) ─────────────────────────────────────────────────────
def nvidia_oku(d):
    """NVIDIA'nın gerçek durumunu okur; yoksa None.

    Anlık kullanım çoğu zaman %0 olduğu için son 30 saniyenin tepesi ve pstate
    (P8 boşta, P0 tam hız) de tutulur. Kartta açık tutulan küçük 'tutamak'
    süreçleri (>= 8 MiB) sayılmaz.
    """
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

    if simdi - d.nvidia_surec_zaman >= NVIDIA_SUREC_ARALIK:
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
    if ortam_komut("vcgencmd"):
        v = _vcgencmd(d)
        if v:
            kartlar.append(v)

    if ortam_komut("nvidia-smi"):
        simdi = ortak.zaman()
        # nvidia-smi her çağrıda bir süreç başlatır (~30 ms). Kart boştayken
        # seyrek sorulur; çalışırken saniyede bir. Kısa yükler 30 sn'lik tepe
        # mantığıyla yine yakalanır.
        durum = (d.nvidia or {}).get("durum")
        aralik = (NVIDIA_AKTIF_ARALIK if durum and durum != "boşta"
                  else NVIDIA_BOSTA_ARALIK)
        if simdi - d.nvidia_zaman >= aralik:
            d.nvidia_zaman = simdi
            d.nvidia = nvidia_oku(d)
    else:
        d.nvidia = None

    sonuc = {"kartlar": kartlar, "nvidia": d.nvidia}
    if not kartlar and not d.nvidia:
        sonuc["yok"] = True
    return sonuc
