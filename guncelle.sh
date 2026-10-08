#!/bin/bash
# SysPano güncelleyici — GitHub'dan klonlanmış kurulumlar için.
#
#   ./guncelle.sh            denetle, güncelle, yeniden kurulum ipucunu ver
#   ./guncelle.sh --denetle  yalnızca denetle (hiçbir şey değiştirmez)
#   ./guncelle.sh --zorla    yerel değişiklikleri sakla (git stash) ve güncelle
#
# Etkileşimsizdir: SSH üzerinden de çalışır. Güncelleme sonrası panonun
# yeniden başlatılması gerekir (kod bellekte kalır).

set -uo pipefail

BURASI="$(cd "$(dirname "$0")" && pwd)"
DENETLE=0
ZORLA=0
for arg in "$@"; do
  case "$arg" in
    --denetle) DENETLE=1 ;;
    --zorla)   ZORLA=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $arg"; exit 1 ;;
  esac
done

renk() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
bilgi() { renk "1;34" "==> $1"; }
uyari() { renk "1;33" "!!  $1"; }
hata()  { renk "1;31" "!!  $1"; }

cd "$BURASI" || exit 1

command -v git >/dev/null 2>&1 || { hata "git bulunamadı."; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || {
  hata "$BURASI bir git deposu değil."
  echo "    Depoyu klonladıysanız bu dizinde çalıştırın ya da elle güncelleyin:"
  echo "      python3 -m pip install --user --upgrade <depo-adresi>"
  exit 1
}

bilgi "Uzak depo denetleniyor"
if ! git fetch --quiet --tags origin 2>/dev/null; then
  hata "Uzak depoya ulaşılamadı (ağ bağlantısını denetleyin)."
  exit 1
fi

DAL=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
[ -z "$DAL" ] && DAL="origin/main"
git rev-parse --verify --quiet "$DAL" >/dev/null || DAL="origin/master"

YEREL=$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)
UZAK=$(git describe --tags --always "$DAL" 2>/dev/null || git rev-parse --short "$DAL")
GERIDE=$(git rev-list --count "HEAD..$DAL" 2>/dev/null || echo 0)

echo "    yerel : $YEREL ($(git rev-parse --short HEAD))"
echo "    uzak  : $UZAK ($(git rev-parse --short "$DAL"))  [$DAL]"

if [ "$GERIDE" = "0" ]; then
  bilgi "SysPano güncel — yapılacak bir şey yok."
  exit 0
fi

echo "    $GERIDE yeni commit:"
git --no-pager log --oneline --no-decorate "HEAD..$DAL" | sed 's/^/      /'

if [ "$DENETLE" = "1" ]; then
  echo
  bilgi "Güncellemek için: ./guncelle.sh"
  exit 0
fi

# ── çalışma ağacı kirli mi? ──
if [ -n "$(git status --porcelain)" ]; then
  if [ "$ZORLA" = "1" ]; then
    uyari "Yerel değişiklikler saklanıyor (git stash)"
    git stash push -u -m "syspano-guncelleme-$(date +%Y%m%d-%H%M%S)" >/dev/null || true
  else
    hata "Çalışma ağacında kaydedilmemiş değişiklik var. Seçenekler:"
    echo "      git stash            # değişiklikleri sakla"
    echo "      ./guncelle.sh --zorla # sakla ve güncelle"
    exit 1
  fi
fi

bilgi "Depo güncelleniyor (git merge --ff-only $DAL)"
if ! git merge --ff-only "$DAL"; then
  hata "Güncelleme başarısız (ileri sarma mümkün değil)."
  echo "      Elle çözün: git status   ya da   ./guncelle.sh --zorla"
  exit 1
fi

# ── yeniden kurulum: kurulum kaydındaki yönteme göre ──
KAYIT="${XDG_STATE_HOME:-$HOME/.local/state}/syspano/kurulum.json"
YONTEM=""
if [ -f "$KAYIT" ]; then
  YONTEM=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('yontem',''))" "$KAYIT" 2>/dev/null || true)
fi
# kayıt yoksa tahmin et
if [ -z "$YONTEM" ] || [ "$YONTEM" = "?" ]; then
  if [ -d "$HOME/.local/share/pipx/venvs/syspano" ]; then YONTEM="pipx"; else YONTEM="pip-kullanici"; fi
fi

bilgi "Paket yeniden kuruluyor ($YONTEM)"
case "$YONTEM" in
  pipx)
    if command -v pipx >/dev/null 2>&1; then
      pipx install --force "$BURASI" || { hata "pipx kurulumu başarısız"; exit 1; }
    else
      uyari "pipx bulunamadı; pip --user denenecek"
      python3 -m pip install --user --upgrade "$BURASI" || exit 1
    fi
    ;;
  pip-sistem)
    uyari "Sistem geneline kurulmuş. Şunu çalıştırın:"
    echo "      sudo $BURASI/install.sh --sistem"
    ;;
  *)
    python3 -m pip install --user --upgrade "$BURASI" 2>/dev/null \
      || python3 -m pip install --user --break-system-packages --upgrade "$BURASI" \
      || { hata "pip kurulumu başarısız"; exit 1; }
    ;;
esac

# ── kurulum kaydını tazele ──
python3 - "$KAYIT" "$YONTEM" "$BURASI" <<'PY' 2>/dev/null || true
import json, os, sys, time
yol, yontem, kaynak = sys.argv[1:4]
os.makedirs(os.path.dirname(yol), exist_ok=True)
veri = {}
try:
    with open(yol) as f:
        veri = json.load(f)
except Exception:
    pass
veri.update({"yontem": yontem, "kaynak": os.path.abspath(kaynak),
             "tarih": time.strftime("%Y-%m-%d %H:%M:%S"),
             "surum": "güncellendi"})
with open(yol, "w") as f:
    json.dump(veri, f, indent=2, ensure_ascii=False)
PY

bilgi "Güncelleme tamam ($(git describe --tags --always 2>/dev/null || echo '?'))"
echo
echo "Yeniden başlatın:"
echo "    systemctl --user restart syspano   # servis olarak çalışıyorsa"
echo "    ya da panoyu kapatıp yeniden açın"
