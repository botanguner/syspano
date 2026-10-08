#!/usr/bin/env bash
# Depodan doğrudan çalıştırma (kurulum gerekmez):
#
#   ./run.sh                     panoyu aç (hedef ekranı otomatik seçer)
#   ./run.sh --liste-ekranlar    ekranları listele
#   ./run.sh test                tüm testleri çalıştır
#   ./run.sh --help              tüm seçenekler
set -euo pipefail
BURASI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BURASI"

case "${1:-}" in
  test|testler) exec ./tests/run.sh ;;
esac

exec env PYTHONPATH="src" python3 -m syspano "$@"
