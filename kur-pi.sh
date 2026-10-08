#!/bin/bash
# SysPano Raspberry Pi / kiosk kurulumu: pano + **bekçi** + kalıcı günlük.
#
# Ne yapar?
#   1. Kurulu mu denetler (`syspano --surum`).
#   2. Panoyu **bekçi üzerinden** oturum açılışına ekler; pano çöker ya da donarsa
#      kendiliğinden geri gelir:
#        · labwc / Raspberry Pi OS (Wayland) → ~/.config/labwc/autostart
#        · diğer masaüstleri                 → ~/.config/autostart/syspano.desktop
#   3. Çift başlatmayı önler (labwc varsa eski XDG girdisini kapatır).
#   4. Donma nedenlerini sonradan inceleyebilmek için **kalıcı ama sınırlı**
#      journald ayarını yapar (Raspberry Pi OS varsayılanı `Storage=volatile`:
#      günlükler yalnız bellekte, fiş çekilince siliniyordu).
#   5. Panoyu hemen başlatır (grafik oturumu varsa).
#
# Kullanım:
#   ./kur-pi.sh                       kur
#   ./kur-pi.sh --kuru                yalnızca ne yapacağını yaz (hiçbir şey değişmez)
#   ./kur-pi.sh --gunluk-yok          journald ayarına dokunma
#   ./kur-pi.sh --kartlar-ekle A,B    eksik kartları yapılandırmaya ekle (örn. pisaglik,loglar)
#   ./kur-pi.sh --geri-al             bu betiğin yaptıklarını geri al
#
# Geri alma: --geri-al her şeyi eski hâline döndürür (yedekler dosya yanında durur).

set -u

KURU=0
GUNLUK=1
GERI_AL=0
KARTLAR=""
AUTOSTART_ADI="syspano-bekci"

renk() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
bilgi() { renk "1;34" "==> $1"; }
ok()    { renk "1;32" "  ✓ $1"; }
uyari() { renk "1;33" "  ! $1"; }
hata()  { renk "1;31" "  ✗ $1"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --kuru)            KURU=1 ;;
    --gunluk-yok)      GUNLUK=0 ;;
    --geri-al)         GERI_AL=1 ;;
    --kartlar-ekle)    shift; KARTLAR="${1:-}" ;;
    -h|--help)         sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1"; exit 1 ;;
  esac
  shift
done

EB="${HOME}"
LABWC_AUTOSTART="$EB/.config/labwc/autostart"
XDG_AUTOSTART="$EB/.config/autostart/syspano.desktop"
JOURNALD_DROPIN="/etc/systemd/journald.conf.d/50-syspano-kalici.conf"
GUNLUK_SATIR="Storage=persistent"
SURUM="$(date +%Y%m%d-%H%M%S)"

pi_mi() {
  command -v vcgencmd >/dev/null 2>&1 && return 0
  grep -qi "raspberry" /proc/device-tree/model 2>/dev/null && return 0
  return 1
}

BURASI="$(cd "$(dirname "$0")" && pwd)"

komut_yolu() {
  command -v syspano 2>/dev/null && return 0
  if [ -x "$EB/.local/bin/syspano" ]; then echo "$EB/.local/bin/syspano"; return 0; fi
  if [ -x "$BURASI/run.sh" ]; then echo "$BURASI/run.sh"; return 0; fi
  echo "$EB/.local/bin/syspano"
}

sudo_var() { sudo -n true 2>/dev/null; }

