#!/bin/bash
# SysPano güncelleyici — GitHub'dan klonlanmış kurulumlar için.
#
#   ./guncelle.sh               denetle, gerekirse güncelle ve yeniden kur
#   ./guncelle.sh --denetle     yalnızca denetle (hiçbir şey değiştirmez)
#   ./guncelle.sh --zorla       yerel değişiklikleri sakla (git stash) ve güncelle
#   ./guncelle.sh --zorla-kur   commit yeni olmasa da paketi yeniden kur
#
# Etkileşimsizdir: SSH üzerinden de çalışır. Güncelleme sonrası panonun
# yeniden başlatılması gerekir (kod bellekte kalır).
#
# ÖNEMLİ: "yeni commit yok" demek "kurulu paket güncel" demek değildir.
# `git pull` ile depo ilerletilmişse betik bunu görür ve kurulu sürüm depodan
# farklıysa paketi yeniden kurar.

set -uo pipefail

BURASI="$(cd "$(dirname "$0")" && pwd)"
DENETLE=0
ZORLA=0
ZORLA_KUR=0
for arg in "$@"; do
  case "$arg" in
    --denetle)   DENETLE=1 ;;
    --zorla)     ZORLA=1 ;;
    --zorla-kur) ZORLA_KUR=1 ;;
    -h|--help)   sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $arg"; exit 1 ;;
  esac
done

renk() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
bilgi() { renk "1;34" "==> $1"; }
uyari() { renk "1;33" "!!  $1"; }
hata()  { renk "1;31" "!!  $1"; }

cd "$BURASI" || exit 1

# ─── sürüm okuma ────────────────────────────────────────────────────────────
repo_surumu() {
  sed -n 's/^__version__[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' \
    "$BURASI/src/syspano/__init__.py" 2>/dev/null | head -1
}

kurulu_surumu() {
  if command -v syspano >/dev/null 2>&1; then
    syspano --surum 2>/dev/null | awk '{print $NF}'
  fi
}

command -v git >/dev/null 2>&1 || { hata "git bulunamadı."; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || {
  hata "$BURASI bir git deposu değil."
  echo "    Depoyu klonladıysanız bu dizinde çalıştırın ya da elle güncelleyin:"
  echo "      python3 -m pip install --user --upgrade <depo-adresi>"
  exit 1
}

REPO_SURUM="$(repo_surumu)"
KURULU_SURUM="$(kurulu_surumu)"
[ -z "$REPO_SURUM" ] && REPO_SURUM="?"
if [ -z "$KURULU_SURUM" ]; then
  KURULU_SURUM="bilinmiyor"
  KURULU_ACIKLAMA="PATH'te 'syspano' yok — paket kurulu değil ya da başka yere kurulu"
else
  KURULU_ACIKLAMA="kurulu paket $KURULU_SURUM"
fi

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

echo "    git      : $(git rev-parse --short HEAD) → $DAL $(git rev-parse --short "$DAL")"
echo "    depo     : $REPO_SURUM   (kurulu paket: $KURULU_SURUM)"

if [ "$GERIDE" != "0" ]; then
  echo "    $GERIDE yeni commit:"
  git --no-pager log --oneline --no-decorate "HEAD..$DAL" | sed 's/^/      /'
fi

# ─── karar ──────────────────────────────────────────────────────────────────
YENIDEN_KUR=1
if [ "$GERIDE" = "0" ]; then
  if [ "$KURULU_SURUM" = "$REPO_SURUM" ] && [ "$ZORLA_KUR" = "0" ]; then
    bilgi "SysPano güncel — hem depo hem kurulu paket $REPO_SURUM, yapılacak bir şey yok."
    exit 0
  fi
  if [ "$DENETLE" = "1" ]; then
    uyari "Yeni commit yok ama $KURULU_ACIKLAMA; depo sürümü $REPO_SURUM."
    echo "      Düzeltmek için: ./guncelle.sh"
    exit 0
  fi
  uyari "Yeni commit yok, ama $KURULU_ACIKLAMA; depo sürümü $REPO_SURUM."
  bilgi "Paket yeniden kurulacak (kod güncellenmiş ama kurulmamış olabilir)."
fi

if [ "$DENETLE" = "1" ]; then
  echo
  bilgi "Güncellemek için: ./guncelle.sh"
  exit 0
fi

# ─── depo ilerlet (yalnızca geride kalmışsa) ────────────────────────────────
if [ "$GERIDE" != "0" ]; then
  if [ -n "$(git status --porcelain)" ]; then
    if [ "$ZORLA" = "1" ]; then
      uyari "Yerel değişiklikler saklanıyor (git stash)"
      git stash push -u -m "syspano-guncelleme-$(date +%Y%m%d-%H%M%S)" >/dev/null || true
    else
      hata "Çalışma ağacında kaydedilmemiş değişiklik var. Seçenekler:"
      echo "      git stash             # değişiklikleri sakla"
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
  REPO_SURUM="$(repo_surumu)"
fi

# ─── paketi yeniden kur ─────────────────────────────────────────────────────
KAYIT="${XDG_STATE_HOME:-$HOME/.local/state}/syspano/kurulum.json"
YONTEM=""
if [ -f "$KAYIT" ]; then
  YONTEM=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('yontem',''))" "$KAYIT" 2>/dev/null || true)
