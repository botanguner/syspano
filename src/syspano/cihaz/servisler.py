"""Servisler: systemd birimlerinin durumu ve günlükleri.

Sunucu makinelerde Apache, MySQL, PostgreSQL, nginx, Docker gibi servislerin
çalışıp çalışmadığını gösterir ve günlüklerine erişim sağlar.

**Maliyet (ölçüldü, bu sınıf makinelerde):**

| Çağrı | Süre | Ne zaman |
|---|---|---|
| `systemctl list-units` (216 birim) | ~0,10 sn | yalnızca **keşif**: açılışta ve 10 dakikada bir |
| `systemctl show <birimler>` | 0,03–0,09 sn | durum sorgusu, `servis_aralik` (varsayılan 30 sn) |
| `journalctl -u <birim> -n N` | ~0,02–0,10 sn | yalnızca günlük görüntüleyici açıkken |

`servis_aralik` ölçümle seçildi (12 servisli bir sistemde): 10 saniyede bir
sormak **8,7 ms/sn**, 30 saniyede bir sormak **2,9 ms/sn**. Servis durumu çok
sık değişmediği için 30 saniye yeterli; kartı daha taze isterseniz değeri
düşürebilirsiniz.

Keşifte şu birimler seçilir: kullanıcının yapılandırdıkları, yaygın sunucu
servisleri (kurulu olanlar) ve **başarısız (failed)** birimler. Sonra yalnızca
bu birimler sorgulanır.
"""

import os
import re
import subprocess
import time

from . import ortak

# Keşifte bakılacak yaygın sunucu/sistem servisleri (kurulu olmayanlar elenir)
YAYGIN = (
    "apache2", "httpd", "nginx", "mysql", "mysqld", "mariadb", "postgresql",
    "docker", "podman", "redis-server", "redis", "memcached", "mongod",
    "elasticsearch", "rabbitmq-server", "php-fpm", "php8.2-fpm", "php8.3-fpm",
    "vsftpd", "smbd", "nmb", "named", "bind9", "dovecot", "postfix", "exim4",
    "samba", "nfs-server", "ssh", "sshd", "cron", "crond", "cups",
    "bluetooth", "NetworkManager", "fail2ban", "ufw", "firewalld",
    "zabbix-agent", "prometheus", "grafana-server", "influxdb",
)

# Ekranda görünecek kısa adlar (birim adı → etiket)
ETIKET = {
    "apache2": "Apache", "httpd": "Apache", "nginx": "nginx",
    "mysql": "MySQL", "mysqld": "MySQL", "mariadb": "MariaDB",
    "postgresql": "PostgreSQL", "docker": "Docker", "podman": "Podman",
    "redis-server": "Redis", "redis": "Redis", "memcached": "Memcached",
    "mongod": "MongoDB", "elasticsearch": "Elasticsearch",
    "rabbitmq-server": "RabbitMQ", "php-fpm": "PHP-FPM",
    "vsftpd": "FTP", "smbd": "Samba", "nmb": "Samba (ad)", "samba": "Samba",
    "named": "DNS (BIND)", "bind9": "DNS (BIND)", "dovecot": "IMAP/POP",
    "postfix": "Postfix", "exim4": "Exim", "nfs-server": "NFS",
    "ssh": "SSH", "sshd": "SSH", "cron": "Zamanlayıcı", "crond": "Zamanlayıcı",
    "cups": "Yazıcı (CUPS)", "bluetooth": "Bluetooth",
    "NetworkManager": "Ağ", "fail2ban": "Fail2ban", "ufw": "Güvenlik duvarı",
    "firewalld": "Güvenlik duvarı", "zabbix-agent": "Zabbix",
    "prometheus": "Prometheus", "grafana-server": "Grafana", "influxdb": "InfluxDB",
}

KESIF_OMRU = 600.0        # saniye; birim listesi bu sürede bir tazelenir
VARSAYILAN_ARALIK = 30.0  # saniye; durum sorgusu aralığı (ölçümle seçildi: 10 sn = 8,7 ms/sn, 30 sn = 2,9 ms/sn)
_SHOW_ALANLARI = ("Id,ActiveState,SubState,LoadState,UnitFileState,"
                  "ActiveEnterTimestamp,MemoryCurrent,MainPID")


