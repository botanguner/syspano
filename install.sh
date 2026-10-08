#!/usr/bin/env bash
# SysPano kurulum betiği
#
# Debian/Ubuntu, Raspberry Pi OS, Fedora, Arch, openSUSE üzerinde çalışır.
# Yaptığı işler:
#   1. Python 3 ve tkinter (grafik arayüz) bağımlılığını denetler, eksikse kurar
#   2. syspano paketini izole bir venv'e (ya da pipx ile) kurar
#   3. İsteğe bağlı: oturum açılışında kendiliğinden başlatma girdisi
#
# Kullanım:
#   ./install.sh                     kur
#   ./install.sh --no-autostart      otomatik başlatmayı kurma
#   ./install.sh --service           systemd kullanıcı servisi de kur
#   ./install.sh --kaldir            kaldır
set -uo pipefail

KAYNAK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERI="${XDG_DATA_HOME:-$HOME/.local/share}/syspano"
BIN="${HOME}/.local/bin"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
SERVIS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

AUTOSTART=1
SERVIS=0
KALDIR=0

kullanim() {
  cat <<'SON'
Kullanım: ./install.sh [seçenekler]

  --no-autostart   oturum açılışında başlatmayı kurma
  --autostart      oturum açılışında başlatmayı kur (varsayılan)
  --service        systemd kullanıcı servisini de kur (Wayland'de önerilmez)
  --kaldir         SysPano'yu kaldır
  -h, --help       bu yardımı göster
SON
}

while [ $# -gt 0 ]; do
  case "$1" in
    --autostart) AUTOSTART=1 ;;
    --no-autostart) AUTOSTART=0 ;;
    --service) SERVIS=1 ;;
    --kaldir|--uninstall) KALDIR=1 ;;
    -h|--help) kullanim; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1"; kullanim; exit 1 ;;
  esac
  shift
done

bilgi() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
uyari() { printf '\033[1;33mUyarı:\033[0m %s\n' "$*"; }
hata()  { printf '\033[1;31mHata:\033[0m %s\n' "$*" >&2; }

sudo_gerek() {
  if [ "$(id -u)" -eq 0 ]; then echo ""; return; fi
  if command -v sudo >/dev/null 2>&1; then echo "sudo"; return; fi
  echo ""
}

paket_kurucu() {
  for y in apt-get dnf pacman zypper; do
    command -v "$y" >/dev/null 2>&1 && { echo "$y"; return; }
  done
  echo ""
}

tkinter_kur() {
  local kur; kur="$(paket_kurucu)"
  [ -z "$kur" ] && return 1
  local S; S="$(sudo_gerek)"
  case "$kur" in
    apt-get) $S apt-get update -y && $S apt-get install -y python3-tk python3-venv ;;
    dnf)     $S dnf install -y python3-tkinter python3-virtualenv ;;
    pacman)  $S pacman -Sy --noconfirm tk python-virtualenv ;;
    zypper)  $S zypper --non-interactive install python3-tk python3-virtualenv ;;
    *) return 1 ;;
  esac
}

# ─── kaldırma ────────────────────────────────────────────────────────────────
if [ "$KALDIR" -eq 1 ]; then
  bilgi "Otomatik başlatma girdisi kaldırılıyor"
  rm -f "$AUTOSTART_DIR/syspano.desktop"
  rm -f "$SERVIS_DIR/syspano.service"
  systemctl --user disable --now syspano.service >/dev/null 2>&1 || true
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  bilgi "Çalışan pano durduruluyor"
  pkill -f "python3 -m syspano" >/dev/null 2>&1 || true
  pkill -f "syspano.tepsi" >/dev/null 2>&1 || true
  if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q syspano; then
    bilgi "pipx paketi kaldırılıyor"
    pipx uninstall syspano
  fi
  bilgi "Kurulum dizini kaldırılıyor: $VERI"
  rm -rf "$VERI"
  rm -f "$BIN/syspano"
  bilgi "Kaldırıldı."
  exit 0
fi

# ─── Python denetimi ─────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  hata "python3 bulunamadı. Önce Python 3 kurun."
  exit 1
fi
PY_SURUM="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
bilgi "Python $PY_SURUM bulundu"

