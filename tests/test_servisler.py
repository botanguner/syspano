"""Servis toplayıcısı testleri.

Ayrıştırıcılar **saf** olduğu için gerçek systemd'ye ihtiyaç duymaz; örnek
çıktılarla sınanır. Birkaç test gerçek sistemi de dener ama esnek yazılmıştır
(systemd yoksa atlanır).
"""

import os
import tempfile

from syspano.cihaz import servisler as S
from syspano.toplayici import Toplayici

ORNEK_SHOW = """Id=apache2.service
LoadState=loaded
ActiveState=active
SubState=running
ActiveEnterTimestamp=Wed 2026-10-07 13:36:18 +03
MemoryCurrent=12345678
MainPID=1208

Id=mariadb.service
LoadState=loaded
ActiveState=inactive
SubState=dead
ActiveEnterTimestamp=
MemoryCurrent=18446744073709551615
MainPID=0
"""

ORNEK_LIST = """apache2.service      loaded    active   running Apache HTTP Server
mariadb.service      loaded    inactive dead    MariaDB 10.11 database server
  sshd.service       loaded    failed   failed  OpenSSH server daemon
not-a-service.target loaded    active   active  Bir hedef
"""


# ─── ayrıştırıcılar ──────────────────────────────────────────────────────────
def test_show_ayristir():
    kayitlar = S.show_ayristir(ORNEK_SHOW)
    assert len(kayitlar) == 2, kayitlar
    assert kayitlar[0]["Id"] == "apache2.service"
    assert kayitlar[0]["ActiveState"] == "active"
    assert kayitlar[1]["Id"] == "mariadb.service"
    assert kayitlar[1]["SubState"] == "dead"


def test_show_ayristir_bos():
    assert S.show_ayristir("") == []
    assert S.show_ayristir(None) == []


def test_list_ayristir():
    kayitlar = S.list_ayristir(ORNEK_LIST)
    assert len(kayitlar) == 3, kayitlar          # .target atlanmalı
    assert kayitlar[0] == {"ad": "apache2.service", "yuk": "loaded",
                           "durum": "active", "alt": "running",
                           "aciklama": "Apache HTTP Server"}
    assert kayitlar[1]["durum"] == "inactive"
    assert kayitlar[2]["durum"] == "failed"      # boşlukla başlayan satır da okunur


def test_list_ayristir_sadece_servis():
    assert all(k["ad"].endswith(".service") for k in S.list_ayristir(ORNEK_LIST))


def test_zaman_ayristir():
    assert S.zaman_ayristir("Wed 2026-10-07 13:36:18 +03") is not None
    assert S.zaman_ayristir("2026-10-07 13:36:18") is not None
    assert S.zaman_ayristir("") is None
    assert S.zaman_ayristir("n/a") is None
    assert S.zaman_ayristir("0") is None
    assert S.zaman_ayristir("saçma") is None


def test_etiket():
    assert S.etiket("apache2.service") == "Apache"
    assert S.etiket("mysqld.service") == "MySQL"
    assert S.etiket("postgresql@14-main.service") == "PostgreSQL"
    assert S.etiket("cups.service") == "Yazıcı (CUPS)"
    assert S.etiket("bilinmeyen-servis.service") == "Bilinmeyen Servis"


# ─── takma ad (alias) sorunu ─────────────────────────────────────────────────
def test_durum_oku_takma_adi_cozer():
    """`systemctl show`, takma adları **asıl** ada çevirir.

    (mysqld.service → mariadb.service). Blokları istenen sıraya göre eşleştirmek
    yanlış sonuç verirdi; birim adı her bloğun `Id` alanından okunmalı.
    """
    gercek = S._calistir
    S._calistir = lambda cmd, zaman: (0, (
        "Id=httpd.service\nActiveState=inactive\nSubState=dead\nLoadState=loaded\n\n"
        "Id=mariadb.service\nActiveState=active\nSubState=running\nLoadState=loaded\n"))
    try:
        kayitlar = S._durum_oku(["httpd.service", "mysqld.service"])
    finally:
        S._calistir = gercek
    assert [k["ad"] for k in kayitlar] == ["httpd.service", "mariadb.service"], kayitlar
    assert kayitlar[0]["etiket"] == "Apache"
    assert kayitlar[1]["etiket"] == "MariaDB"
    assert kayitlar[0]["durum"] == "inactive"
    assert kayitlar[1]["durum"] == "active"


