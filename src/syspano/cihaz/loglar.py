"""Günlük kaynakları: geliştiricinin aradığı log dosyaları.

Sunucu ve geliştirme makinelerinde aranan günlükler burada tanımlıdır: Apache,
nginx, **PHP / PHP-FPM**, Laravel/Symfony/WordPress, MySQL/MariaDB, PostgreSQL,
Redis, MongoDB, PM2, Caddy, Gunicorn, Jenkins ve sistem günlükleri. Kullanıcı
`log_dosyalari` ile kendi dosya/desenlerini ekleyebilir.

**Maliyet ilkesi (ölçümle seçildi):**

| İş | Maliyet | Ne zaman |
|---|---|---|
| Keşif: `glob` + `stat` (bilinen yollar) | ~0,5 ms | açılışta ve **10 dakikada bir** |
| Boyut/yaş tazeleme (yalnızca bulunanlar) | ~0,05 ms × N | **5 saniyede bir** |
| İçerik okuma (`kuyruk`, en fazla 512 KiB) | ~0,2 ms | yalnızca **görüntüleyici açıkken** |

Kart yalnızca dosya adı, boyut ve **son yazılma** bilgisini gösterir; dosya
içeriği kart için hiç okunmaz (SD kartta her okuma pahalıdır). Hata/uyarı
sayısı, içeriği zaten okunan görüntüleyicide ve `--log-kaynaklar` çıktısında
hesaplanır.

Okunamayan dosyalar (ör. `/var/log/mysql/error.log`, çoğu dağıtımda root'a
aittir) kartta **izin yok** olarak işaretlenir; görüntüleyici çözümü söyler.
"""

import glob
import os
import re
import time

from . import ortak

# ── geliştiricinin aradığı günlükler ─────────────────────────────────────────
# (grup, ekranda görünecek etiket, yol ya da glob deseni)
# Desenler hem Debian/Raspberry Pi OS (apache2, mariadb) hem Fedora/RHEL
# (httpd) düzenini kapsar; bulunmayanlar sessizce elenir.
DESENLER = (
    # PHP
    ("php", "PHP-FPM", "/var/log/php*-fpm.log"),
    ("php", "PHP-FPM", "/var/log/php-fpm.log"),
    ("php", "PHP (yavaş)", "/var/log/php*-fpm-slow.log"),
    ("php", "PHP", "/var/log/php/error.log"),
    ("php", "PHP", "/var/log/php_errors.log"),
    ("php", "PHP", "/var/log/php*/error.log"),
    # Apache
    ("apache", "Apache", "/var/log/apache2/error.log"),
    ("apache", "Apache (erişim)", "/var/log/apache2/access.log"),
    ("apache", "Apache (vhost)", "/var/log/apache2/other_vhosts_access.log"),
    ("apache", "Apache", "/var/log/httpd/error_log"),
    ("apache", "Apache (erişim)", "/var/log/httpd/access_log"),
    # nginx / Caddy
    ("nginx", "nginx", "/var/log/nginx/error.log"),
    ("nginx", "nginx (erişim)", "/var/log/nginx/access.log"),
    ("nginx", "Caddy", "/var/log/caddy/*.log"),
    # uygulama günlükleri
    ("uygulama", "Laravel", "/var/www/*/storage/logs/*.log"),
    ("uygulama", "Laravel", "~/www/*/storage/logs/*.log"),
    ("uygulama", "Laravel", "~/*/storage/logs/laravel*.log"),
    ("uygulama", "Symfony", "/var/www/*/var/log/*.log"),
    ("uygulama", "WordPress", "/var/www/*/wp-content/debug.log"),
    ("uygulama", "PM2 (hata)", "~/.pm2/logs/*-error.log"),
    ("uygulama", "PM2", "~/.pm2/logs/*-out.log"),
    ("uygulama", "Gunicorn", "/var/log/gunicorn/*.log"),
    # veritabanı
    ("veritabani", "MySQL", "/var/log/mysql/error.log"),
    ("veritabani", "MySQL (yavaş sorgu)", "/var/log/mysql/mysql-slow.log"),
    ("veritabani", "MariaDB", "/var/log/mariadb/mariadb.log"),
    ("veritabani", "MySQL", "/var/log/mysqld.log"),
    ("veritabani", "PostgreSQL", "/var/log/postgresql/postgresql-*.log"),
    ("veritabani", "Redis", "/var/log/redis/redis-server.log"),
    ("veritabani", "Redis", "/var/log/redis/redis.log"),
    ("veritabani", "MongoDB", "/var/log/mongodb/mongod.log"),
    # sunucu / CI
    ("sunucu", "Jenkins", "/var/log/jenkins/jenkins.log"),
    ("sunucu", "Syslog", "/var/log/syslog"),
    ("sunucu", "Çekirdek", "/var/log/kern.log"),
    ("sunucu", "Kimlik", "/var/log/auth.log"),
    ("sunucu", "Mesajlar", "/var/log/messages"),
    ("sunucu", "Paket (dnf)", "/var/log/dnf.log"),
    ("sunucu", "Paket (dpkg)", "/var/log/dpkg.log"),
    ("sunucu", "Paket (pacman)", "/var/log/pacman.log"),
)