fi
# kayıt yoksa ya da geçersizse tahmin et
if [ -z "$YONTEM" ] || [ "$YONTEM" = "?" ]; then
  if [ -d "$HOME/.local/share/pipx/venvs/syspano" ]; then
    YONTEM="pipx"
  elif [ -x "$HOME/.local/bin/syspano" ]; then
    YONTEM="pip-kullanici"
  else
    YONTEM="pip-kullanici"
  fi
  uyari "Kurulum kaydı yok; yöntem tahmin edildi: $YONTEM"
fi

bilgi "Paket yeniden kuruluyor ($YONTEM)"
case "$YONTEM" in
  pipx)
    if command -v pipx >/dev/null 2>&1; then
      pipx install --force "$BURASI" || { hata "pipx kurulumu başarısız"; exit 1; }
    else
      uyari "pipx bulunamadı; pip --user denenecek"
      python3 -m pip install --user --upgrade "$BURASI" || exit 1
      YONTEM="pip-kullanici"
    fi
    ;;
  pip-sistem)
    uyari "Sistem geneline kurulmuş. Şunu çalıştırın:"
    echo "      sudo $BURASI/install.sh --sistem"
    YENIDEN_KUR=0
    ;;
  *)
    python3 -m pip install --user --upgrade "$BURASI" 2>/dev/null \
      || python3 -m pip install --user --break-system-packages --upgrade "$BURASI" \
      || { hata "pip kurulumu başarısız"; exit 1; }
    YONTEM="pip-kullanici"
    ;;
esac

# ─── kurulum kaydını tazele ─────────────────────────────────────────────────
if [ "$YENIDEN_KUR" = "1" ]; then
  python3 - "$KAYIT" "$YONTEM" "$BURASI" "$REPO_SURUM" <<'PY' || true
import json, os, sys, time
yol, yontem, kaynak, surum = sys.argv[1:5]
os.makedirs(os.path.dirname(yol), exist_ok=True)
veri = {}
try:
    with open(yol) as f:
        veri = json.load(f)
except Exception:
    pass
veri.update({"yontem": yontem, "kaynak": os.path.abspath(kaynak),
             "url": veri.get("url", "https://github.com/botanguner/syspano.git"),
             "surum": surum, "tarih": time.strftime("%Y-%m-%d %H:%M:%S")})
with open(yol, "w") as f:
    json.dump(veri, f, indent=2, ensure_ascii=False)
PY
fi

# ─── doğrula ────────────────────────────────────────────────────────────────
hash -r 2>/dev/null || true
YENI_KURULU="$(kurulu_surumu)"
echo
if [ -n "$YENI_KURULU" ] && [ "$YENI_KURULU" = "$REPO_SURUM" ]; then
  bilgi "Tamam — kurulu sürüm artık $YENI_KURULU."
else
  uyari "Kurulu sürüm hâlâ '${YENI_KURULU:-bulunamadı}', depo sürümü $REPO_SURUM."
  echo "      Kurulum yolu PATH'te olmayabilir. Deneyin:"
  echo "        ~/.local/bin/syspano --surum"
  echo "        python3 -m syspano --surum"
fi

echo "Yeniden başlatın (Python kodu bellekte kalır):"
if systemctl --user list-unit-files syspano.service --no-legend 2>/dev/null | grep -q "syspano.service"; then
  echo "    systemctl --user restart syspano"
else
  echo "    panoda: ⚙ → Panoyu yeniden başlat"
fi