def test_durum_oku_bulunamayan_birimi_atlar():
    gercek = S._calistir
    S._calistir = lambda cmd, zaman: (0, "Id=yok.service\nLoadState=not-found\nActiveState=inactive\n")
    try:
        assert S._durum_oku(["yok.service"]) == []
    finally:
        S._calistir = gercek


def test_bellek_infinity_temizlenir():
    gercek = S._calistir
    S._calistir = lambda cmd, zaman: (0, (
        "Id=a.service\nLoadState=loaded\nActiveState=active\nSubState=running\n"
        f"MemoryCurrent={2 ** 64 - 1}\n"))
    try:
        kayitlar = S._durum_oku(["a.service"])
    finally:
        S._calistir = gercek
    assert kayitlar[0]["bellek"] is None, "sonsuz bellek değeri gösterilmemeli"


# ─── günlük ──────────────────────────────────────────────────────────────────
def test_kuyruk_dosya_sonu():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        for i in range(500):
            f.write(f"satır {i}\n")
        yol = f.name
    try:
        metin = S.kuyruk(yol, 5)
        assert metin.splitlines() == [f"satır {i}" for i in range(495, 500)]
        # dosyadan uzun istek: hepsi gelmeli, çökmemeli
        assert len(S.kuyruk(yol, 1000).splitlines()) == 500
    finally:
        os.remove(yol)


def test_kuyruk_olmayan_dosya():
    metin = S.kuyruk("/yok/boyle/bir/dosya.log", 5)
    assert "okunamadı" in metin


def test_gunluk_log_dosyasi_tercih_edilir():
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write("özel log dosyası\nikinci satır\n")
        yol = f.name
    try:
        metin, kaynak = S.gunluk("apache2.service", 10,
                                 {"servis_log_dosyalari": {"apache2": yol}})
        assert kaynak == yol and "özel log" in metin
        # birim adı ".service" ile de eşleşmeli
        metin2, kaynak2 = S.gunluk("apache2", 10,
                                   {"servis_log_dosyalari": {"apache2.service": yol}})
        assert kaynak2 == yol and "özel log" in metin2
    finally:
        os.remove(yol)


def test_gunluk_olmayan_dosya_journala_duser():
    metin, kaynak = S.gunluk("hicbir-servis-12345.service", 5,
                             {"servis_log_dosyalari": {"hicbir-servis-12345": "/yok/x.log"}})
    assert "bulunamadı" in metin


# ─── toplayıcı davranışı ─────────────────────────────────────────────────────
def test_oku_onbellek():
    """`servis_aralik` içinde systemctl yeniden çağrılmamalı."""
    if not S.systemd_var():
        print("    (systemd yok — atlandı)")
        return
    d = Toplayici({"guncelleme_ms": 1000, "servis_aralik": 60})
    sayac = {"n": 0}
    gercek = S._durum_oku

    def sayan(birimler):
        sayac["n"] += 1
        return gercek(birimler)

    S._durum_oku = sayan
    try:
        S.oku(d, d.ayar)
        ilk = sayac["n"]
        for _ in range(5):
            S.oku(d, d.ayar)
        assert sayac["n"] == ilk, "servis durumu her ölçümde yeniden sorgulanıyor"
    finally:
        S._durum_oku = gercek


def test_oku_yapisi():
    if not S.systemd_var():
        print("    (systemd yok — atlandı)")
        return
    d = Toplayici({"guncelleme_ms": 1000})
    v = S.oku(d, d.ayar)
    assert v.get("yok") is False
    assert isinstance(v["birimler"], list)
    for k in v["birimler"]:
        for alan in ("ad", "etiket", "durum", "alt", "baslama", "bellek", "pid"):
            assert alan in k, f"{alan} eksik"
        assert k["ad"].endswith(".service")


def test_systemd_yoksa_yok_doner():
    gercek = S.systemd_var
    S.systemd_var = lambda: False
    try:
        assert S.oku(Toplayici({}), {}) == {"yok": True}
    finally:
        S.systemd_var = gercek


if __name__ == "__main__":
    import sys
    import traceback
    gecen, kalan = 0, 0
    for ad, fonk in sorted(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            try:
                fonk()
                print(f"  ✓ {ad}")
                gecen += 1
            except Exception:
                print(f"  ✗ {ad}")
                traceback.print_exc()
                kalan += 1
    print(f"\n{gecen} geçti, {kalan} kaldı")
    sys.exit(1 if kalan else 0)
