# Güvenlik Politikası

SysPano yerel bir sistem izleme panosudur: verileri `/proc` ve `/sys`'den okur,
hiçbir ağ servisi açmaz ve yükseltilmiş yetki istemez. Yine de bir güvenlik
sorunu bildirmek isterseniz aşağıdaki yolu izleyin.

## Desteklenen sürümler

| Sürüm | Destek |
|---|---|
| 1.2.x (son sürüm) | ✅ güvenlik düzeltmeleri alır |
| 1.1.x ve öncesi | ❌ desteklenmez — lütfen önce güncelleyin (`./guncelle.sh`) |

Sürümünüzü `syspano --surum` ile görebilirsiniz.

## Güvenlik açığı nasıl bildirilir

**Lütfen herkese açık bir issue açmayın.**

1. Tercih edilen yol: deponun **Security** sekmesi →
   **Report a vulnerability** (özel güvenlik açığı bildirimi). Bildirim yalnızca
   bakımcı ile sizin aranızda kalır.
2. Alternatif: GitHub profilindeki iletişim bilgisinden özel mesaj.

Bildirimde şunlar yardımcı olur:

- Sorunun ne olduğu ve nasıl kötüye kullanılabileceği
- Yeniden üretme adımları (komut, yapılandırma, ekran)
- Etkilenen sürüm (`syspano --surum`) ve ortam (`syspano --kurulum-bilgisi`)
- Varsa öneri

**Yanıt süresi:** ilk yanıt hedefi 7 gün içinde. Düzeltme yayımlandığında
sürüm notlarında (CHANGELOG) size teşekkür ederiz — istemezseniz adınızı
yazmayız.

## Kapsam ve tehdit modeli

SysPano'nun saldırı yüzeyi kasıtlı olarak küçüktür. Bir sorun bildirmeden önce
şu sınırları göz önünde bulundurun:

| Konu | Durum |
|---|---|
| Ağ | Yalnızca **güncelleme denetimi** ağa çıkar (`git fetch`/`ls-remote`). Kapatmak için `"guncelleme_denetimi": false` |
| Yetki | `sudo` gerekmez, root olarak çalıştırılmamalıdır |
| Veri kaynağı | `/proc`, `/sys` — yalnızca okuma |
| Sırlar | Hiçbir kimlik bilgisi saklanmaz; ayarlar `~/.config/syspano/config.json`'da tutulur |
| Harici bağımlılık | Yok (yalnızca Python 3 + tkinter). Tepsi simgesi isteğe bağlı `PySide6` |

### Güvenlik açısından önemli davranışlar

- **Güncelleme** (`guncelle.sh` / `syspano --guncelle` / ayar ekranındaki
  düğme): `git pull --ff-only` yapar ve paketi **kurulum kaydındaki** yöntemle
  yeniden kurar. Çalışma ağacı kirliyse durur. Panodan başlatılan güncelleme
  ayrı bir süreçte çalışır ve günlüğü
  `~/.local/state/syspano/guncelleme.log`'a yazar.
- **Gömülü terminal**: pano içinden bir kabuk (`$SHELL`) açar. Bu, panoyu
  çalıştıran kullanıcının yetkileriyle bir kabuk açmak demektir; panoyu
  kullanmadığınız bir ekranda tutuyorsanız `"terminal": false` ile kapatın.
- **Tepsi ↔ pano iletişimi**: dosya üzerinden, `$XDG_RUNTIME_DIR/syspano/`
  (oturuma özel, kullanıcıya özel) dizininde; komut dosyası işlendikten sonra
  silinir.
- **Ayar dosyası**: `~/.config/syspano/config.json`'a yalnızca sizin
  değiştirdiğiniz anahtarlar yazılır.

Kapsam dışı sayılanlar: cihaza zaten erişimi olan bir saldırganın
yapabilecekleri, yükseltilmiş yetkiyle çalıştırmanın sonuçları ve `/proc`
içeriğinin kendisinin kötü niyetli olması.

---

## Security Policy (English)

SysPano is a local system-monitoring dashboard. It reads `/proc` and `/sys`,
opens no network services and requires no privileges. The only network access is
the optional **update check**, which can be disabled with
`"guncelleme_denetimi": false`.

Please report vulnerabilities **privately** via the repository's
**Security → Report a vulnerability** form. Do not open a public issue. Include
the affected version (`syspano --surum`), your environment
(`syspano --kurulum-bilgisi`) and reproduction steps. First response within
7 days.

Supported versions: the latest 1.2.x release only.
