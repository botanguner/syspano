"""Yedek durumu (isteğe bağlı).

Varsayılan olarak gdrive-yedek projesinin durum dosyasını okur; yoksa kart
gizlenir. Yolu yapılandırmadan değiştirilebilir:

    "yedek_durum_yolu": "~/.local/state/gdrive-yedek/durum.json",
    "yedek_zamanlayici": "yedek.timer"
"""

import json
import os
import subprocess
import time

from . import ortak

VARSAYILAN_YOL = "~/.local/state/gdrive-yedek/durum.json"
VARSAYILAN_ZAMANLAYICI = "yedek.timer"
SORGU_ARALIK = 5.0        # saniye; systemctl sorguları bu aralıkta önbelleğe alınır
_onbellek = {"zaman": 0.0, "sonuc": {}}


def _sonraki_calisma(timer):
    """systemd kullanıcı zamanlayıcısının sıradaki çalışma zamanı (epoch)."""
    if not timer:
        return ""
    try:
        c = subprocess.run(
            ["systemctl", "--user", "show", timer,
             "-p", "NextElapseUSecRealtime", "--value"],
            capture_output=True, text=True, timeout=3)
        metin = c.stdout.strip()
        if metin and metin not in ("0", "n/a", "infinity"):
            return metin
    except Exception:
        pass
    return ""


def _calistir(komut, zaman=10):
    try:
        c = subprocess.run(komut, capture_output=True, text=True, timeout=zaman)
        return c.returncode, (c.stdout or "").strip()
    except Exception:
        return 1, ""


def _sorgu(zamanlayici, taze=False):
    """Zamanlayıcı/servis durumu (önbellekli)."""
    simdi = ortak.zaman()
    if (not taze and _onbellek["sonuc"]
            and simdi - _onbellek["zaman"] < SORGU_ARALIK):
        return _onbellek["sonuc"]
    _, timer = _calistir(["systemctl", "--user", "is-active", zamanlayici])
    _, servis = _calistir(["systemctl", "--user", "is-active",
                           zamanlayici.replace(".timer", ".service")])
    sonuc = {"zamanlayici_etkin": timer == "active", "calisiyor": servis == "active"}
    _onbellek.update({"zaman": simdi, "sonuc": sonuc})
    return sonuc


def durum_metni(ayar=None):
    """Ayar ekranı YEDEK bölümü: (satırlar, eylemler).

    `satirlar`: [(metin, renk anahtarı), ...] — durum + sıradaki çalışma.
    `eylemler`: düğme kimlikleri ("yedek_simdi" · "zamanlayici_ac" · "zamanlayici_kapat").
    """
    ayar = ayar or {}
    yol = os.path.expanduser(ayar.get("yedek_durum_yolu") or VARSAYILAN_YOL)
    zamanlayici = ayar.get("yedek_zamanlayici", VARSAYILAN_ZAMANLAYICI)
    durum = _sorgu(zamanlayici)
    satirlar = []

    if not os.path.exists(yol):
        satirlar.append(("Yedek kurulu değil (durum dosyası yok)", "soluk"))
        satirlar.append((f"Beklenen: {yol}", "cok_soluk"))
        return satirlar, []

    try:
        with open(yol) as f:
            veri = json.load(f)
    except Exception as hata:
        satirlar.append((f"Durum dosyası okunamadı: {hata}", "kirmizi"))
        return satirlar, ["yedek_simdi"]

    if durum.get("calisiyor"):
        satirlar.append(("⏳ Yedek sürüyor…", "mavi"))
    elif veri.get("sonuc"):
        hata = (veri.get("hata") or "").strip()
        satirlar.append((f"⚠ Son yedek başarısız — {hata[:60] or 'ayrıntı yok'}",
                         "kirmizi"))
    else:
        bas = ortak.sayi(veri.get("baslangic")) or 0
        yas = ortak.sure_metni(time.time() - bas) if bas else "?"
        parcalar = [f"Son yedek: {yas}", "başarılı"]
        if veri.get("yuklenen"):
            parcalar.append(f"{int(veri['yuklenen'])} dosya")
        if veri.get("toplam_bayt"):
            parcalar.append(ortak.boyut_metni(veri["toplam_bayt"]))
        satirlar.append((" · ".join(parcalar), "yesil"))

    sonraki = _sonraki_calisma(zamanlayici) if durum.get("zamanlayici_etkin") else ""
    from . import servisler as S
    if not durum.get("zamanlayici_etkin"):
        satirlar.append(("Zamanlayıcı kapalı — otomatik yedek yok", "sari"))
    elif sonraki:
        okunur = S.zaman_ayristir(sonraki)
        satirlar.append((f"Sıradaki: {time.strftime('%d.%m %H:%M', time.localtime(okunur))}"
                         if okunur else f"Sıradaki: {sonraki[:24]}", "soluk"))

    eylemler = ["yedek_simdi"]
    eylemler.append("zamanlayici_kapat" if durum.get("zamanlayici_etkin")
                    else "zamanlayici_ac")
    return satirlar, eylemler


def eylem(ad, ayar=None):
    """`yedek_simdi` · `zamanlayici_ac` · `zamanlayici_kapat` → (basarili, mesaj)."""
    ayar = ayar or {}
    zamanlayici = ayar.get("yedek_zamanlayici", VARSAYILAN_ZAMANLAYICI)
    servis = zamanlayici.replace(".timer", ".service")
    # --no-block ŞART: yedek birkaç dakika sürer (oneshot); beklemeli çağrı
    # panoyu o süre boyunca kilitler (ölçüldü: 25 dakikalık yedek).
    esleme = {"yedek_simdi": ["systemctl", "--user", "start", "--no-block", servis],
              "zamanlayici_ac": ["systemctl", "--user", "start", zamanlayici],
              "zamanlayici_kapat": ["systemctl", "--user", "stop", zamanlayici]}
    if ad not in esleme:
        return False, f"bilinmeyen eylem: {ad}"
    kod, cikti = _calistir(esleme[ad], 15)
    _onbellek["zaman"] = 0.0
    if kod != 0:
        return False, f"systemctl hatası: {cikti[:60] or 'bilinmiyor'}"
    return True, {"yedek_simdi": "Yedek başlatıldı (arka planda)",
                  "zamanlayici_ac": "Otomatik yedek açıldı",
                  "zamanlayici_kapat": "Otomatik yedek kapatıldı"}[ad]


def oku(d, ayar):
    yol = os.path.expanduser(ayar.get("yedek_durum_yolu") or VARSAYILAN_YOL)
    zamanlayici = ayar.get("yedek_zamanlayici", VARSAYILAN_ZAMANLAYICI)

    if not os.path.exists(yol):
        return {"yok": True}

    try:
        with open(yol) as f:
            veri = json.load(f)
    except Exception:
        return {"yok": True}

    simdi = ortak.zaman()
    if simdi - d.yedek_zaman >= 60.0:
        d.yedek_zaman = simdi
        d.yedek_sonraki = _sonraki_calisma(zamanlayici)

    veri = dict(veri)
    veri["sonraki"] = d.yedek_sonraki
    veri["yok"] = False
    return veri
