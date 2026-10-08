#!/usr/bin/env bash
# Testleri çalıştırır. Tk/görüntü gerektiren testler ekran yoksa kendini atlar,
# bu yüzden bu betik görüntüsüz ortamlarda (CI) da çalışır.
#
# Kullanım:
#   ./tests/run.sh              tüm testler
#   ./tests/run.sh yerlesim     yalnızca adı 'yerlesim' geçenler
set -uo pipefail
BURASI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BURASI"

SUZGE="${1:-}"
kalan=0
gecen=0
for t in tests/test_*.py; do
  ad="$(basename "$t")"
  if [ -n "$SUZGE" ] && [[ "$ad" != *"$SUZGE"* ]]; then
    continue
  fi
  printf '%-28s ' "$ad"
  if PYTHONPATH=src python3 "$t" >/tmp/syspano-test.log 2>&1; then
    tail -1 /tmp/syspano-test.log | sed 's/^/  /'
    gecen=$((gecen + 1))
  else
    echo "BAŞARISIZ"
    tail -20 /tmp/syspano-test.log | sed 's/^/    /'
    kalan=1
  fi
done

if [ "$kalan" = "0" ]; then
  echo "tümü geçti ($gecen dosya)"
fi
exit $kalan