# Karttaki sıra: geliştiriciye en yakın grup önce (aynı grup içinde en yeni önce).
# Sistem günlükleri her saniye yazıldığı için en sonda kalır.
GRUP_SIRASI = ("php", "uygulama", "apache", "nginx", "veritabani", "sunucu", "ozel")

# journald'a yazan servisler: dosya günlüğü olmayanlar (Debian/Raspberry Pi OS'ta
# MariaDB, PostgreSQL, Redis, Docker, SSH) buradan okunur. "journalctl -u" ile
# okunur; dosya kaynaklarından SONRA listelenir.
#   (grup, ekranda görünecek etiket, systemd birimi — "-k" çekirdek günlüğü)
JOURNAL_KAYNAKLARI = (
    ("veritabani", "MariaDB", "mariadb.service"),
    ("veritabani", "MySQL", "mysql.service"),
    ("veritabani", "PostgreSQL", "postgresql.service"),
    ("veritabani", "Redis", "redis-server.service"),
    ("uygulama", "Docker", "docker.service"),
    ("sunucu", "SSH", "ssh.service"),
    ("sunucu", "SSH", "sshd.service"),
    ("sunucu", "Çekirdek", "-k"),
)
CEKIRDEK_BIRIMI = "-k"

# Görüntüleyicidebir satırın önem derecesi
HATA_KELIMELERI = ("error", "fail", "fatal", "exception", "critical", "panic", "hata")
UYARI_KELIMELERI = ("warn", "notice", "deprecated", "uyarı")

KESIF_OMRU = 600.0      # saniye; kaynak listesi bu sürede bir tazelenir
STAT_ARALIK = 5.0       # saniye; boyut/yaş tazeleme aralığı
AZAMI_BAYT = 512 * 1024  # kuyruk okumasında en fazla bu kadar bayt okunur
VARSAYILAN_PENCERE_DK = 60   # journald hata/uyarı sayımı için zaman penceresi


def _ozel_etiket(desen):
    """Kendi eklenen desen için okunur etiket: '~/p/*/storage/logs/*.log' → 'logs/*.log'."""
    parcalar = [p for p in desen.rstrip("/").split("/") if p not in ("", "~")]
    if not parcalar:
        return desen
    son = parcalar[-1]
    if "*" in son and len(parcalar) >= 2:
        son = f"{parcalar[-2]}/{son}"
    return son


def desenler(ayar=None):
    """Varsayılan desenler + `log_dosyalari` girdileri."""
    hepsi = list(DESENLER)
    for desen in (ayar or {}).get("log_dosyalari") or []:
        desen = str(desen)
        hepsi.append(("ozel", _ozel_etiket(desen), desen))
    return hepsi


def _genislet(desen):
    """Deseni gerçek dosya yollarına çevirir (~ genişletmesi ve glob)."""
    return [y for y in sorted(glob.glob(os.path.expanduser(desen)))
            if os.path.isfile(y)]


