# SysPano sürüm geçmişi

Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) ·
Sürümleme: [Semantic Versioning](https://semver.org/lang/tr/).

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