# ── geri alma ───────────────────────────────────────────────────────────────
if [ "$GERI_AL" = "1" ]; then
  bilgi "Kurulum geri alınıyor"
  if [ "$KURU" = "1" ]; then
    echo "    (kuru çalıştırma: hiçbir şey değiştirilmedi)"
    exit 0
  fi
  if [ -f "$LABWC_AUTOSTART" ] && grep -q -- "--bekci" "$LABWC_AUTOSTART"; then
    cp "$LABWC_AUTOSTART" "$LABWC_AUTOSTART.bak-$SURUM"
    grep -v -- "--bekci" "$LABWC_AUTOSTART" > "$LABWC_AUTOSTART.yeni" \
      && mv "$LABWC_AUTOSTART.yeni" "$LABWC_AUTOSTART"
    ok "$LABWC_AUTOSTART içinden bekçi satırı kaldırıldı (yedek: .bak-$SURUM)"
  fi
  if [ -f "$XDG_AUTOSTART" ]; then
    sed -i "s/^Hidden=true/Hidden=false/" "$XDG_AUTOSTART" 2>/dev/null \
      && ok "XDG oturum girdisi yeniden etkinleştirildi"
  fi
  if [ -f "$JOURNALD_DROPIN" ]; then
    if sudo_var; then
      sudo rm -f "$JOURNALD_DROPIN" && sudo systemctl restart systemd-journald \
        && ok "journald ayarı kaldırıldı (yeniden volatile)"
    else
      uyari "journald ayarını kaldırmak için: sudo rm $JOURNALD_DROPIN && sudo systemctl restart systemd-journald"
    fi
  fi
  bilgi "Geri alma bitti."
  exit 0
fi

# ── 1. kurulu mu ────────────────────────────────────────────────────────────
bilgi "Kurulum denetleniyor"
PAN="$(komut_yolu)"
if [ ! -x "$PAN" ] && ! command -v syspano >/dev/null 2>&1; then
  hata "syspano kurulu görünmüyor. Önce: ./install.sh"
  exit 1
fi
ok "pano: $PAN ($("$PAN" --surum 2>/dev/null || echo 'sürüm okunamadı'))"
if pi_mi; then
  ok "Raspberry Pi algılandı ($(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo 'model okunamadı'))"
else
  uyari "Raspberry Pi algılanmadı — pano/ bekçi kurulumu yine yapılır, Pi'ye özel denetimler atlanır"
fi

# ── 2. oturum açılışı: bekçi ─────────────────────────────────────────────────
bilgi "Oturum açılışına bekçi ekleniyor"
SATIR="$PAN --bekci &"
LABWC_VAR=0
command -v labwc >/dev/null 2>&1 && LABWC_VAR=1
[ -n "${XDG_CURRENT_DESKTOP:-}" ] && case "$XDG_CURRENT_DESKTOP" in *labwc*|*LXDE*) LABWC_VAR=1 ;; esac

if [ "$LABWC_VAR" = "1" ]; then
  VAR_MI=0
  [ -f "$LABWC_AUTOSTART" ] && grep -q -- "--bekci" "$LABWC_AUTOSTART" && VAR_MI=1
  if [ "$VAR_MI" = "1" ]; then
    ok "bekçi satırı zaten var: $LABWC_AUTOSTART"
  elif [ "$KURU" = "1" ]; then
    echo "    (kuru) $LABWC_AUTOSTART içine eklenecek: $SATIR"
  else
    mkdir -p "$(dirname "$LABWC_AUTOSTART")"
    touch "$LABWC_AUTOSTART"
    cp "$LABWC_AUTOSTART" "$LABWC_AUTOSTART.bak-$SURUM"
    printf '%s\n' "$SATIR" >> "$LABWC_AUTOSTART"
    ok "eklendi: $LABWC_AUTOSTART → $SATIR"
  fi
  # çift başlatmayı önle
  if [ -f "$XDG_AUTOSTART" ] && grep -q "^Hidden=false" "$XDG_AUTOSTART"; then
    if [ "$KURU" = "1" ]; then
      echo "    (kuru) $XDG_AUTOSTART kapatılacak (çift pano olmasın)"
    else
      cp "$XDG_AUTOSTART" "$XDG_AUTOSTART.bak-$SURUM"
      sed -i "s/^Hidden=false/Hidden=true/" "$XDG_AUTOSTART"
      ok "XDG girdisi kapatıldı (çift pano olmasın): $(basename "$XDG_AUTOSTART")"
    fi
  fi
else
  if [ "$KURU" = "1" ]; then
    echo "    (kuru) $XDG_AUTOSTART içine yazılacak: Exec=$PAN --bekci"
  else
    mkdir -p "$(dirname "$XDG_AUTOSTART")"
    cat > "$XDG_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=SysPano