def _satir(grup, etiket, yol):
    try:
        bilgi = os.stat(yol)
    except OSError as hata:
        return None
    return {
        "tur": "dosya",
        "grup": grup,
        "etiket": etiket,
        "ad": os.path.basename(yol),
        "yol": yol,
        "boyut": bilgi.st_size,
        "son": bilgi.st_mtime,
        "okunabilir": os.access(yol, os.R_OK),
    }


def _birim_adi(ad):
    """'journal:mariadb' → 'mariadb.service' (kısa yazımı da kabul et)."""
    ad = str(ad).strip()
    if ad == CEKIRDEK_BIRIMI or "." in ad:
        return ad
    return ad + ".service"


def journal_kaynaklari(ayar=None):
    """journald'a yazan servisler (dosya günlüğü olmayanlar) — ucuz keşif.

    Tek bir `systemctl show` çağrısıyla kurulu birimler bulunur (~30–90 ms) ve
    yalnızca **çalışan/başarısız** olanlar listeye girer. İçerik okunmaz; pano
    kartında "journal" yazar, satıra dokununca `journalctl` çıktısı açılır.
    """
    from . import servisler as S
    if not S.systemd_var():
        return []
    # kullanıcının kendi ekledikleri de olabilir: journal:birim  biçiminde
    ek = [str(x) for x in (ayar or {}).get("log_dosyalari") or []
          if str(x).startswith("journal:")]
    tablo = list(JOURNAL_KAYNAKLARI) + [
        ("ozel", x.split(":", 1)[1], _birim_adi(x.split(":", 1)[1])) for x in ek]
    birimler = sorted({b for _g, _e, b in tablo if b != CEKIRDEK_BIRIMI})
    var_olan = set()
    if birimler:
        kod, cikti = S._calistir(["systemctl", "show", *birimler,
                                  "-p", "Id,LoadState,ActiveState"], 8)
        if kod == 0:
            for kayit in S.show_ayristir(cikti):
                ad = kayit.get("Id") or ""
                # yalnızca kurulu **ve** çalışan/başarısız birimler: durmuş bir
                # servisin boş günlüğü kartta gereksiz yer kaplar
                if (ad and kayit.get("LoadState") not in (None, "", "not-found")
                        and kayit.get("ActiveState") in ("active", "activating",
                                                         "reloading", "failed")):
                    var_olan.add(ad)
    # çekirdek günlüğü: journalctl varsa her zaman anlamlıdır
    from .. import ortam
    cekirdek_var = ortam.komut_var("journalctl")
    kaynaklar = []
    for grup, etiket, birim in tablo:
        if birim == CEKIRDEK_BIRIMI:
            if not cekirdek_var:
                continue
        elif birim not in var_olan and birim.split(".")[0] not in var_olan:
            continue
        kaynaklar.append({
            "tur": "journal",
            "grup": grup,
            "etiket": etiket,
            "ad": "çekirdek günlüğü" if birim == CEKIRDEK_BIRIMI else birim,
            "yol": "",
            "birim": birim,
            "boyut": 0,
            "son": 0.0,
            "okunabilir": True,
        })
    return kaynaklar


def _sirala(kaynaklar):
    """Grup sırasına, sonra **dosya kaynaklarına** (en yeni önce), en son
    journal kaynaklarına göre sıralar."""
    def anahtar(k):
        try:
            grup = GRUP_SIRASI.index(k["grup"])
        except ValueError:
            grup = len(GRUP_SIRASI)
        journal = 1 if k.get("tur") == "journal" else 0
        return (grup, journal, -k["son"], k["ad"])
    return sorted(kaynaklar, key=anahtar)


def bul(desen_listesi=None, ayar=None, journal=True):
    """Var olan günlük kaynaklarını bulur: dosyalar + journald servisleri."""
    gorulen, kaynaklar = set(), []
    for grup, etiket, desen in (desen_listesi if desen_listesi is not None
                                else DESENLER):
        for yol in _genislet(desen):
            anahtar = os.path.realpath(yol)
            if anahtar in gorulen:
                continue
            kayit = _satir(grup, etiket, yol)
            if kayit:
                gorulen.add(anahtar)
                kaynaklar.append(kayit)
    if journal:
        kaynaklar += journal_kaynaklari(ayar)
    return _sirala(kaynaklar)


