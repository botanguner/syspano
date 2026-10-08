# SysPano sürüm geçmişi

Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) ·
Sürümleme: [Semantic Versioning](https://semver.org/lang/tr/).

## [1.6.0] — 2026-10-08

### Değişti
- **Günlük hata/uyarı sayımı artık zaman penceresine göre (journald).**
  "Son 200 satır" ölçütü yanıltıcıydı: sakin bir günlükte aylar önceki açılış
  hataları hâlâ o pencerede kalıp **"8 hata"** gösteriyordu — Raspberry Pi'de
  MariaDB'de tam olarak bu görüldü (düzeltmeden sonra da kart "8 hata" diyordu;
  oysa yeni açılışta hiç hata yoktu). Artık journald kaynaklarında sayım
  **son 60 dakikaya** göre yapılır; dosya kaynaklarında zaman damgası garantisi
  olmadığı için son satırlar kullanılmaya devam eder.
  - Yeni ayar: `log_pencere_dk` (varsayılan 60).
  - Yeni seçenek: `--log-pencere DK` (ör. `syspano --log mariadb --log-pencere 15`).
  - Görüntüleyici başlığı journal kaynaklarında pencereyi yazar:
    `journalctl · son 60 dk: 0 hata · 0 uyarı · mariadb.service`.
  - `--log-kaynaklar` çıktısında journal satırlarının sayımı da bu pencereye göre.

### Eklendi
- `loglar.ozet_journal(birim, dakika)`: `journalctl --since -Ndk -o cat` ile
  penceredeki hata/uyarı sayımı (çekirdek günlüğü için `-k`).
- 3 yeni test (toplam **14 dosyada 141 test**): pencere sayımı ve `--since`
  argümanı, çekirdek/varsayılan pencere, okunamayan journal'da güvenli sıfır.

## [1.5.0] — 2026-10-08

### Eklendi
- **journald günlük kaynakları: dosyaya yazmayan servisler de panoda.** Debian /
  Ubuntu / Raspberry Pi OS'ta MariaDB, PostgreSQL, Redis, Docker ve SSH
  günlüklerini dosyaya değil **journald**'a yazar (`/var/log/mysql/error.log`
  yoktur; `rsyslog` kurulu değilse `/var/log/syslog` de yoktur). GÜNLÜKLER kartı
  artık bunları `journalctl` üzerinden listeler:
  - **MariaDB, MySQL, PostgreSQL, Redis, Docker, SSH** ve **çekirdek günlüğü**
    (`journalctl -k`).
  - Keşif **tek** `systemctl show` çağrısıyla yapılır (~30–90 ms) ve yalnızca
    kurulu **ve** çalışan/başarısız birimler listeye girer — durmuş bir servisin
    boş günlüğü kartta yer kaplamaz.
  - Kart satırında sağda `journal` yazar (dosya kaynaklarında yaş · boyut).
    Satıra dokununca görüntüleyici `journalctl` çıktısını açar; başlıkta okunur
    ad (ör. `MariaDB`) ve birim adı görünür. Hata/uyarı sayısı ve **Yalnız hata**
    süzgeci journal kaynaklarında da çalışır.
  - `log_dosyalari` içine `"journal:benim-servisim"` yazarak kendi birimlerinizi
    ekleyebilirsiniz (kısa ad `.service` olarak tamamlanır).
- `cihaz/loglar.py`: `journal_kaynaklari()`, `gunluk_journal()`; `bul()` artık
  dosya + journal kaynaklarını birlikte döndürür (dosya kaynakları önce).
- `syspano --log-kaynaklar` çıktısı journal kaynaklarını da listeler (hata/uyarı
  sayısıyla); `syspano --log BIRIM` ile içeriği yazdırılır.

### Değişti
- GÜNLÜKLER kartında sıralama: aynı grup içinde **dosya kaynakları önce** (en
  yeni yazılan en üstte), journal kaynakları sonra.

### Ölçüm (Raspberry Pi 4)
- Dosya keşfi **2,67 ms**; journald birimleri için **tek** `systemctl show`
  çağrısı eklenir. İkisi birlikte 10 dakikada bir çalışır (saniyeye düşen
  maliyet ~0,2 ms); tazeleme dosya başına ~0,06 ms (journal kaynaklarında stat
  yok).
- Panelin toplam CPU'su: **%3,8** tek çekirdek (`guncelleme_ms=2000`).

### Test
- 6 yeni test (toplam **14 dosyada 138 test**): journal keşfi (tek çağrı, yalnız
  çalışan birimler), dosya-journal sıralaması, `journal:birim` yapılandırması,
  `journalctl -k`/`-u` çağrıları, kartta `log_journal` eylemi ve "journal"
  etiketi, görüntüleyicide journal kaynağı.

## [1.4.3] — 2026-10-08

### Düzeltildi
- **Kısa kartlar boş kalıyordu.** Raspberry Pi'nin 1 sütunlu düzeninde (tasarım
  uzayı 533×320) **GEÇMİŞ** kartı yalnızca başlığı gösteriyordu: kart, alttaki
  açıklama satırına (CPU/BELLEK/SICAKLIK) 34 birim ayırıp eğriler için yer
  kalmayınca hiçbir şey çizmiyordu. Artık **eğriler her zaman çizilir**;
  açıklama satırı yalnızca yer varsa eklenir (kart 96 birimden kısaysa atlanır).
  Aynı sorunun GPU kartındaki biçimi de düzeltildi: çok kısa kaldığında yalnızca
  başlık çiziyordu, artık en azından GPU modelini yazar.
