"""Tepsi simgesi temizliği testleri: yetim kalma ve tek kopya.

PySide6 yoksa atlanır (tepsi modülü Qt'ye bağlı). Saf yardımcılar sınanır.
"""

import os

try:
    from syspano import tepsi
except Exception as hata:                       # PySide6 yok
    print(f"atlandı (PySide6 yok: {hata})")
    if __name__ == "__main__":
        import sys
        print("\n0 geçti, 0 kaldı")
        sys.exit(0)
    raise SystemExit(0)


def test_sahipsiz_mi():
    """Pano (ebeveyn) kapandıysa tepsi kendini kapatmalı (SIGKILL'de bile)."""
    assert tepsi.sahipsiz_mi(4242, 4242) is False
    assert tepsi.sahipsiz_mi(4242, 1) is True          # 1 = init (yetim)
    assert tepsi.sahipsiz_mi(4242, 9999) is True
    assert tepsi.sahipsiz_mi(0, 1) is False            # ebeveyn bilinmiyorsa karar verme


def test_tepsi_pid_zararsiz():
    """Var olan bir tepsi varsa PID döner, yoksa None; asla çökmez."""
    pid = tepsi.tepsi_pid()
    assert pid is None or isinstance(pid, int) and pid > 0
    # kendi PID'ini asla döndürmemeli
    assert pid != os.getpid()


if __name__ == "__main__":
    import sys
    import traceback
    gecen, kalan = 0, 0
    for ad, fonk in sorted(globals().items()):
        if ad.startswith("test_") and callable(fonk):
            try:
                fonk()
                print(f"  ✓ {ad}")
                gecen += 1
            except Exception:
                print(f"  ✗ {ad}")
                traceback.print_exc()
                kalan += 1
    print(f"\n{gecen} geçti, {kalan} kaldı")
    sys.exit(1 if kalan else 0)