def tazele(kaynaklar):
    """Boyut ve son yazılma bilgisini yeniler (dosya içeriği okunmaz)."""
    yeni = []
    for k in kaynaklar:
        if k.get("tur") == "journal":
            yeni.append(k)                    # stat gerekmez
            continue
        kayit = _satir(k["grup"], k["etiket"], k["yol"])
        if kayit:
            yeni.append(kayit)
    return _sirala(yeni)


def gunluk(yol, satir=200):
    """Bir günlük dosyasının sonunu okur: (metin, kaynak)."""
    yol = os.path.expanduser(str(yol))
    if not os.path.exists(yol):
        return f"(dosya yok: {yol})", "yok"
    if not os.access(yol, os.R_OK):
        return (f"(izin yok: {yol})\n\n"
                "Çözüm: kullanıcıyı günlükleri okuyan gruba ekleyin, örneğin\n"
                "  sudo usermod -aG adm $USER      # Debian/Ubuntu/Pi\n"
                "  sudo usermod -aG systemd-journal $USER   # journalctl için\n"
                "Sonra oturumu kapatıp açın (gruplar oturumda etkinleşir)."), "izin yok"
    return ortak.kuyruk(yol, satir, AZAMI_BAYT), "dosya"


def gunluk_journal(birim, satir=200):
    """journald'a yazan bir servisin günlüğü: (metin, kaynak)."""
    from . import servisler as S
    if str(birim) == CEKIRDEK_BIRIMI:
        kod, cikti = S._calistir(["journalctl", "-k", "-n", str(satir),
                                  "--no-pager", "-o", "short-iso"], 10)
        metin = (cikti or "").strip()
        if kod != 0 or not metin:
            kod, cikti = S._calistir(["journalctl", "-k", "-n", str(satir),
                                      "--no-pager"], 10)
            metin = (cikti or "").strip()
        if not metin:
            return "(çekirdek günlüğü boş)", "journalctl"
        return metin, "journalctl -k"
    return S._journal(str(birim), satir), "journalctl"


def _satir_turu(metin):
    dusuk = metin.lower()
    if any(k in dusuk for k in HATA_KELIMELERI):
        return "hata"
    if any(k in dusuk for k in UYARI_KELIMELERI):
        return "uyari"
    return "bilgi"


def ozet(metin):
    """Metindeki hata/uyarı satırı sayısı."""
    hata = uyari = 0
    for satir in (metin or "").splitlines():
        tur = _satir_turu(satir)
        if tur == "hata":
            hata += 1
        elif tur == "uyari":
            uyari += 1
    return {"hata": hata, "uyari": uyari}


# ── dosya günlüklerinde zaman penceresi ─────────────────────────────────────
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
_EGIK = re.compile(r"(\d{4})/(\d{2})/(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
# Apache: [Thu Oct 08 16:42:53.327959 2026]  (yıl sonda)
_APACHE = re.compile(r"\[(\w{3}) (\w{3}) +(\d{1,2}) (\d{2}):(\d{2}):(\d{2})[^\]]*?(\d{4})\]")
_AYLAR = {a: i for i, a in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
     "Nov", "Dec"), start=1)}


