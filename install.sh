#!/bin/bash
# SysPano kurucusu — Ubuntu/Debian, Fedora/RHEL, Arch ve Raspberry Pi OS uyumlu.
#
# Yaptıkları:
#   1. Python 3 ve tkinter var mı diye bakar (yoksa nasıl kurulacağını söyler,
#      --paket ile kendisi kurmayı dener).
#   2. Paketi pipx ya da `pip install --user` ile kurar.
#   3. İstersen oturum açılışında kendiliğinden başlatır (.desktop ya da systemd
#      kullanıcı servisi).
#
# Kullanım:
#   ./install.sh                 pipx/--user ile kur, oturum açılışı girdisi ekle
#   ./install.sh --sistem        sistem geneline kur (sudo)
#   ./install.sh --autostart-yok oturum açılışı girdisini ekleme
#   ./install.sh --servis        systemd kullanıcı servisi kur
#   ./install.sh --paket         eksik sistem paketlerini kurmayı dene (sudo)

set -e

BURASI="$(cd "$(dirname "$0")" && pwd)"
AUTOSTART=1
YONTEM="kullanici"
SERVIS=0
PAKET_KUR=0

while [ $# -gt 0 ]; do
  case "$1" in
    --sistem)        YONTEM="sistem" ;;
    --autostart-yok) AUTOSTART=0 ;;
    --servis)        SERVIS=1 ;;
    --paket)         PAKET_KUR=1 ;;
    -h|--help)       sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1"; exit 1 ;;
  esac
  shift
done

renk() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
bilgi() { renk "1;34" "==> $1"; }
uyari() { renk "1;33" "!!  $1"; }
hata()  { renk "1;31" "!!  $1"; }

# ── 1. Python ve tkinter ────────────────────────────────────────────────────
bilgi "Python denetleniyor"
if ! command -v python3 >/dev/null; then
  hata "python3 bulunamadı. Kurun: sudo apt install python3 / sudo dnf install python3"
  exit 1
fi
echo "    $(python3 --version)"

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  uyari "tkinter yok. SysPano arayüzü Tkinter ile çizilir."
  if [ "$PAKET_KUR" = "1" ]; then
    if command -v apt-get >/dev/null; then
      sudo apt-get update -y && sudo apt-get install -y python3-tk
    elif command -v dnf >/dev/null; then
      sudo dnf install -y python3-tkinter
    elif command -v pacman >/dev/null; then
      sudo pacman -S --noconfirm tk
    elif command -v zypper >/dev/null; then
      sudo zypper install -y python3-tk
    else
      hata "Paket yöneticisi tanınmadı; python3-tk paketini elle kurun."
      exit 1
    fi
  else
    echo "    Kurmak için:"
    echo "      Debian/Ubuntu/Raspberry Pi OS : sudo apt install python3-tk"
    echo "      Fedora/RHEL                   : sudo dnf install python3-tkinter"
    echo "      Arch                          : sudo pacman -S tk"
    echo "    ya da bu betiği --paket ile çalıştırın."
    exit 1
  fi
fi

# ── 2. X11 / Xwayland ───────────────────────────────────────────────────────
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] && [ -z "${DISPLAY:-}" ]; then
  uyari "Wayland oturumu görünüyor ama DISPLAY tanımsız."
  echo "    Tkinter X11 gerektirir; Xwayland'in kurulu olduğundan emin olun"
  echo "    (çoğu dağıtımda 'xwayland' paketi) ya da bir X11 oturumunda açın."
fi

# ── 3. Kurulum ──────────────────────────────────────────────────────────────
if [ "$YONTEM" = "sistem" ]; then
  bilgi "Sistem geneline kuruluyor (sudo pip)"
  sudo python3 -m pip install --break-system-packages "$BURASI"
  KURULUM_YONTEMI="pip-sistem"
else
  if command -v pipx >/dev/null; then
    bilgi "pipx ile kuruluyor"
    pipx install --force "$BURASI"
    pipx ensurepath >/dev/null 2>&1 || true
    KURULUM_YONTEMI="pipx"
  else
    bilgi "Kullanıcı dizinine kuruluyor (pip install --user)"
    python3 -m pip install --user --upgrade "$BURASI" 2>/dev/null \
      || python3 -m pip install --user --break-system-packages --upgrade "$BURASI"
    KURULUM_YONTEMI="pip-kullanici"
  fi
fi

# ── kurulum kaydı: güncelleyici (guncelle.sh / syspano --guncelle) bunu okur ──
KAYIT_DIZINI="${XDG_STATE_HOME:-$HOME/.local/state}/syspano"
mkdir -p "$KAYIT_DIZINI"
python3 - "$KAYIT_DIZINI" "$KURULUM_YONTEMI" "$BURASI" <<'PY' || true
import json, os, sys, time
dizin, yontem, kaynak = sys.argv[1:4]
veri = {
    "yontem": yontem,
    "kaynak": os.path.abspath(kaynak),
    "url": "https://github.com/botanguner/syspano.git",
    "surum": "kuruldu",
    "tarih": time.strftime("%Y-%m-%d %H:%M:%S"),
}
with open(os.path.join(dizin, "kurulum.json"), "w") as f:
    json.dump(veri, f, indent=2, ensure_ascii=False)
print("    Kurulum kaydı: " + os.path.join(dizin, "kurulum.json"))
PY

KOMUT="$(command -v syspano || true)"
[ -z "$KOMUT" ] && KOMUT="$HOME/.local/bin/syspano"
[ -x "$KOMUT" ] || KOMUT="python3 -m syspano"

bilgi "Kuruldu: $KOMUT"
"$KOMUT" --surum >/dev/null 2>&1 && echo "    sürüm: $("$KOMUT" --surum)" || true

# ── 4. Oturum açılışı ───────────────────────────────────────────────────────
if [ "$AUTOSTART" = "1" ]; then
  mkdir -p "$HOME/.config/autostart"
  sed "s|@KOMUT@|$KOMUT|" "$BURASI/desktop/syspano-autostart.desktop" \
    > "$HOME/.config/autostart/syspano.desktop"
  bilgi "Oturum açılışı girdisi: ~/.config/autostart/syspano.desktop"
fi

if [ "$SERVIS" = "1" ]; then
  mkdir -p "$HOME/.config/systemd/user"
  sed "s|@KOMUT@|$KOMUT|" "$BURASI/systemd/syspano.service" \
    > "$HOME/.config/systemd/user/syspano.service"
  systemctl --user daemon-reload
  systemctl --user enable --now syspano.service && \
    bilgi "systemd kullanıcı servisi çalışıyor: systemctl --user status syspano" || \
    uyari "Servis başlatılamadı; 'journalctl --user -u syspano' çıktısına bakın."
fi

echo
bilgi "Hazır. Denemek için:"
echo "    syspano --liste-ekranlar       # ekranları gör"
echo "    syspano --pencere 1200x700     # pencerede dene"
echo "    syspano                        # hedef ekranı otomatik seç ve başlat"
echo
echo "Güncelleme:  ./guncelle.sh            (ya da: syspano --guncelle)"
echo "Denetleme :  ./guncelle.sh --denetle  (ya da: syspano --guncelle-denetle)"
echo
echo "Tepsi simgesini isterseniz: pip install PySide6"
