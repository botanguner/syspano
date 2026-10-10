"""Güncelleme: kurulum kaydı, sürüm denetimi ve güncelleme.

Amaç: GitHub'dan klonlayıp kuran birinin tek komutla (ya da panodaki bir
düğmeyle) güncelleyebilmesi.

İki dosya tutulur (her ikisi de `~/.local/state/syspano/`):

* **kurulum.json** — `install.sh` yazar: nereye kuruldu, hangi yöntemle
  (pipx / pip --user / sistem), kaynak dizin, sürüm.
* **surum-denetimi.json** — son denetimin sonucu: yerel sürüm, uzaktaki durum,
  yeni sürüm var mı. Pano yalnızca bu dosyayı okur (ağa çıkmaz).

Klonlanmış bir kurulumda "yeni sürüm var mı?" sorusu, `git rev-list --count
HEAD..@{u}` ile yanıtlanır: uzakta bizde olmayan commit var mı? Etiket
kullanılmışsa etiket de karşılaştırılır.
"""

import json
import os
import re
import subprocess
import sys
import time

from . import __version__
from . import ortam

VARSAYILAN_URL = "https://github.com/botanguner/syspano.git"
KAYIT_ADI = "kurulum.json"
DENETIM_ADI = "surum-denetimi.json"
SUREC_ADI = "guncelleme-durum.json"
GUNCELLEME_ASAMASI = "guncelleniyor"


# ─── yollar ──────────────────────────────────────────────────────────────────
def durum_dizini():
    return ortam.emin_ol(ortam.kalici_durum_dizini())


def kayit_yolu():
    return os.path.join(durum_dizini(), KAYIT_ADI)


def denetim_yolu():
    return os.path.join(durum_dizini(), DENETIM_ADI)


def surec_yolu():
    return os.path.join(durum_dizini(), SUREC_ADI)