def satir_zamani(satir):
    """Satırdaki zaman damgasını epoch'a çevirir (yoksa None) — saf fonksiyon.

    Desteklenen biçimler: ISO (`2026-10-10 12:48:12`, Laravel/journal), eğik
    çizgili (`2026/10/10 12:48:12`, nginx) ve Apache (`[Thu Oct 08 16:42:53 2026]`).
    """
    metin = str(satir or "")
    m = _ISO.search(metin) or _EGIK.search(metin)
    if m:
        try:
            return time.mktime(time.strptime("-".join(m.groups()[:3]) + " " +
                                             ":".join(m.groups()[3:]), "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return None
    m = _APACHE.search(metin)
    if m:
        ay = _AYLAR.get(m.group(2))
        if not ay:
            return None
        try:
            return time.mktime((int(m.group(7)), ay, int(m.group(3)), int(m.group(4)),
                                int(m.group(5)), int(m.group(6)), 0, 0, -1))
        except Exception:
            return None
    return None


def ozet_metin(metin, dakika=None, simdi=None):
    """Metindeki hata/uyarıları **son `dakika` dakikaya** göre sayar (saf).

    Damgalı satırlar yalnızca pencere içindeyse sayılır; damgasız satırlar
    (ör. devam satırları) her zaman sayılır. Hiç damga bulunamazsa `pencereli`
    False döner ve çağıran son satırlara (kuyruk) düşebilir.
    """
    dakika = int(dakika if dakika is not None else VARSAYILAN_PENCERE_DK)
    simdi = time.time() if simdi is None else simdi
    esik = simdi - dakika * 60
    hata = uyari = damgali = 0
    for satir in (metin or "").splitlines():
        t = satir_zamani(satir)
        if t is not None:
            damgali += 1
            if t < esik:
                continue
        tur = _satir_turu(satir)
        if tur == "hata":
            hata += 1
        elif tur == "uyari":
            uyari += 1
    return {"hata": hata, "uyari": uyari, "damgali": damgali,
            "pencereli": damgali > 0, "pencere_dk": dakika}


def ozet_dosya(yol, dakika=None, satir=400):
    """Bir günlük dosyasındaki hata/uyarıları zaman penceresine göre sayar."""
    metin = ortak.kuyruk(os.path.expanduser(str(yol)), satir, AZAMI_BAYT)
    return ozet_metin(metin, dakika)


def ozet_journal(birim, dakika=None, satir=2000):
    """journald kaynağında **son `dakika` dakikanın** hata/uyarı sayısı.

    Son 200 satıra bakmak yanıltıcı olabiliyordu: sakin bir günlükte aylar önceki
    açılış hataları hâlâ o pencerede kalıp "8 hata" gösteriyordu (Raspberry Pi'de
    MariaDB'de görüldü). Bu yüzden journal kaynaklarında sayım zaman penceresine
    göre yapılır; dosya kaynaklarında zaman damgası garantisi olmadığı için
    kuyruk (son satırlar) kullanılmaya devam eder.
    """
    from . import servisler as S
    dakika = int(dakika if dakika is not None else VARSAYILAN_PENCERE_DK)
    hedef = (["-k"] if str(birim) == CEKIRDEK_BIRIMI else ["-u", str(birim)])
    kod, cikti = S._calistir(["journalctl", *hedef, "--since", f"-{max(1, dakika)}min",
                              "-n", str(satir), "--no-pager", "-o", "cat"], 10)
    if kod != 0:
        return {"hata": 0, "uyari": 0, "satir": 0, "pencere_dk": dakika,
                "hata_mesaji": "okunamadı"}
    satirlar = (cikti or "").splitlines()
    o = ozet("\n".join(satirlar))
    return {"hata": o["hata"], "uyari": o["uyari"], "satir": len(satirlar),
            "pencere_dk": dakika}


def suz(metin, yalniz_hata=False):
    """Yalnızca hata/uyarı satırlarını bırakır (görüntüleyicideki süzgeç)."""
    if not yalniz_hata:
        return metin
    return "\n".join(s for s in (metin or "").splitlines()
                     if _satir_turu(s) in ("hata", "uyari"))


# ─── toplayıcı arayüzü ───────────────────────────────────────────────────────
def oku(d, ayar):
    simdi = ortak.zaman()

    # keşif: pahalı, seyrek
    if d.log_kaynaklar is None or simdi - d.log_kesif > KESIF_OMRU:
        d.log_kaynaklar = bul(desenler(ayar), ayar=ayar)
        d.log_kesif = simdi
        d.log_son = 0.0                 # keşif sonrası ilk ölçüm hemen yapılsın

    # boyut/yaş: ucuz ama her saniye de gerekmez
    if d.log_son and simdi - d.log_son < STAT_ARALIK:
        return d.log_sonuc

    kaynaklar = tazele(d.log_kaynaklar)
    sonuc = {"kaynaklar": kaynaklar, "toplam": len(kaynaklar),
             "yok": not kaynaklar}
    d.log_sonuc = sonuc
    d.log_son = simdi
    return sonuc