# ─── tkinter denetimi (pip ile kurulamaz, dağıtım paketidir) ─────────────────
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  uyari "tkinter eksik; grafik arayüz için gerekli."
  if tkinter_kur; then
    bilgi "tkinter kuruldu"
  else
    hata "tkinter otomatik kurulamadı. Elle kurun:"
    echo "  Debian/Ubuntu/Raspberry Pi OS :  sudo apt install python3-tk"
    echo "  Fedora                        :  sudo dnf install python3-tkinter"
    echo "  Arch                          :  sudo pacman -S tk"
    exit 1
  fi
fi
bilgi "tkinter hazır"

# ─── kurulum: pipx ya da izole venv ──────────────────────────────────────────
KURULDU=0
if command -v pipx >/dev/null 2>&1; then
  bilgi "pipx ile kuruluyor"
  if pipx install --force "$KAYNAK" >/dev/null 2>&1; then KURULDU=1; fi
fi

if [ "$KURULDU" -eq 0 ]; then
  bilgi "İzole sanal ortam kuruluyor: $VERI/venv"
  if ! python3 -m venv "$VERI/venv" >/dev/null 2>&1; then
    uyari "venv oluşturulamadı (python3-venv eksik olabilir), kurulmaya çalışılıyor…"
    tkinter_kur || true
    python3 -m venv "$VERI/venv" || { hata "venv oluşturulamadı"; exit 1; }
  fi
  "$VERI/venv/bin/pip" install --quiet --upgrade pip
  if ! "$VERI/venv/bin/pip" install --quiet "$KAYNAK"; then
    hata "Paket kurulamadı."
    exit 1
  fi
  mkdir -p "$BIN"
  cat > "$BIN/syspano" <<SON
#!/usr/bin/env bash
exec "$VERI/venv/bin/syspano" "\$@"
SON
  chmod +x "$BIN/syspano"
  bilgi "Başlatıcı yazıldı: $BIN/syspano"
fi

SYSYOL="$(command -v syspano || true)"
[ -z "$SYSYOL" ] && [ -x "$BIN/syspano" ] && SYSYOL="$BIN/syspano"
[ -z "$SYSYOL" ] && SYSYOL="syspano"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) uyari "$BIN PATH'te değil. Kabuğunuza şunu ekleyin:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# ─── otomatik başlatma ───────────────────────────────────────────────────────
if [ "$AUTOSTART" -eq 1 ]; then
  mkdir -p "$AUTOSTART_DIR"
  cat > "$AUTOSTART_DIR/syspano.desktop" <<SON
[Desktop Entry]
Type=Application
Name=SysPano Sistem Panosu
Comment=CPU, bellek, sıcaklık, fan, pil, GPU, disk ve ağ izleme panosu
Exec=$SYSYOL
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
SON
  bilgi "Otomatik başlatma kuruldu: $AUTOSTART_DIR/syspano.desktop"
fi

# ─── systemd kullanıcı servisi (isteğe bağlı) ────────────────────────────────
if [ "$SERVIS" -eq 1 ]; then
  mkdir -p "$SERVIS_DIR"
  cat > "$SERVIS_DIR/syspano.service" <<SON
[Unit]
Description=SysPano sistem ve kaynak izleme panosu
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=$SYSYOL
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
SON
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  systemctl --user enable --now syspano.service >/dev/null 2>&1 || \
    uyari "Servis etkinleştirilemedi (grafik oturumu ortamı gerekebilir)."
  bilgi "systemd kullanıcı servisi kuruldu: $SERVIS_DIR/syspano.service"
fi

cat <<SON

Kurulum tamam.

  Panoyu başlat          : syspano
  Ekranları listele      : syspano --liste-ekranlar
  Belirli ekranda aç     : syspano --ekran HDMI-A-1
  Küçük pencerede aç     : syspano --mod pencere --pencere 1280x720
  Yazıları büyüt         : syspano --olcek 1.4
  Yapılandırmayı kaydet  : syspano --ekran ana --mod pencere --yapilandir
  Kartları listele       : syspano --kartlari-listele

Yapılandırma dosyası: ${XDG_CONFIG_HOME:-$HOME/.config}/syspano/config.json
SON