def systemd_var():
    """Sistem systemd ile mi yönetiliyor?"""
    return os.path.isdir("/run/systemd/system")


# ─── ayrıştırıcılar (saf; test edilebilir) ───────────────────────────────────
def show_ayristir(metin):
    """`systemctl show A B -p ...` çıktısını birim sözlüklerine çevirir.

    Çıktı, aralarında boş satır bulunan bloklardan oluşur; her blok bir birimdir
    ve sırası verilen birim sırasıyla aynıdır (birim adı blokta geçmez).
    """
    birimler = []
    for blok in (metin or "").split("\n\n"):
        kayit = {}
        for satir in blok.splitlines():
            if "=" not in satir:
                continue
            anahtar, deger = satir.split("=", 1)
            anahtar = anahtar.strip()
            if anahtar:
                kayit[anahtar] = deger.strip()
        if kayit:
            birimler.append(kayit)
    return birimler


def list_ayristir(metin):
    """`systemctl list-units --type=service --no-legend --plain` çıktısını ayırır.

    Biçim: 'birim.adı  loaded  active  running  Açıklama metni'
    """
    birimler = []
    for satir in (metin or "").splitlines():
        p = satir.split(None, 4)
        if len(p) < 4 or not p[0].endswith(".service"):
            continue
        birimler.append({"ad": p[0], "yuk": p[1], "durum": p[2],
                         "alt": p[3], "aciklama": p[4] if len(p) > 4 else ""})
    return birimler


