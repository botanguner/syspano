# SysPano sürüm geçmişi

Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) ·
Sürümleme: [Semantic Versioning](https://semver.org/lang/tr/).

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
