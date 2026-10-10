"""Belge–kod uyum testleri: README ve ayarlar koddan kopmasın.

Belgeler elle yazılır; kod değişince geride kalırlar. Bu testler kopmayı
yakalar:

* README'deki `config.json` örneği gerçek varsayılanlarla **aynı** olmalı.
* Her ayar anahtarı kodda **okunuyor** olmalı (ölü anahtar kalmasın).
* README'de yazan test sayısı gerçek test sayısına eşit olmalı.
* Koda kart eklenirse README onu anmalı.
* Komut satırına seçenek eklenirse README onu anmalı.
* `cihaz/yedek.py` içindeki varsayılanlar ayarlarla aynı olmalı.
* CHANGELOG'un en üst kaydı koddaki sürümle aynı olmalı.

İsteğe bağlı: `SYSPANO_WIKI` değişkeni bir wiki kopyasını gösteriyorsa test
sayısı orada da denetlenir (ör. `SYSPANO_WIKI=/tmp/wiki-clone ./tests/run.sh belgeler`).

Tk gerekmez, görüntüsüz ortamda çalışır.
"""

import json
import os
import pathlib
import re

from syspano import __version__, ayar
from syspano.arayuz import yerlesim
from syspano.cihaz import yedek

KOK = pathlib.Path(__file__).resolve().parent.parent
TESTLER = KOK / "tests"


def _readme():
    return (KOK / "README.md").read_text(encoding="utf-8")


def _json_blogu(metin, baslik="## Yapılandırma"):
    """Başlıktan sonraki ilk ```json bloğunu sözlük olarak döndürür."""
    kuyruk = metin.split(baslik, 1)
    assert len(kuyruk) == 2, f"README'de '{baslik}' başlığı yok"
    eslesme = re.search(r"```json\s*\n(.*?)```", kuyruk[1], re.S)
    assert eslesme, f"'{baslik}' başlığından sonra ```json bloğu yok"
    return json.loads(eslesme.group(1))


def test_readme_yapilandirma_ornegi_varsayilanlarla_ayni():
    """README'deki örnek `config.json`, `--varsayilan-yapilandirma` ile aynı olmalı."""
    ornek = _json_blogu(_readme())
    eksik = sorted(set(ayar.VARSAYILAN) - set(ornek))
    fazla = sorted(set(ornek) - set(ayar.VARSAYILAN))
    assert not eksik, f"README örneğinde olmayan anahtar: {eksik}"
    assert not fazla, f"README örneğinde koddan olmayan anahtar: {fazla}"
    for anahtar, deger in ayar.VARSAYILAN.items():
        assert ornek[anahtar] == deger, (
            f"README örneğinde {anahtar} = {ornek[anahtar]!r}, "
            f"kodda {deger!r}")


def test_varsayilan_anahtarlar_kodda_kullaniliyor():
    """Ölü ayar anahtarı kalmasın: her anahtar ayar.py dışında okunmalı."""
    kaynak = {}
    for dosya in (KOK / "src" / "syspano").rglob("*.py"):
        if dosya.name == "ayar.py":
            continue
        kaynak[dosya] = dosya.read_text(encoding="utf-8")
    kullanilmayan = sorted(
        anahtar for anahtar in ayar.VARSAYILAN
        if not any(f'"{anahtar}"' in metin or f"'{anahtar}'" in metin
                   for metin in kaynak.values()))
    assert not kullanilmayan, (
        f"bu ayar anahtarlarını hiçbir modül okumuyor: {kullanilmayan}")


def _sayilar(metin):
    """Belgelerde yazan (dosya, test) çiftleri."""
    bulunan = re.findall(r"(\d+) dosya(?:da)?[^\n]*?(\d+) test", metin)
    # ikinci kalıpta sıra ters: "<test> test / <dosya> dosya"
    bulunan += [(d, t) for t, d in re.findall(r"(\d+) test\s*/\s*(\d+) dosya", metin)]
    return [(int(a), int(b)) for a, b in bulunan]


def test_belge_test_sayisi_dogru():
    """README'de yazan test sayısı gerçek sayıya eşit olmalı."""
    dosyalar = sorted(TESTLER.glob("test_*.py"))
    testler = sum(len(re.findall(r"^def test_", d.read_text(encoding="utf-8"), re.M))
                  for d in dosyalar)
    beklenen = (len(dosyalar), testler)

    sayilar = _sayilar(_readme())
    assert sayilar, "README'de test sayısı yazan bir cümle bulunamadı"
    for bulunan in sayilar:
        assert bulunan == beklenen, (
            f"README {bulunan[0]} dosyada {bulunan[1]} test diyor, "
            f"gerçek: {beklenen[0]} dosyada {beklenen[1]} test")

    wiki = os.environ.get("SYSPANO_WIKI")
    if wiki and pathlib.Path(wiki).is_dir():
        for sayfa in sorted(pathlib.Path(wiki).glob("*.md")):
            for bulunan in _sayilar(sayfa.read_text(encoding="utf-8")):
                assert bulunan == beklenen, (
                    f"{sayfa.name} {bulunan[0]} dosyada {bulunan[1]} test diyor, "
                    f"gerçek: {beklenen[0]} dosyada {beklenen[1]} test")


def test_readme_tum_kartlari_anar():
    """Koda kart eklenirse README de anmalı."""
    readme = _readme()
    eksik = [k for k in yerlesim.KART_BILGI if f'"{k}"' not in readme]
    assert not eksik, f"README'de anılmayan kart: {eksik}"
    assert yerlesim.KART_BILGI, "hiç kart tanımlı değil"


def test_readme_tum_secenekleri_anar():
    """Komut satırına seçenek eklenirse README de anmalı."""
    kaynak = (KOK / "src" / "syspano" / "cli.py").read_text(encoding="utf-8")
    bayraklar = set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', kaynak))
    assert bayraklar, "cli.py'de seçenek bulunamadı"
    readme = _readme()
    eksik = sorted(b for b in bayraklar if b not in readme)
    assert not eksik, f"README'de anılmayan seçenek: {eksik}"


def test_yedek_varsayilanlari_ayarla_ayni():
    """`cihaz/yedek.py` sabitleri ayar varsayılanlarıyla aynı kalmalı."""
    assert yedek.VARSAYILAN_YOL == ayar.VARSAYILAN["yedek_durum_yolu"]
    assert yedek.VARSAYILAN_ZAMANLAYICI == ayar.VARSAYILAN["yedek_zamanlayici"]


def test_changelog_en_ust_surum_kodla_ayni():
    """Sürüm yükseltilip CHANGELOG kaydı unutulmasın.

    CHANGELOG 1.14.1'de kalıp 1.15.1–1.17.0 kayıtları atlanmıştı; bu test
    aynı kaymanın tekrarını yakalar.
    """
    changelog = (KOK / "CHANGELOG.md").read_text(encoding="utf-8")
    basliklar = re.findall(r"^## \[([^\]]+)\]", changelog, re.M)
    assert basliklar, "CHANGELOG'da sürüm başlığı yok"
    assert basliklar[0] == __version__, (
        f"CHANGELOG'un en üst kaydı {basliklar[0]}, kodda sürüm {__version__}")


if __name__ == "__main__":
    import sys
    import traceback
    gecen, kalan = 0, 0
    print(f"SysPano {__version__}")
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
