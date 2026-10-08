#!/bin/bash
# Kurulum yapmadan doğrudan depodan çalıştırır.
#
#   ./run.sh                      panoyu başlat
#   ./run.sh --pencere 1200x700   pencere modunda
#   ./run.sh --liste-ekranlar     ekranları listele
#   ./run.sh test [dosya]         testleri çalıştır (bkz. tests/run.sh)

BURASI="$(cd "$(dirname "$0")" && pwd)"

if [ "$1" = "test" ]; then
  shift
  exec "$BURASI/tests/run.sh" "$@"
fi

export PYTHONPATH="$BURASI/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m syspano "$@"