def zaman_ayristir(metin):
    """'Wed 2026-10-07 13:36:18 +03' → epoch (okunamazsa None)."""
    metin = (metin or "").strip()
    if not metin or metin in ("n/a", "0"):
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", metin)
    if not m:
        return None
    try:
        return time.mktime(time.strptime("-".join(m.groups()[:3]) + " " +
                                         ":".join(m.groups()[3:]), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def etiket(ad):
    """Birim adından okunur etiket: 'apache2.service' → 'Apache'."""
    temel = ad[:-len(".service")] if ad.endswith(".service") else ad
    if temel in ETIKET:
        return ETIKET[temel]
    # 'postgresql@14-main' gibi örnekli birimlerde taban adı kullan
    taban = temel.split("@", 1)[0]
    if taban in ETIKET:
        return ETIKET[taban]
    return temel.replace("-", " ").replace("_", " ").title()


# ─── systemctl yardımcıları ──────────────────────────────────────────────────
def _calistir(cmd, zaman):
    try:
        c = subprocess.run(cmd, capture_output=True, text=True, timeout=zaman)
        return c.returncode, c.stdout or ""
    except Exception:
        return 1, ""


def _kesif(ayar):
    """İzlenecek birimleri bulur: yapılandırılanlar + ayakta olanlar + failed."""
    adaylar = list(ayar.get("servisler") or [])
    yapilandirilan = {a if a.endswith(".service") else a + ".service" for a in adaylar}
    adaylar = sorted({a if a.endswith(".service") else a + ".service" for a in YAYGIN}
                     | yapilandirilan)

    secili = set(yapilandirilan)
    # 1) yaygın servislerden kurulu olanlar
    kod, cikti = _calistir(["systemctl", "show", *adaylar, "-p", "Id,LoadState"], 8)
    if kod == 0:
        # Blokları konuma göre eşleştirmek YANLIŞ olur: systemd takma adları
        # asıl ada çevirir (ör. mysqld.service → mariadb.service). Bu yüzden
        # birim adı her bloğun içindeki `Id` alanından okunur.
        for kayit in show_ayristir(cikti):
            ad = kayit.get("Id") or ""
            if ad and kayit.get("LoadState") not in (None, "", "not-found"):
                secili.add(ad)
    # 2) başarısız birimler (tek çağrı; önemli olduğu için her keşifte bakılır)
    kod, cikti = _calistir(["systemctl", "list-units", "--type=service",
                            "--state=failed", "--no-legend", "--plain"], 8)
    if kod == 0:
        for b in list_ayristir(cikti):
            secili.add(b["ad"])
    return sorted(secili)


def _durum_oku(birimler):
    """Verilen birimlerin durumunu TEK çağrıyla okur (ada göre eşleştirir)."""
    if not birimler:
        return []
    kod, cikti = _calistir(["systemctl", "show", *birimler, "-p", _SHOW_ALANLARI], 8)
    if kod != 0:
        return []
    sonuc = []
    for kayit in show_ayristir(cikti):
        ad = kayit.get("Id") or ""
        if not ad or kayit.get("LoadState") == "not-found":
            continue
        bellek = ortak.sayi(kayit.get("MemoryCurrent"))
        if bellek is not None and bellek >= 2 ** 63 - 1:      # 'infinity'
            bellek = None
        sonuc.append({
            "ad": ad,
            "etiket": etiket(ad),
            "durum": kayit.get("ActiveState") or "bilinmiyor",
            "alt": kayit.get("SubState") or "",
            "baslama": zaman_ayristir(kayit.get("ActiveEnterTimestamp")),
            "bellek": bellek,
            "pid": int(ortak.sayi(kayit.get("MainPID")) or 0),
        })
    return sonuc


# ─── günlük okuma ────────────────────────────────────────────────────────────
def kuyruk(yol, satir=200):
    """Dosyanın son `satir` satırı (ortak.kuyruk ile aynı; bkz. `cihaz/ortak.py`)."""
    return ortak.kuyruk(yol, satir)


def gunluk(ad, satir=200, ayar=None):
    """Bir birimin günlüğünü döndürür: (metin, kaynak).

    Yapılandırmada bu birim için bir log dosyası tanımlıysa önce o denenir
    (Apache'nin `/var/log/apache2/error.log` gibi kendi günlükleri), yoksa
    `journalctl` kullanılır.
    """
    ayar = ayar or {}
    dosyalar = ayar.get("servis_log_dosyalari") or {}
    # Hem 'apache2' hem 'apache2.service' yazılmış olabilir; iki yönü de dene
    temel = ad[:-len(".service")] if ad.endswith(".service") else ad
    yol = dosyalar.get(ad) or dosyalar.get(temel) or dosyalar.get(temel + ".service")
    if yol:
        yol = os.path.expanduser(yol)
        if os.path.exists(yol):
            return kuyruk(yol, satir), yol
        return f"(log dosyası bulunamadı: {yol})\n\njournalctl deneniyor…\n" + \
            _journal(ad, satir), yol
    return _journal(ad, satir), "journalctl"


def _journal(ad, satir):
    kod, cikti = _calistir(["journalctl", "-u", ad, "-n", str(satir),
                            "--no-pager", "-o", "short-iso"], 10)
    if kod != 0 or not cikti.strip():
        kod2, cikti2 = _calistir(["journalctl", "-u", ad, "-n", str(satir),
                                  "--no-pager"], 10)
        cikti = cikti2 or cikti
    metin = (cikti or "").strip()
    if not metin:
        return ("(günlük kaydı yok — servis hiç çalışmamış ya da journald bu "
                "birim için kayıt tutmuyor)")
    return metin


# ─── toplayıcı arayüzü ───────────────────────────────────────────────────────
def oku(d, ayar):
    if not systemd_var():
        return {"yok": True}

    simdi = ortak.zaman()
    aralik = max(2.0, float(ayar.get("servis_aralik") or VARSAYILAN_ARALIK))

    # keşif: seyrek (pahalı çağrı)
    if d.servis_birimler is None or simdi - d.servis_kesif > KESIF_OMRU:
        d.servis_birimler = _kesif(ayar)
        d.servis_kesif = simdi
        d.servis_son = 0.0            # keşif sonrası ilk durumu hemen oku

    # durum: arada son sonucu döndür
    if d.servis_son and simdi - d.servis_son < aralik:
        return d.servis_sonuc

    birimler = _durum_oku(d.servis_birimler)
    sonuc = {"birimler": birimler, "toplam": len(birimler),
             "aralik": aralik, "yok": False}
    d.servis_sonuc = sonuc
    d.servis_son = simdi
    return sonuc