- Liste kartlarında "+N daha" satırı, kart çok kısaysa **hiç çizilmez** (1.4.2'de
  yer ayırma eklendi; çok kısa kartta yer de yetmediği için satırların üstüne
  binmesin diye tamamlandı).

### Eklendi
- İki yeni kart testi: **"hiçbir kart boş kalmaz"** (her kart en az bir içerik
  öğesi çizmeli) ve liste kartlarında **"+N daha" çakışması**. Test boyutlarına
  Pi'nin kısa kart yükseklikleri eklendi (533×72, 360×66 tasarım birimi) —
  bu boyutlar olmadan iki hata da gözden kaçıyordu. Testler eski kodda
  `gecmis 533x72: 2 öğe` ve `servisler … '+3 servis daha' ↔ 'nginx'` hatasını
  veriyor.

## [1.4.2] — 2026-10-08

### Düzeltildi
- **Liste kartlarında "+N daha" yazısı son satırın üstüne biniyordu.** Kısa bir
  SERVİSLER kartında son satır ile "+7 servis daha" iç içe geçiyordu (Raspberry
  Pi 800×480 panelinde görüldü: "Bluetooth" yazısının üzerine biniyordu).
  Artık liste taşıyorsa alttaki "+N daha" satırı için **yer ayrılıyor**; satır
  yüksekliği ve sığan satır sayısı buna göre hesaplanıyor
  (`kartlar._liste_yerlesimi`, SERVİSLER ve GÜNLÜKLER kartları paylaşıyor).
  Yeni test, "daha" yazısının başka bir metinle kesişmesini denetliyor (eski
  kodda 4 çakışma yakalıyor).
- **`guncelle.sh` her durumda `systemctl --user restart syspano` öneriyordu.**
  Panonun systemd kullanıcı servisi olmadığı makinelerde (ör. Raspberry Pi'de
  oturum açılışında `.desktop` ile başlıyor) bu komut hata veriyordu. Artık
  yönerge ortama göre: servis varsa `systemctl --user restart syspano`, yoksa
  **"panoda: ⚙ → Panoyu yeniden başlat"**.

## [1.4.1] — 2026-10-08

### Düzeltildi
- **Ayarlar ekranındaki güncelleme akışı sonuçsuz kalıyordu.** Düğmeye
  dokununca "denetleniyor" bildirimi 2,5 saniyede kayboluyor, sonuç (güncel /
  yeni sürüm / denetlenemedi) yalnızca SÜRÜM kutusundaki soluk tek satırda
  **8 saniye sonra** beliriyordu; güncelleme bittikten sonra başarılı mı
  başarısız mı olduğu panoda hiç görünmüyor, panonun yeniden başlatılması
  gerektiği de söylenmiyordu. Artık:
  - SÜRÜM kutusunda **renkli durum satırı** var ve her aşamayı yazar:
    `⟳ Denetleniyor…`, `✓ Güncel · son denetim 5 dk önce`,
    `⬆ Yeni sürüm var: 1.4.1 — «Güncelle»ye dokunun`, `⚠ Denetlenemedi: …`,
    `⏳ Güncelleme sürüyor… (42 sn)`,
    `✓ Güncelleme tamam (1.4.1) — Panoyu yeniden başlatın`,
    `⚠ Güncelleme başarısız — …`.
  - Sonuç ayrıca **bildirim** olarak çıkar ve denetim sabit 8 saniye beklemek
    yerine **önbelleği izleyerek** sonucu yakalar (en fazla 30 saniye; aşılırsa
    kırmızı "zaman aşımı" uyarısı).
  - Güncelleme süreci durumu `~/.local/state/syspano/guncelleme-durum.json`'a
    yazılır; pano bunu izleyip bitişte/hatada haber verir. Pano güncelleme
    sırasında yeniden başlatılırsa izleme kaldığı yerden sürer.
  - **"Kurulu paket yeni, bellekteki kod eski"** durumu artık açıkça söylenir ve
    ⚙ düğmesindeki sarı nokta bu durumda da yanar: güncelleme sonrası pano
    yeniden başlatılmadan hiçbir şey değişmiyordu (Raspberry Pi'de canlı
    görüldü: 1.4.0 kuruluyken pano 1.3.2 kodunu çalıştırıyordu).
  - Yeniden başlatma yönergesi ortama göre verilir: systemd kullanıcı servisi
    varsa `systemctl --user restart syspano`, masaüstü oturumunda
    kendiliğinden başlatılıyorsa **⚙ → Panoyu yeniden başlat**. (Eski
    `guncelleme.log` her durumda systemctl öneriyordu; Pi'de böyle bir servis
    yok, komut hata veriyordu.)
