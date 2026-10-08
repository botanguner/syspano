#!/bin/bash
# SysPano kaldırıcı: pip paketini, oturum açılışı girdisini ve servisi temizler.
# Kullanım:  ./uninstall.sh            (kullanıcı kurulumu)
#            ./uninstall.sh --sistem   (sudo ile kurulmuşsa)

set -e
SISTEM=0
[ "$1" = "--sistem" ] && SISTEM=1

bilgi() { printf '\033[1;34m==> %s\033[0m\n' "$1"; }

if [ "$SISTEM" = "1" ]; then
  sudo python3 -m pip uninstall -y syspano || true
else
  if command -v pipx >/dev/null; then pipx uninstall syspano 2>/dev/null || true; fi
  python3 -m pip uninstall -y syspano 2>/dev/null || \
    python3 -m pip uninstall -y --break-system-packages syspano 2>/dev/null || true
fi

rm -f "$HOME/.config/autostart/syspano.desktop"

if [ -f "$HOME/.config/systemd/user/syspano.service" ]; then
  systemctl --user disable --now syspano.service 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/syspano.service"
  systemctl --user daemon-reload 2>/dev/null || true
fi

bilgi "SysPano kaldırıldı. Yapılandırma için: rm -rf ~/.config/syspano"
