#!/usr/bin/env bash
# Tüm testleri çalıştırır (Tk/görüntü gerekmez).
set -uo pipefail
BURASI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BURASI"
kalan=0
for t in tests/test_*.py; do
  printf '%-28s ' "$(basename "$t")"
  if PYTHONPATH=src python3 "$t" >/tmp/syspano-test.log 2>&1; then
    tail -1 /tmp/syspano-test.log | sed 's/^/  /'
  else
    echo "BAŞARISIZ"; cat /tmp/syspano-test.log | tail -20; kalan=1
  fi
done
exit $kalan