- **Alt bilgi şeridi opak yapıldı.** Kaydırılan kart içeriği şeridin altından
  görünüp yazıyla çakışıyordu (Pi'nin 800×480 panelinde görüldü: "SICAKLIK /
  FAN" başlığı `800x480 (DSI-1) · ölçek 1,50` yazısının üstüne biniyordu).
- **⚙ düğmesindeki uyarı noktası her karede bir tuval öğesi sızdırıyordu**
  (ham `create_oval` etiketsiz kalıyordu): nokta göründüğü sürece kare başına
  bir öğe birikiyor, bellek ve çizim süresi büyüyordu. Artık çizim yardımcısı
  kullanılıyor — kare öğelerinin birikmediğini denetleyen test yakaladı.
- **Küçük ekranda kırpılan ölçek artık söylenir.** Raspberry Pi'de
  `"olcek": 2.8` yazıyordu ama pencere sınırı yüzünden etkin ölçek **1,50**'ydi;
  ayar ekranındaki kaydırıcı ise 2,80 gösteriyordu. Artık kırpma olduğunda
  ayar ekranı "Bu ekranda en fazla 1.50 uygulanabiliyor (istenen 2.80)" yazar.

### Eklendi
- `guncelleme.durum_metni()` — **saf** fonksiyon: aşama → (metin, renk).
- `guncelleme.surec_yaz()` / `surec_oku()` — güncelleme sürecinin durumu.
- `guncelleme.yeniden_baslat_gerekli()` — kurulu paketin dosya zamanını pano
  açılış anıyla karşılaştırır (sürümden bağımsız, en isabetli ölçüt);
  `kurulu_surum()` ve `yeniden_baslat_yolu()`.
- `syspano --guncelle-denetle` çalışan kod/kurulu paket ayrımını ve doğru
  yeniden başlatma yolunu yazar.
- Tepsi/komut dosyası (pano ↔ tepsi iletişimi) `gorunum:ayar` komutunu da kabul
  eder: ayar ekranı uzaktan/tepsiden açılabilir.
- **7 yeni test** (toplam **14 dosyada 130 test**): durum metninin tüm
  aşamaları, süreç durumu dosyası, yeniden başlatma tespiti, ortama göre
  yönerge, ayar ekranında durum satırı ve ölçek uyarısı, panoda uçtan uca
  denetim akışı.

## [1.4.0] — 2026-10-08

### Eklendi
- **GÜNLÜKLER kartı: geliştiricinin aradığı günlük dosyaları panoda.** Kart,
  bilinen günlük dosyalarını kendiliğinden bulur, **gruba göre** (geliştiriciye
  en yakın önce) ve grup içinde **en son yazılan önce** sıralar; her satırda son
  yazılma yaşı ve boyut görünür (90 saniyeden yenisi yeşil), okunamayanlar
  *izin yok* olarak işaretlenir. Bir satıra **dokununca son 200 satır** açılır.
  - Aranan dosyalar: **PHP/PHP-FPM** (`php*-fpm.log`, `php_errors.log`, yavaş
    günlük), **Laravel** (`storage/logs/*.log`), Symfony, WordPress, PM2,
    Gunicorn, **Apache** (`apache2/error.log`, `httpd/error_log`), nginx, Caddy,
    **MySQL/MariaDB**, PostgreSQL, Redis, MongoDB, Jenkins ve sistem günlükleri
    (`syslog`, `messages`, `kern.log`, `auth.log`, paket yöneticisi).
  - `log_dosyalari` ile kendi dosya/desenlerinizi ekleyebilirsiniz
    (`"~/projelerim/*/storage/logs/*.log"` gibi; `~` ve glob desteklenir).
- **Günlük görüntüleyicide hata/uyarı özeti ve `Yalnız hata` süzgeci.** Başlık
  okunan satırların hata ve uyarı sayısını yazar; süzgeç yalnızca hata/uyarı
  satırlarını bırakır (yüz binlerce satırlık Laravel günlüğünde gezinmek için).
  Servis günlüklerinde de çalışır.
- **Komut satırı:** `syspano --log-kaynaklar` (bulunan günlükler + son
  satırlarındaki hata/uyarı sayısı), `syspano --log-dosya YOL`,
  `syspano --log-hata` (yalnız hata/uyarı satırları). SSH'de de çalışır.
- `cihaz/loglar.py`: keşif, önbellek, kuyruk okuma, özet ve süzgeç mantığı.
- `ortak.kuyruk(yol, satir, azami_bayt)`: sondan geriye okuma artık **bayt
  sınırlı** (en fazla 512 KiB) — tek satırlık dev bir günlük belleği şişirmez.
- `tests/test_loglar.py` (**17 test**): glob/`~` genişletme, aynı dosyayı iki kez
  saymama, izin denetimi, CRLF ve `\n`'siz son satır, bayt sınırı, hata/uyarı
  özeti, süzgeç, keşif ve stat önbelleği.

### Değişti
- Günlük görüntüleyici artık **iki tür kaynağı** da açıyor: systemd birimi
  (journalctl ya da tanımlı dosya) ve doğrudan **günlük dosyası**. Başlıkta
  dosya yolu ve kaynak türü görünür.
- `cihaz/servisler.py` içindeki kuyruk okuma `ortak.kuyruk`'a taşındı: tek
  kaynak, tek davranış (mevcut `servisler.kuyruk` korunuyor).
- Demo verisine SERVİSLER ve GÜNLÜKLER kartları eklendi (`syspano --demo`
  artık bu iki kartı da dolu gösterir).

### Ölçüm
- Keşif (bilinen yolların `glob` + `stat`'ı): **~1,0 ms** → açılışta ve
  10 dakikada bir. Boyut/yaş tazeleme: dosya başına **~0,005 ms** → 5 saniyede
  bir. Kuyruk okuma (200 satır): **~0,14 ms** → yalnızca görüntüleyici açıkken.
  Kart hiçbir dosyanın içeriğini okumaz.

## [1.3.3] — 2026-10-08

### Düzeltildi
- **Belgeler koddan kopmuştu** (1.3.1 ve 1.3.2 değişiklikleri README/wiki'ye
  işlenmemişti): "Desteklenen cihazlar" tablosunda Ağ satırı hâlâ *sinyal
  gücü* diyordu (1.3.1'de kaldırıldı), test sayısı **98** kalmıştı (gerçek:
  **13 dosyada 105 test**), örnek `config.json` iki ayarı (`otomatik_kart`,
  `uygulama_basligi`) atlıyordu ve wiki'nin Kartlar sayfası kaldırılan Wi-Fi
  sinyalini anlatıyordu. Hepsi düzeltildi.

### Değişti
- **Ölü ayar anahtarları kaldırıldı:** `fare_ile_kaydirma` ve `saydam_olmayan`
  varsayılanlarda duruyordu ama **hiçbir modül okumuyordu**; `--yapilandir` ve
  `--varsayilan-yapilandirma` çıktısında artık görünmezler.
- **Kodda okunan ama varsayılanlarda olmayan ayarlar eklendi:**
  `guncelleme_denetimi`, `otomatik_kart`, `yedek_durum_yolu`,
  `yedek_zamanlayici`. Artık `--yapilandir` ile üretilen dosya gerçekten tüm
  ayarları içerir ve varsayılanlar tek yerde durur.
- **Ağ modülü yalnızca gösterilen alanları topluyor:** arayüzün bağlantı hızı
  (`/sys/class/net/*/speed`) saniyede bir okunuyor ama hiç gösterilmiyordu;
  tıpkı 1.3.1'deki Wi-Fi sinyali gibi kaldırıldı.

### Eklendi
- **`tests/test_belgeler.py` — belge–kod uyum testleri (6 test).** Belgeler elle
  yazıldığı için kod değişince geride kalıyordu; artık testler yakalıyor:
  README'deki `config.json` örneği varsayılanlarla aynı mı, her ayar anahtarı
  kodda okunuyor mu (ölü anahtar kalmasın), README'deki test sayısı doğru mu,
  yeni bir kart ya da komut satırı seçeneği README'ye yazılmış mı,
  `cihaz/yedek.py` sabitleri ayarlarla aynı mı. `SYSPANO_WIKI` bir wiki
  kopyasını gösteriyorsa test sayısı orada da denetlenir:
  `SYSPANO_WIKI=/tmp/wiki-clone ./run.sh test belgeler`.
- README'de **Belge–kod uyumu** testinin ve wiki'nin güncel sayıları.

## [1.3.2] — 2026-10-08

### Düzeltildi
- **Güncelleme sonrası panoda yanlış "güncelleme var" rozeti kalıyordu.**
  Güncellemeyi çalıştıran süreç eski sürümü bellekte tuttuğu için denetim
  "depodaki sürüm yeni, kurulu paket eski" sonucunu önbelleğe yazıyordu ve pano
  bu önbelleği 24 saate kadar gösteriyordu. Artık `guncelleme.guncelle()`
  denetimi **depodaki sürümle** yapıyor ve kurulum kaydına da yeni sürümü
  yazıyor. (Canlı sistemde görüldü: Raspberry Pi 1.3.1'e güncellendikten sonra
  ⚙ düğmesindeki sarı nokta duruyordu.)
- `guncelleme.denetle(yerel=...)`: çalışan sürüm dışında bir sürümle denetim
  yapılabiliyor (güncelleme sonrası doğru önbellek için gerekliydi).

## [1.3.1] — 2026-10-08

### Düzeltildi
- **Ağ modülündeki kullanılmayan Wi-Fi sinyal okuması kaldırıldı.**
  `/proc/net/wireless` Raspberry Pi'de **~1,8 ms** sürüyor (Wi-Fi sürücüsü her
  okumada firmware'e soruyor — NVMe sıcaklığındaki durumun aynısı) ve dönen
  değer arayüzde **hiç gösterilmiyordu**; yani saniyede bir boşuna yapılan bir
  işti. Pi'de ölçüldü: ağ `oku()` çağrısı ~2,5 ms'den ~0,2 ms'ye indi.
  Sinyal göstermek istenirse yavaş sensörlerdeki gibi seyreltilerek eklenmeli.

## [1.3.0] — 2026-10-08

### Eklendi
- **SERVİSLER kartı ve günlük görüntüleyici.** Sunucu makinelerde Apache,
  MySQL/MariaDB, PostgreSQL, nginx, Docker gibi systemd servislerinin durumu
  (renkli nokta · çalışma süresi · bellek; **bozuklar en üstte**) ve **bir
  satıra dokununca açılan günlük görünümü**: son 200 satır, parmakla kaydırma,
  `⟳ Yenile` düğmesi, açıkken 8 saniyede bir tazeleme, `error`/`fail` satırları
  kırmızı, `warn` satırları sarı.
  - İzlenen servisler: yaygın sunucu servislerinden **kurulu olanlar**,
    **başarısız (failed)** birimler ve `config.json`'daki `"servisler"`.
    systemd takma adları asıl ada çevrilir (`mysqld.service` → `mariadb.service`).
  - `servis_log_dosyalari` ile bir servisin kendi log dosyası (ör. Apache
    `error.log`) okunur; yoksa `journalctl` kullanılır.
  - systemd yoksa kart gizlenir, panonun geri kalanı çalışır.
  - Komut satırı: `syspano --servisler`, `syspano --log BIRIM [--log-satir N]`.
- Ölçülerek ayarlanan maliyet: keşif (tüm birimler, ~100 ms) yalnızca açılışta
  ve 10 dakikada bir; durum **tek** `systemctl show` çağrısıyla 10 saniyede bir
  (~30 ms); günlük yalnızca görüntüleyici açıkken (~20 ms).
- Belgeler: README'de **Servisler ve günlükler** ile **Teknolojiler** bölümleri;
  wiki'de yeni **Teknolojiler** sayfası ve güncellenen Kartlar/Kullanım/Ayarlar/
  Mimari/Performans/Sorun-Giderme sayfaları. Teknolojiler sayfası projenin hangi
  araçlarla ve **yapay zekâ desteğiyle** nasıl geliştirildiğini anlatır
  (ölçüm → iyileştirme → gerçek cihazda doğrulama → regresyon testi).

### Düzeltildi
- `servisler`: `systemctl show` bloklarını istenen sıraya göre eşleştirmek
  yanlıştı — systemd takma adları **asıl ada** çevirir (`mysqld.service` →
  `mariadb.service`), bu yüzden yanlış birimin durumu gösterilebiliyordu. Artık
  her blok kendi `Id` alanından okunuyor.
- `servisler`: log dosyası eşleşmesi tek yönlüydü (`apache2` **ya da**
  `apache2.service`); artık iki yön de deneniyor.
- **Günlük görünümünün başlığı** kaydırmayla birlikte yukarı kayıp görünmez
  oluyordu; artık üst şerit gibi sabit ve satırlar başlığın altındaki bantta
  kaydırılıyor.

### Notlar
- Testler: **12 dosyada 98 test** (servis ayrıştırma, takma ad çözümü, log
  kuyruğu, günlük görünümü düzeni dahil).

## [1.2.1] — 2026-10-08

### Düzeltildi
- **Depodaki ekran görüntüsünde kişisel ve makine bilgileri görünüyordu:**
  ana makine adı, yerel IP (`192.168.1.82`), disk modeli
  (`SAMSUNG MZVLB1T0HALR-00000`), dizüstü modeli ve gerçek çekirdek sürümü.
  Görüntü artık `syspano --demo` ile alınmış, yalnızca uydurma veri içeren bir
  kare; PNG meta verisi de sıyrıldı.
- `tests/test_kartlar.py`: örnek veride gerçek disk modeli ve yerel IP vardı;
  yerine "Örnek SSD 512 GB" ve belgeleme için ayrılmış adres (`192.0.2.10`,
  RFC 5737) konuldu.
- Alt bilgi, çekirdek sürümünü `os.uname()` yerine toplanan veriden okuyor —
  demo modunda gerçek sürüm görünmesin.
- **Depo geçmişi yeniden yazıldı.** 1.2.1 öncesi commit'lerde kişisel bilgi
  içeren ekran görüntüleri duruyordu; geçmişteki **her** commit'te görselin
  temiz sürümü olacak biçimde yeniden yazıldı (`main` güncellendi). Bu, tüm
  commit SHA'larını değiştirdi: eski bir klonunuz varsa
  `git fetch && git reset --hard origin/main` ya da yeniden klonlayın.

### Eklendi
- **`--demo` modu** (`src/syspano/demo.py`): hiçbir sistem dosyası okumaz,
  değerler zamanla dalgalanır. Ekran görüntüsü almak, arayüz geliştirmek ve
  donanımı olmadan denemek için. Pano, arka uç olarak onu gerçek toplayıcıyla
  aynı arayüzle kullanır (`al`, `dongu`, `aralik`).
- `tests/test_demo.py`: demo verisinin bu makineden iz taşımadığını (makine
  adı, kullanıcı adı, ev dizini, çekirdek sürümü, gerçek ağ öneki) ve
  kartların beklediği şekle uyduğunu denetler. **11 dosyada 81 test.**

## [1.2.0] — 2026-10-08

### Değişti — kaynak kullanımı yarıdan fazla azaldı
Ölçüm (14" dizüstü, 1400×880 pencere): toplam CPU **%5,0 → %2,35** (50 → 23,5
ms/sn), toplayıcı 39,5 → 21,7 ms/sn, çizim karesi 20,6 → 3,6 ms, pencere
gizliyken %1,6. Ölçüm aracı eklendi: `arac/olcum.py`.

- **Kare değiştirme (5,8×).** Tk'de `delete("all")` sonrası öğe oluşturmak, her
  öğe için "hasarlı bölge" hesabı yüzünden çok pahalıdır (ölçüm: 178 öğe için
  23,6 ms; silmeden 3,8 ms). Pano artık yeni kareyi eski kare **tuvalde
  dururken** çiziyor, sonra eskisini siliyor ve etiketleri değiştiriyor
  (`KARE`/`KARE_YENI`). Öğe birikmediği testle güvenceye alındı.
- **Uyarlanabilir sensör seyreltmesi.** `_harita_kur` her sensörün okuma
  maliyetini bir kez ölçer; < 0,3 ms olanlar her ölçümde, 0,3–2 ms olanlar
  5 sn'de, ≥ 2 ms olanlar 10 sn'de bir okunur. NVMe sıcaklığı tek başına
  9,25 ms sürüyordu (diske SMART komutu) — sıcaklık modülü 9,9 → 0,6 ms.
- **Önbellekler:** GPU kart listesi ve sysfs yolları 60 sn'de bir taranır,
  `which()` sonucu saklanır. Süreç listesi (`/proc` taraması, ~8 ms) 3 sn'de
  bir; `nvidia-smi` (~30 ms, süreç başlatır) kart boştayken 2 sn'de bir
  (çalışırken 1 sn); `vcgencmd` 3 sn'de bir.
- **Pencere gizliyken çizim yapılmaz** (tepsiden saklandığında CPU ~%1,6'ya
  düşer); büyüteç kapalıyken bekçi zamanlayıcısı 100 ms yerine 400 ms.
- Kaydırma sırasında içerik `canvas.move` ile taşınıyor (önceki sürümde).

### Düzeltildi
- `sicaklik`: sensör 0 döndürdüğünde harita her saniye yeniden kuruluyordu;
  artık yalnızca sensör dosyası gerçekten kaybolduğunda (en çok 5 sn'de bir).
- Etiket adlandırması netleşti: ekrandaki kare `kare`, çizilmekte olan
  `kare-yeni` (önceden görünen kare yanıltıcı biçimde `eski-kare` idi).

### Eklendi
- `arac/olcum.py`: modül modül toplayıcı süresi, çizim karesi ve kaydırma
  maliyeti; üretim temposunda (1 sn aralık) ölçüm.
- Testler: süreç taramasının seyreltildiği, yavaş sensörün seyreltildiği, ucuz
  sensörün seyreltilmediği, sensör haritası ve GPU kart listesinin yeniden
  kurulmadığı, `which()` önbelleği, kare öğelerinin birikmediği ve gizliyken
  çizilmediği denetleniyor. **10 dosyada 79 test.**

## [1.1.2] — 2026-10-08

### Düzeltildi
- **Dokunmatikte aşağı kaydırınca pano kilitleniyordu (Pi).** `ciz()` her
  çağrıldığında sonuna yeni bir çizim zamanlayıcısı kuruyordu; kaydırma ise
  **her parmak hareketinde** `ciz()` çağırıyordu. İki saniyelik bir kaydırmada
  saniyede onlarca **kalıcı** çizim döngüsü birikiyor, CPU doyuyor ve arayüz
  yanıt vermiyordu. Ayar ekranı uzun olduğu için en çok orada görülüyordu.
  - `ciz()` artık bekleyen zamanlayıcıyı **önce iptal ediyor**: her an en fazla
    bir çizim planlı. Kaç kez çağrılırsa çağrılsın döngü çoğalmıyor.
  - Kaydırma sırasında içerik yeniden çizilmek yerine `canvas.move` ile
    taşınıyor — parmağı takip ediyor ve ucuz. Tam çizim en fazla 150 ms'de bir
    (fare tekerleğinde 100 ms) yapılıyor; sürükleme bitince bir kez tazeleniyor.
- `cekim.Cekim.etiket()`: kaydırılabilir içerik "icerik" etiketiyle çiziliyor.
  Üst şerit, alt bilgi, bildirim ve kaydırma çubuğu etiketsiz kaldığı için
  kaydırmada yalnızca içerik hareket ediyor.
- `_icerik_ciz`: ayar ekranının durumu kare başına iki kez hesaplanıyordu
  (her biri bir dosya okuması); artık bir kez.

### Eklendi
- `test_uygulama.py`: çizim zamanlayıcılarının **çoğalmadığı** (12 ardışık
  çizimden sonra bekleyen zamanlayıcı sayısı artmıyor), parmakla kaydırmanın
  içeriği doğru taşıdığı ve **kaydırdıktan sonra** dokunmanın doğru öğeye
  isabet ettiği denetleniyor.

## [1.1.1] — 2026-10-08

### Düzeltildi
- **`git pull && ./guncelle.sh` paketi hiç kurmuyordu.** `git pull` depoyu zaten
  ilerlettiği için `guncelle.sh` "yeni commit yok" deyip **yeniden kurulum
  adımına hiç gelmeden** çıkıyordu; `syspano --surum` eski sürümü göstermeye
  devam ediyordu. Bu, güncellemenin en doğal kullanım biçimi olduğu için
  ciddi bir tuzaktı.
  - Betik artık **depo sürümü ile kurulu paket sürümünü** karşılaştırıyor:
    yeni commit olmasa bile kurulu paket depodan farklıysa yeniden kuruyor.
  - Çıktıda her zaman `git` konumu, depo sürümü ve kurulu sürüm yazıyor;
    kurulum sonrası yeni sürüm doğrulanıyor ve `syspano` PATH'te bulunamazsa
    alternatif komutlar öneriliyor.
  - Yeni `--zorla-kur`: sürümler aynı olsa da paketi yeniden kurar.
- `guncelleme.denetle()`: kurulu paket ile klondaki kod farklıysa bunu
  "yeniden kurulum gerekli" olarak bildiriyor (`kurulum_gerekli` alanı);
  `syspano --guncelle-denetle` ve panodaki sürüm satırı bunu gösteriyor.

### Eklendi
- `tests/test_guncelleme.py`: `guncelle.sh`'ın kendisi sahte bir `syspano` ile
  sınanıyor — sürümler aynıyken "yapılacak bir şey yok" demeli, kurulu paket
  eskide kalmışsa farkı bildirmeli.

## [1.1.0] — 2026-10-08

### Eklendi
- **Ayar ekranı (pano üzerinden, dokunmatik dostu).** Üst şeritteki **⚙**
  düğmesi ya da `syspano --ayarlar`. Kartların yerine aynı tuvalde çizilir;
  değişiklikler anında uygulanır ve `config.json`'a yazılır. Ayarlanabilenler:
  ölçek (kaydırıcı + −/+ + Oto), tema, büyüteç, güncelleme aralığı, hedef ekran,
  gömülü terminal, tepsi simgesi, kartları otomatik gizleme, 11 kartın tek tek
  açılıp kapanması, sürüm/güncelleme düğmeleri ve "varsayılana dön".
  - Dokunmatik için: her denetim en az 46 tasarım birimi yüksekliğinde;
    kaydırıcı çubuğunun görünen yüksekliği 8 birim ama dokunma alanı 46 birim;
    yalnızca dokunma ve sürükleme kullanılır (hover/sağ tık yok).
  - Yerleşim saf bir fonksiyon (`arayuz/ayar_ekrani.py:yerlesim`) olduğu için
    7 farklı ekran boyutunda otomatik sınanır.
- **Güncelleme stratejisi.** `guncelle.sh` (denetle / güncelle / `--zorla`),
  `syspano --guncelle`, `--guncelle-denetle`, `--kurulum-bilgisi`.
  `install.sh` artık bir **kurulum kaydı** yazar
  (`~/.local/state/syspano/kurulum.json`); güncelleyici paketi aynı yöntemle
  (pipx / pip --user / sistem) yeniden kurar. Yerel değişiklik varsa durur.
- Panoda **sarı nokta**: yeni sürüm varsa ⚙ düğmesinde görünür. Denetim günde
  bir kez arka planda, ağa çıkan iş ayrı bir süreçte yapılır.
- Ayar ekranından güncelleme başlatma ve panoyu yeniden başlatma
  (`os.execv`; aynı komut satırı seçenekleriyle).
- `cekim.Cekim.oval()`: tasarım biriminde elips. Ham `create_oval` ölçeği
  atlıyordu; anahtar ve kaydırıcı tutamağı yüksek DPI'lı panellerde yanlış yere
  düşüyordu (Pi'de %40 kayma).

### Düzeltildi
- `ayar_ekrani`: dar düzende satır yüksekliği yanlış hesaplandığı için etiketler
  denetimlerle çakışıyordu; kart anahtarlarının etiketleri hiç çizilmiyordu.
- `ayar_ekrani`: kaydırıcı çubuğunun dokunma alanı 8 birimdi (parmakla
  basılamıyordu); artık 46 birim, "Oto" düğmesi her zaman görünür.

## [1.0.1] — 2026-10-08

### Eklendi
- `tests/test_ortam.py`: `/proc/bus/input/devices` ayrıştırma (fare, dokunmatik
  panel, klavye, tek eksenli ve bozuk maskeler) ve büyüteç kararının sınanması.
- `tests/test_ayar.py`: yapılandırma okuma/güncelleme/silme davranışı.
- Uygulama testi: büyütecin gerçek hareket olmadan belirmediği ve tıklamanın
  onu kapattığı denetleniyor. Testler artık 8 dosyada 41 test.

### Düzeltildi
- **Büyüteç dokunmatik ekranlarda ekranı kapatıyordu.** Faresi olmayan bir
  cihazda (Raspberry Pi + 7" dokunmatik panel) pencere imlecin altında
  açıldığında gelen tek hareket olayı "imleç durdu" sayılıyor, daire beliriyor
  ve onu gizleyecek yeni bir hareket hiç gelmediği için kalıcı olarak ekranda
  kalıyordu.
  - Büyüteç artık **gerçek hareket** bekliyor: imleç en az 3 piksel oynamadan
    daire belirmez. Panoya dokunmak/tıklamak daireyi kapatır ve yeniden
    hareket bekler; imleç pencereden çıkınca durum sıfırlanır.
  - `"buyutec": "auto"` (yeni varsayılan): fare/dokunmatik yüzey sunan bir
    girdi aygıtı yoksa (`/proc/bus/input/devices` içindeki göreli eksenler)
    büyüteç kendiliğinden kapalıdır. Tasarım alanı 640×320'den küçük
    ekranlarda da kapalıdır (daire ekranın yarısını kaplıyordu).
  - `--buyutec` / `--buyutec-yok` ile istenirse zorlanabilir. Açılışta karar ve
    gerekçesi yazılır: `büyüteç : kapalı (fare yok (dokunmatik ekran))`.
- `ortam._eksen_ayristir`: çok kelimeli bit maskeleri (`B: ABS=2608000 1000003`)
  yanlış ayrıştırılıyordu — çekirdek kelimeleri en anlamlıdan başlayarak yazar,
  bit 0–31 son kelimededir.
- `ayar.guncelle`: pano terminal yazı boyutunu kaydederken **tüm** ayarları
  (varsayılanlar dahil) dosyaya yazıyordu; artık yalnızca değişen anahtar
  yazılır, böylece `"buyutec": "auto"` gibi akıllı varsayılanlar sabitlenmez.
  Daha önce çalıştırılmış bir cihazda `~/.config/syspano/config.json` içinde
  `"buyutec": true` kaldıysa o satırı silin (ya da dosyayı silin).

## [1.0.0] — 2026-10-08

İlk sürüm: ASUS ScreenPad'e özel panonun cihazdan bağımsız hâli.

### Eklendi
- **Uyarlanabilir yerleşim**: ekran boyutu ve en-boy oranına göre 1–4 sütun,
  orantılı satır yükseklikleri, sığmayan kartların önem sırasına göre
  gizlenmesi ve gerekirse dikey kaydırma (fare tekerleği, sürükleme, dokunmatik).
- **Çok ekran desteği**: xrandr (X11/Xwayland), kscreen-doctor (KDE mantıksal
  uzay), wlr-randr (labwc/sway), swaymsg. `--ekran auto|ana|tumu|AD|sıra`.
- **Çok ortam desteği**: KWin betiği (görev çubuğunda gösterme, çerçevesiz,
  en üstte) ve KDE dışı ortamlar için yöneticisiz pencere modu.
- **Geniş donanım desteği**: Intel (RC6), AMD (`gpu_busy_percent`), NVIDIA
  (`nvidia-smi`), Raspberry Pi VideoCore (`vcgencmd`); Intel/AMD/ARM sıcaklık
  sensörleri (`coretemp`, `k10temp`, `cpu_thermal`, `acpitz`, thermal_zone);
  her marka fan yongası; herhangi bir `power_supply` pili; kök diskin otomatik
  bulunması (NVMe/SSD/MMC); IPv4 varsayılan yolundan ağ arayüzü.
- **Kartlar**: CPU, bellek, sıcaklık/fan, pil, çekirdekler, geçmiş eğrileri,
  GPU, disk/ağ, süreçler, yedek, sistem. Her kart donanım yoksa kendini gizler.
- **Gömülü terminal** (PTY + VT100, 256 renk/truecolor) ve yazı boyutu kısayolları.
- **Tepsi simgesi** (isteğe bağlı, PySide6): göster/gizle, görünüm, yazı boyutu.
- **Büyüteç**: yüksek yoğunluklu panellerde imleç durunca beliren dairesel
  büyütme; kırpma sayesinde fare gezerken maliyeti yok.
- **CLI ve yapılandırma**: `~/.config/syspano/config.json`, `--yapilandir`,
  `--varsayilan-yapilandirma`, `--kartlar/--kart-ekle/--kart-cikar`,
  `--kartlari-listele`, `--olcek`, `--tema`, `--aralik`, `--yonetilen`,
  `--mod/--pencere/--tam-ekran`.
- **Paketleme**: `pyproject.toml` (pip/pipx), `install.sh` (apt/dnf/pacman/
  zypper tanıma, venv kurulumu, otomatik başlatma, systemd kullanıcı servisi),
  `desktop/`, `systemd/`, `run.sh`.
- **Testler**: yerleşim (14 çözünürlük), geometri kırpma, ekran ayrıştırma,
  donanım toplayıcıları, kart taşma denetimi ve uygulama duman testi —
  6 dosyada 27 test. Tk gerektirenler görüntü yoksa kendini atlar.

### Arayüz dayanıklılığı (küçük ekranlar)
- KPI kartlarının iç yerleşimi artık yüksekliğe göre oransal
  (`_kpi_duzen`): alçak kartlarda yazı ile çubuk çakışmıyor.
- `GPU`, `DİSK / AĞ` ve `YEDEK` kartları sabit dikey konumlar yerine kalan
  yere göre çiziyor; kart kısa olduğunda ayrıntı sırayla düşüyor.
- Kart başlıkları ve uzun değerler dar kartlarda `…` ile kısaltılıyor
  (`_kirp`); `GEÇMİŞ` göstergesi sığmayan öğeleri çizmiyor.
- Yerleşim: kart ağırlıklı yükseklikler sığmazsa satırlar **eşit** yüksekliğe
  geçiyor (küçük ekranda daha çok satır sığdırıyor); dar düzende (1–2 sütun)
  iki sütun kaplayan kartlar tek sütuna iniyor, sütun boşa gitmiyor.
- Ekrana sığmayan içerik için sağ kenarda **kaydırma çubuğu**; görüntü dışı
  kartlar hiç çizilmiyor.
- Panonun yeniden çizim döngüsü, pencere kapandıktan sonra çalışmıyor
  (`_kapali` denetimi) — testlerde ve hızlı aç/kapa durumunda hata vermiyor.

### Düzeltildi (orijinal ScreenPad panosundan devralınan hatalar)
- `parca_kirp`: çemberi hiç kesmeyen doğru parçası "tamamen görünür"
  sayılıyordu; büyüteç açıkken daire dışına taşan çizgiler çiziliyordu.
- `disk`: disk adı sabit `nvme0n1` yazılıydı; kök dosya sisteminden bulunuyor.
- `pil`: `BAT0`/`AC0` sabitti; `power_supply` taranarak bulunuyor.
- `ag`: `/proc/net/dev`'deki ilk arayüz seçiliyordu; varsayılan yol kullanılıyor.
- `gpu`: Intel kart yolu sabit `card1` idi; `gt_cur_freq_mhz` sunan kart aranıyor.
- `sicaklik`: hwmon adları sabitti (`iwlwifi_2`, `pch_cannonlake`); önekle
  aranıyor, ARM için `/sys/class/thermal` yedeği eklendi.
- Yerleşim: üst boşluk `kullanılabilir` yüksekliğe sayılmadığı için içerik her
  zaman bir boşluk kadar taşıyordu.