Name[tr]=SysPano Panosu
Comment=System and resource monitor with watchdog
Comment[tr]=SysPano panosu (bekçiyle)
Exec=$PAN --bekci
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
Hidden=false
EOF
    ok "yazıldı: $XDG_AUTOSTART (Exec=$PAN --bekci)"
  fi
fi

# ── 3. kalıcı günlük (donma teşhisi) ────────────────────────────────────────
if [ "$GUNLUK" = "1" ]; then
  bilgi "Donma teşhisi için journald kalıcılığı"
  if [ -f "$JOURNALD_DROPIN" ] && grep -q "^$GUNLUK_SATIR" "$JOURNALD_DROPIN"; then
    ok "zaten ayarlı: $JOURNALD_DROPIN"
  elif [ "$KURU" = "1" ]; then
    echo "    (kuru) $JOURNALD_DROPIN yazılacak: Storage=persistent, SystemMaxUse=200M"
  elif sudo_var; then
    sudo mkdir -p "$(dirname "$JOURNALD_DROPIN")"
    sudo tee "$JOURNALD_DROPIN" >/dev/null <<EOF
# Raspberry Pi OS varsayılanı Storage=volatile (SD kartı korumak için).
# Donma/çökme nedenlerini sonradan inceleyebilmek için kalıcı ama SINIRLI.
[Journal]
$GUNLUK_SATIR
SystemMaxUse=200M
EOF
    sudo systemctl restart systemd-journald && sleep 1
    ok "kalıcı ve sınırlı günlük açıldı (200 MB) — geri almak: ./kur-pi.sh --geri-al"
  else
    uyari "journald ayarı için sudo gerekiyor. Elle:"
    echo "      sudo mkdir -p $(dirname "$JOURNALD_DROPIN")"
    echo "      printf '[Journal]\n$GUNLUK_SATIR\nSystemMaxUse=200M\n' | sudo tee $JOURNALD_DROPIN"
    echo "      sudo systemctl restart systemd-journald"
  fi
fi

# ── 4. istenen kartlar ──────────────────────────────────────────────────────
if [ -n "$KARTLAR" ]; then
  bilgi "Kart listesi güncelleniyor: $KARTLAR"
  if [ "$KURU" = "1" ]; then
    echo "    (kuru) syspano --kart-ekle $KARTLAR"
  else
    if "$PAN" --kart-ekle "$KARTLAR" 2>&1 | grep -q "kaydedildi"; then
      "$PAN" --kart-ekle "$KARTLAR" 2>&1 | grep "kaydedildi" | sed 's/^/  ✓ /'
    else
      ok "kart listesi zaten istendiği gibi"
    fi
  fi
fi

# ── 5. şimdi başlat ─────────────────────────────────────────────────────────
bilgi "Pano/ bekçi şimdi başlatılıyor"
if [ "$KURU" = "1" ]; then
  echo "    (kuru) $PAN --bekci (arka planda)"
elif pgrep -f "[l]ocal/bin/syspano --bekci" >/dev/null 2>&1; then
  ok "bekçi zaten çalışıyor"
elif [ -z "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then
  uyari "grafik oturumu yok (WAYLAND_DISPLAY/DISPLAY tanımsız) — pano bir sonraki açılışta bekçiyle gelecek"
else
  setsid nohup "$PAN" --bekci >/dev/null 2>&1 < /dev/null &
  sleep 6
  if pgrep -f "[m] syspano" >/dev/null 2>&1; then
    ok "pano ve bekçi çalışıyor"
  else
    uyari "pano henüz görünmedi; günlük: ~/.local/state/syspano/pano.log"
  fi
fi

echo
bilgi "Bitti"
echo "  · pano günlüğü : ~/.local/state/syspano/pano.log"
echo "  · durum/kalp    : \${XDG_RUNTIME_DIR}/syspano/durum.json"
echo "  · donma denemesi: sudo kill -STOP \$(pgrep -f 'local/bin/syspano$')  # bekçi toparlar"
echo "  · geri alma     : $0 --geri-al"