# ─── kurulum kaydı ───────────────────────────────────────────────────────────
def kayit_oku():
    try:
        with open(kayit_yolu()) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def kayit_yaz(yontem, kaynak, url=None, surum=None):
    d = {
        "yontem": yontem,                 # pipx | pip-kullanici | pip-sistem
        "kaynak": os.path.abspath(kaynak) if kaynak else None,
        "url": url or VARSAYILAN_URL,
        "surum": surum or __version__,
        "tarih": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    gecici = kayit_yolu() + ".tmp"
    with open(gecici, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(gecici, kayit_yolu())
    return d


# ─── sürüm karşılaştırma ─────────────────────────────────────────────────────
def yerel_surum():
    return __version__


def surum_parcala(metin):
    """'v1.2.3-4-gabcdef' → (1, 2, 3)."""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", str(metin or ""))
    if m:
        return tuple(int(x) for x in m.groups())
    m = re.search(r"(\d+)\.(\d+)", str(metin or ""))
    if m:
        return tuple(int(x) for x in m.groups()) + (0,)
    return (0, 0, 0)


def surum_karsilastir(a, b):
    """a<b → -1, a==b → 0, a>b → 1."""
    pa, pb = surum_parcala(a), surum_parcala(b)
    return (pa > pb) - (pa < pb)


def etiketleri_ayristir(cikti):
    """`git ls-remote --tags --refs` çıktısından sürüm etiketleri.

    Satır biçimi: '<sha>\\trefs/tags/v1.2.3'
    """
    etiketler = []
    for satir in (cikti or "").splitlines():
        if "refs/tags/" not in satir:
            continue
        ad = satir.split("refs/tags/", 1)[1].strip()
        if ad.endswith("^{}"):          # anotasyonlu etiketin çözülmüş hâli
            ad = ad[:-3]
        if re.match(r"^v?\d+\.\d+", ad) and ad not in etiketler:
            etiketler.append(ad)
    etiketler.sort(key=surum_parcala)
    return etiketler


# ─── komut çalıştırma ────────────────────────────────────────────────────────
def _calistir(cmd, cwd=None, zaman=60):
    try:
        c = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=zaman)
        return c.returncode, (c.stdout or "") + (c.stderr or "")
    except FileNotFoundError:
        return 127, f"komut bulunamadı: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"zaman aşımı: {' '.join(cmd)}"
    except Exception as hata:
        return 1, str(hata)


def git_var():
    from shutil import which
    return which("git") is not None


def _git_deposu(yol):
    return bool(yol) and os.path.isdir(os.path.join(yol, ".git"))


def _depo_surumu(kaynak):
    """Klondaki paketin sürümü (`src/syspano/__init__.py`).

    Kurulu paket ile depodaki kod farklı olabilir: `git pull` ile depo
    ilerletilmiş ama `pip install` çalıştırılmamışsa `syspano --surum` eski
    sürümü gösterir. Bu ayrımı yakalamak için depo sürümü ayrıca okunur.
    """
    if not kaynak:
        return None
    yol = os.path.join(kaynak, "src", "syspano", "__init__.py")
    try:
        with open(yol) as f:
            for satir in f:
                m = re.match(r'__version__\s*=\s*"([^"]+)"', satir.strip())
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def _upstream(kaynak):
    """Klonun takip ettiği uzak dal ('@{u}' varsa o, yoksa origin/HEAD)."""
    kod, cikti = _calistir(["git", "-C", kaynak, "rev-parse", "--abbrev-ref",
                            "--symbolic-full-name", "@{u}"], zaman=10)
    if kod == 0 and cikti.strip():
        return cikti.strip().splitlines()[-1]
    for aday in ("origin/main", "origin/master", "origin/HEAD"):
        kod, _ = _calistir(["git", "-C", kaynak, "rev-parse", "--verify", aday], zaman=10)
        if kod == 0:
            return aday
    return None


# ─── denetim ─────────────────────────────────────────────────────────────────
def denetim_oku():
    try:
        with open(denetim_yolu()) as f:
            return json.load(f)
    except Exception:
        return {}


def _denetim_yaz(sonuc):
    gecici = denetim_yolu() + ".tmp"
    with open(gecici, "w") as f:
        json.dump(sonuc, f, ensure_ascii=False)
    os.replace(gecici, denetim_yolu())
    return sonuc


def denetle(url=None, yerel=None):
    """Yeni sürüm var mı? Ağa çıkar; sonucu diske yazar.

    `yerel` verilmezse çalışan paketin sürümü kullanılır. Güncelleme
    bittikten hemen sonra paket henüz yeniden başlatılmadığı için eski sürüm
    bellekte olur; o durumda `yerel` olarak **depodaki** sürüm geçirilir ki
    yanlış bir "güncelleme var" rozeti kalmasın.

    Dönen: {yerel, uzak, yeni, geride, mesaj, yontem, kaynak, zaman}
    """
    yerel = yerel or __version__
    kayit = kayit_oku()
    kaynak = kayit.get("kaynak")
    sonuc = {
        "zaman": time.time(), "yerel": yerel,
        "yontem": kayit.get("yontem", "?"), "kaynak": kaynak,
        "url": url or kayit.get("url") or VARSAYILAN_URL,
        "uzak": None, "yeni": False, "geride": 0, "mesaj": "", "hata": None,
    }

    if not git_var():
        sonuc["hata"] = "git yok — güncelleme denetimi yapılamıyor"

    elif _git_deposu(kaynak):
        kod, _ = _calistir(["git", "-C", kaynak, "fetch", "--quiet", "--tags",
                            "origin"], zaman=60)
        if kod != 0:
            sonuc["hata"] = "uzak depoya ulaşılamadı (ağ?)"
        else:
            dal = _upstream(kaynak)
            if not dal:
                sonuc["hata"] = "uzak dal bulunamadı"
            else:
                kod, cikti = _calistir(["git", "-C", kaynak, "rev-list", "--count",
                                        f"HEAD..{dal}"], zaman=15)
                if kod == 0 and cikti.strip().splitlines()[-1].isdigit():
                    geride = int(cikti.strip().splitlines()[-1])
                    sonuc["geride"] = geride
                    sonuc["yeni"] = geride > 0
                    if geride:
                        _, konu = _calistir(["git", "-C", kaynak, "log", "--oneline",
                                             "-1", dal], zaman=15)
                        sonuc["mesaj"] = konu.strip()[:140]
                    # etiket varsa sürümü de bildir
                    kod, etiket = _calistir(["git", "-C", kaynak, "describe", "--tags",
                                             "--abbrev=0", dal], zaman=15)
                    etiket = etiket.strip().splitlines()[-1] if etiket.strip() else ""
                    if kod == 0 and etiket and not etiket.lower().startswith(("fatal", "usage")):
                        sonuc["uzak"] = etiket
                        if surum_karsilastir(sonuc["uzak"], yerel) > 0:
                            sonuc["yeni"] = True

        # kurulu paket ile depodaki kod aynı mı? (git pull yapılıp kurulmamış olabilir)
        depo_surum = _depo_surumu(kaynak)
        sonuc["depo_surum"] = depo_surum
        if depo_surum and surum_karsilastir(depo_surum, yerel) != 0:
            sonuc["yeni"] = True
            sonuc["kurulum_gerekli"] = True
            sonuc["mesaj"] = (f"depodaki sürüm {depo_surum}, kurulu paket {yerel}"
                              " — yeniden kurulum gerekli")

    else:
        # klon yok: etiketleri uzaktan okuyup sürümü karşılaştır
        kod, cikti = _calistir(["git", "ls-remote", "--tags", "--refs", sonuc["url"]],
                               zaman=45)
        if kod != 0:
            sonuc["hata"] = "uzak depoya ulaşılamadı (ağ?)"
        else:
            etiketler = etiketleri_ayristir(cikti)
            if etiketler:
                sonuc["uzak"] = etiketler[-1]
                sonuc["yeni"] = surum_karsilastir(sonuc["uzak"], yerel) > 0

    return _denetim_yaz(sonuc)


def denetim_bayati(saat=24):
    """Son denetim belirtilen saatten eski mi?"""
    son = denetim_oku()
    return (time.time() - float(son.get("zaman") or 0)) > saat * 3600


def yeni_surum_var():
    """Önbellekteki sonuca göre yeni sürüm var mı? (ağa çıkmaz)"""
    return bool(denetim_oku().get("yeni"))


# ─── güncelleme süreci (pano ↔ arka plan süreci) ─────────────────────────────
def surec_yaz(asama, sonuc=None, mesaj="", baslangic=None, surum=None):
    """Güncelleme sürecinin durumunu yazar.

    Arka planda çalışan `syspano --guncelle` süreci bunu yazar; pano okuyup
    "sürüyor / bitti / başarısız" diye gösterir — böylece kullanıcı sonucu
    tahmin etmek zorunda kalmaz.
    """
    d = surec_oku()
    if asama:
        d["asama"] = asama
    if baslangic is not None:
        d["basladi"] = float(baslangic)
    if surum is not None:
        d["surum"] = surum
    if sonuc is not None:
        d["bitti"] = time.time()
        d["sonuc"] = int(sonuc)
    if mesaj:
        d["mesaj"] = mesaj
    gecici = surec_yolu() + ".tmp"
    with open(gecici, "w") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(gecici, surec_yolu())
    return d


def surec_oku():
    """Son güncelleme sürecinin durumu (yoksa boş sözlük)."""
    try:
        with open(surec_yolu()) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def kurulu_surum():
    """Kurulu paketin sürümü (pip kaydı); okunamazsa çalışan sürüm."""
    try:
        from importlib.metadata import version
        return version("syspano")
    except Exception:
        return __version__


def kurulu_dosya():
    """Kurulu paketin `__init__.py` yolu (yoksa None)."""
    try:
        import importlib.util
        spec = importlib.util.find_spec("syspano")
        yol = getattr(spec, "origin", None)
        return yol if yol and os.path.exists(yol) else None
    except Exception:
        return None


def yeniden_baslat_gerekli(baslangic=None):
    """Kurulu kod, bellekte çalışan koddan **yeni** mi? (güncelleme sonrası)

    Güncelleme paketi yeniden kurar ama çalışan süreç eski kodu bellekte tutar;
    pano bunu fark edip "yeniden başlatın" demelidir.

    * `baslangic` verilirse (pano kendi açılış anını verir): kurulu paketin
      dosya zamanı ondan sonraysa — en isabetli ölçüt budur.
    * Verilmezse sürümler karşılaştırılır: kurulu paket, çalışan koddan yeni
      sürümlüyse. (Bu yüzden eski bir kurulumla depodan çalıştırmak yanlış
      uyarı vermez.)
    """
    if baslangic:
        yol = kurulu_dosya()
        if yol:
            try:
                return os.path.getmtime(yol) > float(baslangic) + 2
            except OSError:
                pass
    return surum_karsilastir(kurulu_surum(), __version__) > 0


def systemd_kullanici_birimi():
    """Pano systemd **kullanıcı servisi** olarak mı çalışıyor?"""
    kod, cikti = _calistir(["systemctl", "--user", "list-unit-files",
                            "syspano.service", "--no-legend"], zaman=5)
    return kod == 0 and "syspano.service" in (cikti or "")


def yeniden_baslat_yolu():
    """Bu makinede panoyu yeniden başlatmanın doğru yolu (kısa metin).

    Servis olarak çalışıyorsa `systemctl --user restart syspano`; masaüstü
    oturumunda kendiliğinden başlatıldıysa panodaki ⚙ ekranındaki düğme.
    """
    try:
        if systemd_kullanici_birimi():
            return "systemctl --user restart syspano"
    except Exception:
        pass
    return "panoda ⚙ → Panoyu yeniden başlat"


def _yas_metni(sn):
    sn = max(0, int(sn))
    if sn < 90:
        return "az önce"
    if sn < 3600:
        return f"{sn // 60} dk önce"
    if sn < 86400:
        return f"{sn // 3600} saat önce"
    return f"{sn // 86400} gün önce"


def durum_metni(denetim=None, surec=None, simdi=None, denetim_suruyor=False,
                zaman_asimi=False, baslangic=None):
    """Ayarlar ekranındaki güncelleme durumu: (metin, renk anahtarı).

    **Saf** fonksiyon: ağa çıkmaz, dosya yazmaz. Sıralama, kullanıcının en çok
    merak ettiği bilgiyi öne koyar: denetim/güncelleme sürüyorsa o, bittiyse
    sonuç, bekleyen bir yeniden başlatma varsa o, sonra denetim sonucu.
    """
    simdi = time.time() if simdi is None else simdi
    denetim = denetim_oku() if denetim is None else denetim
    surec = surec_oku() if surec is None else surec

    if denetim_suruyor:
        return ("⟳ Denetleniyor… (ağa çıkılıyor)", "mavi")
    if surec.get("asama") == GUNCELLEME_ASAMASI and not surec.get("bitti"):
        gecen = int(max(0.0, simdi - float(surec.get("basladi") or simdi)))
        return (f"⏳ Güncelleme sürüyor… ({gecen} sn)", "mavi")
    if surec.get("bitti"):
        yas = simdi - float(surec.get("bitti") or 0)
        if surec.get("sonuc"):
            # başarısızlık bir süre görünür kalsın (kullanıcı görsün), sonra normal duruma dön
            if yas < 3600:
                ayrinti = surec.get("mesaj") or "ayrıntı: güncelleme.log"
                return (f"⚠ Güncelleme başarısız — {ayrinti}", "kirmizi")
        elif yeniden_baslat_gerekli(baslangic):
            # Yalnızca gerçekten yeniden başlatma bekliyorsa hatırlat. Kayıt
            # kalıcı olduğu için koşulsuz gösterildiğinde, pano yeniden
            # başlatılsa da uyarı sonsuza dek kalıyordu (kullanıcı bildirdi).
            surum = surec.get("surum") or kurulu_surum()
            return (f"✓ Güncelleme tamam ({surum}) — Panoyu yeniden başlatın", "sari")
    if zaman_asimi:
        return ("⚠ Denetim zaman aşımına uğradı (ağ yok?) — yeniden deneyin", "kirmizi")
    if yeniden_baslat_gerekli(baslangic):
        kurulu = kurulu_surum()
        if kurulu and kurulu != __version__:
            return (f"⟳ Kurulu paket {kurulu}, bellekteki kod {__version__}"
                    " — Panoyu yeniden başlatın", "sari")
        return ("⟳ Güncelleme kuruldu ama pano eski kodu bellekte tutuyor"
                " — Panoyu yeniden başlatın", "sari")
    if not denetim or not denetim.get("zaman"):
        return ("Güncelleme durumu bilinmiyor — «Güncellemeyi denetle»", "soluk")
    if denetim.get("hata"):
        return (f"⚠ Denetlenemedi: {denetim['hata']}", "kirmizi")
    if denetim.get("kurulum_gerekli"):
        return (f"⚠ Yeniden kurulum gerekli (depo {denetim.get('depo_surum') or '?'})",
                "sari")
    if denetim.get("yeni"):
        hedef = denetim.get("depo_surum") or denetim.get("uzak") or "?"
        return (f"⬆ Yeni sürüm var: {hedef} — «Güncelle»ye dokunun", "sari")
    return (f"✓ Güncel · son denetim {_yas_metni(simdi - float(denetim['zaman']))}",
            "yesil")


# ─── güncelleme ──────────────────────────────────────────────────────────────
def guncelle(url=None, tekrar_kur=True):
    """Klonu günceller ve paketi yeniden kurar.

    Dönen: {"ok": bool, "adimlar": [(basarili, mesaj)], "yeniden_baslat": bool}
    """
    adimlar = []

    def ekle(ok, mesaj):
        adimlar.append((bool(ok), mesaj))
        return ok

    kayit = kayit_oku()
    kaynak = kayit.get("kaynak")
    yontem = kayit.get("yontem")

    if not kayit:
        ekle(False, "Kurulum kaydı yok. Depoyu klonlayıp `./install.sh` çalıştırın "
                    "ya da elle güncelleyin: pip install --upgrade <depo>")
        return {"ok": False, "adimlar": adimlar, "yeniden_baslat": False}

    if not git_var():
        ekle(False, "git kurulu değil; elle güncelleyin.")
        return {"ok": False, "adimlar": adimlar, "yeniden_baslat": False}

    # 1) yerel değişiklik var mı? (varsa pull riskli)
    if _git_deposu(kaynak):
        kod, cikti = _calistir(["git", "-C", kaynak, "status", "--porcelain"], zaman=15)
        if kod != 0:
            ekle(False, f"depo okunamadı: {kaynak}")
            return {"ok": False, "adimlar": adimlar, "yeniden_baslat": False}
        if cikti.strip():
            ekle(False, f"{kaynak} içinde kaydedilmemiş değişiklik var; "
                        "önce `git stash` ya da `git checkout .` yapın.")
            return {"ok": False, "adimlar": adimlar, "yeniden_baslat": False}

        # 2) çek
        kod, cikti = _calistir(["git", "-C", kaynak, "pull", "--ff-only"], zaman=180)
        ekle(kod == 0, ("kod güncellendi: " + cikti.strip().splitlines()[0])
             if kod == 0 else f"git pull başarısız: {cikti.strip()[:200]}")
        if kod != 0:
            return {"ok": False, "adimlar": adimlar, "yeniden_baslat": False}
    else:
        ekle(True, "klon yok; paket uzak depodan güncellenecek")

    # 3) yeniden kur
    if tekrar_kur:
        if yontem == "pipx":
            kod, cikti = _calistir(["pipx", "install", "--force", kaynak], zaman=300)
            ekle(kod == 0, "pipx ile yeniden kuruldu" if kod == 0
                 else f"pipx kurulumu başarısız: {cikti.strip()[:200]}")
        elif yontem == "pip-sistem":
            ekle(False, "sistem kurulumu: `sudo ./install.sh --sistem` çalıştırın")
        else:
            kod, cikti = _calistir([sys.executable, "-m", "pip", "install",
                                    "--user", "--upgrade", kaynak], zaman=300)
            if kod != 0:
                kod, cikti = _calistir([sys.executable, "-m", "pip", "install",
                                        "--user", "--break-system-packages",
                                        "--upgrade", kaynak], zaman=300)
            ekle(kod == 0, "pip --user ile yeniden kuruldu" if kod == 0
                 else f"pip kurulumu başarısız: {cikti.strip()[:200]}")

    # Güncelleme bitti: kurulu sürüm artık **depodaki** sürümdür (paket yeniden
    # kuruldu). Çalışan süreç hâlâ eski sürümü bellekte tuttuğu için denetimi
    # depo sürümüyle yapıyoruz — yoksa panoda yanlış "güncelleme var" rozeti kalır.
    yeni_surum = _depo_surumu(kaynak) or __version__
    kayit_yaz(yontem or "pip-kullanici", kaynak, kayit.get("url"), yeni_surum)
    sonuc = denetle(yerel=yeni_surum)
    ekle(True, f"güncelleme tamam — kurulu sürüm {yeni_surum}, güncel"
         if not sonuc.get("yeni") else
         f"güncelleme tamam — kurulu sürüm {yeni_surum}"
         + (f", uzak {sonuc['uzak']}" if sonuc.get("uzak") else ""))
    return {"ok": all(ok for ok, _ in adimlar), "adimlar": adimlar,
            "yeniden_baslat": True}


def metin_ozet(baslik_genisligi=0):
    """Panoda/terminalde gösterilecek tek satırlık durum."""
    son = denetim_oku()
    if not son:
        return "güncelleme durumu bilinmiyor"
    if son.get("kurulum_gerekli"):
        return (f"yeniden kurulum gerekli · depo {son.get('depo_surum')} / "
                f"kurulu {son['yerel']}")
    if son.get("hata"):
        return f"denetlenemedi: {son['hata']}"
    if son.get("yeni"):
        uzak = f" (uzak {son['uzak']})" if son.get("uzak") else ""
        return f"yeni sürüm var{uzak} · yerel {son['yerel']}"
    return f"güncel · yerel {son['yerel']}"
