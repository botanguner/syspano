#!/bin/bash
# SysPano kurucusu — Ubuntu/Debian, Fedora/RHEL, Arch ve Raspberry Pi OS uyumlu.
#
# Yaptıkları:
#   1. Python 3 ve tkinter var mı diye bakar (yoksa nasıl kurulacağını söyler,
#      --paket ile kendisi kurmayı dener).
#   2. Paketi pipx ya da `pip install --user` ile kurar.
#   3. **Panoyu nasıl başlatmak istediğini sorar** (oturum açılışı / systemd
#      kullanıcı servisi / yalnızca elle) ve seçime göre gerekli ayarı yapar.
#      Raspberry Pi'de oturum/servis seçenekleri **bekçi** ile kurulur: pano
#      çöker ya da donarsa kendiliğinden geri gelir.
#
# Kullanım:
#   ./install.sh                      sorar, sonra kurar
#   ./install.sh --baslatma oturum    sormaz: oturum açılışı (varsayılan)
#   ./install.sh --baslatma servis    sormaz: systemd kullanıcı servisi
#   ./install.sh --baslatma manuel    sormaz: otomatik başlatma kurulmaz
#   ./install.sh --sor                etkileşimli olmasa bile sor
#   ./install.sh --sadece-baslatma    paketi kurmaz; yalnız başlatma ayarını yapar
#   ./install.sh --sistem             sistem geneline kur (sudo)
#   ./install.sh --paket              eksik sistem paketlerini kurmayı dene (sudo)
#   ./install.sh --autostart-yok      (eski) = --baslatma manuel
#   ./install.sh --servis             (eski) = --baslatma servis

set -e

BURASI="$(cd "$(dirname "$0")" && pwd)"
YONTEM="kullanici"
PAKET_KUR=0
SADECE_BASLATMA=0
SOR=0
BASLATMA=""            # "" | oturum | servis | manuel
BASLATMA_VERILDI=0

while [ $# -gt 0 ]; do
  case "$1" in
    --sistem)            YONTEM="sistem" ;;
    --paket)             PAKET_KUR=1 ;;
    --baslatma)          shift; BASLATMA="${1:-}"; BASLATMA_VERILDI=1 ;;
    --sor)               SOR=1 ;;
    --sadece-baslatma)   SADECE_BASLATMA=1 ;;
    --autostart-yok)     BASLATMA="manuel"; BASLATMA_VERILDI=1 ;;
    --servis)            BASLATMA="servis"; BASLATMA_VERILDI=1 ;;
    -h|--help|--yardim)  sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1"; exit 1 ;;
  esac
  shift
done

renk() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
bilgi() { renk "1;34" "==> $1"; }
uyari() { renk "1;33" "!!  $1"; }
hata()  { renk "1;31" "!!  $1"; }

pi_mi() {
  command -v vcgencmd >/dev/null 2>&1 && return 0
  grep -qi "raspberry" /proc/device-tree/model 2>/dev/null && return 0
  return 1
}

# ── başlatma tercihini belirle (sor / bayrak / varsayılan) ──────────────────
baslatma_sec() {
  # geçerli kıl: türkçe/ingilizce eşanlamlılar
  case "$BASLATMA" in
    oturum|session|autostart) BASLATMA="oturum" ;;
    servis|service|systemd)   BASLATMA="servis" ;;
    manuel|manual|hic|hiç|yok) BASLATMA="manuel" ;;
    "") ;;
    *) uyari "Bilinmeyen --baslatma değeri: '$BASLATMA' (oturum|servis|manuel)"
       BASLATMA="" ;;
  esac
  if [ -n "$BASLATMA" ]; then
    return 0
  fi
  if [ "$SOR" = "1" ] || [ -t 0 ]; then
    echo
    bilgi "Panoyu nasıl başlatmak istersiniz?"
    echo "    1) Oturum açılışında (masaüstü)        [varsayılan]"
    echo "    2) systemd kullanıcı servisi olarak"
    echo "    3) Yalnızca elle başlatayım"
    printf "    Seçim [1]: "
    read -r cevap || cevap=""
    case "${cevap:-1}" in
      1|o|O|oturum) BASLATMA="oturum" ;;
      2|s|S|servis) BASLATMA="servis" ;;
      3|m|M|manuel) BASLATMA="manuel" ;;
      *) uyari "'$cevap' anlaşılmadı; oturum açılışı seçildi."
         BASLATMA="oturum" ;;
    esac
  else
    BASLATMA="oturum"
    echo "    (etkileşimli değil: oturum açılışı seçildi — değiştirmek için --baslatma servis|manuel)"
  fi
}

# ── 1. Python ve tkinter ────────────────────────────────────────────────────
if [ "$SADECE_BASLATMA" = "0" ]; then
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
fi   # SADECE_BASLATMA

if [ "$SADECE_BASLATMA" = "1" ]; then
  KOMUT="$(command -v syspano || true)"
  [ -z "$KOMUT" ] && KOMUT="$HOME/.local/bin/syspano"
  [ -x "$KOMUT" ] || KOMUT="python3 -m syspano"
  bilgi "Yalnızca başlatma ayarı yapılacak (paket kurulmadı): $KOMUT"
fi

# ── 4. Başlatma tercihi ─────────────────────────────────────────────────────
baslatma_sec

# Raspberry Pi: bekçi ile kur (pano donarsa/çökerse geri gelir)
BEKCI=""
if pi_mi; then
  case "$BASLATMA" in
    oturum|servis) BEKCI=" --bekci" ;;
  esac
  if [ -n "$BEKCI" ]; then
    bilgi "Raspberry Pi algılandı: bekçiyle kurulacak (donmaya karşı)"
    echo "    Tam Pi kurulumu (kalıcı günlük, kartlar) için: ./kur-pi.sh"
  fi
fi

case "$BASLATMA" in
  oturum)
    mkdir -p "$HOME/.config/autostart"
    sed "s|@KOMUT@|$KOMUT$BEKCI|" "$BURASI/desktop/syspano-autostart.desktop" \
      > "$HOME/.config/autostart/syspano.desktop"
    bilgi "Oturum açılışı girdisi: ~/.config/autostart/syspano.desktop"
    echo "    Komut: $KOMUT$BEKCI"
    ;;
  servis)
    mkdir -p "$HOME/.config/systemd/user"
    sed "s|@KOMUT@|$KOMUT$BEKCI|" "$BURASI/systemd/syspano.service" \
      > "$HOME/.config/systemd/user/syspano.service"
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user daemon-reload 2>/dev/null || \
        uyari "systemctl --user çalışmadı (oturum yöneticisi yok?)"
      systemctl --user enable --now syspano.service 2>/dev/null \
        && bilgi "systemd kullanıcı servisi çalışıyor: systemctl --user status syspano" \
        || uyari "Servis şimdi başlatılamadı; bir sonraki oturumda denenecek. 'journalctl --user -u syspano' çıktısına bakın."
    fi
    echo "    Birim: ~/.config/systemd/user/syspano.service (ExecStart=$KOMUT$BEKCI)"
    ;;
  manuel)
    bilgi "Otomatik başlatma kurulmadı (elle başlatacaksınız)"
    echo "    Başlatmak için: $KOMUT"
    echo "    Sonradan isterseniz: ./install.sh --sadece-baslatma --baslatma oturum"
    ;;
esac

if [ "$SADECE_BASLATMA" = "0" ]; then
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
fi
