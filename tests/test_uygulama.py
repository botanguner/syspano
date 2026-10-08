"""Uygulama duman testi: pano kurulur, çizilir, büyüteç ve terminal denenir.

Tk bir görüntü gerektirir (X11/Xwayland); yoksa test atlanır. Pencere gizli
tutulur, ana döngü elle adımlanır.
"""

import os
import time


def _pano_olustur(**ek):
    import tkinter as tk
    from syspano.arayuz.pano import Pano
    ayar = {"pencere": [900, 560], "kartlar": ["cpu", "bellek", "sicaklik", "pil",
                                              "cekirdek", "disk_ag", "surecler"],
            "buyutec": True, "guncelleme_ms": 400, "tepsi": False}
    ayar.update(ek)
    try:
        tk.Tk().destroy()
    except Exception as hata:
        print(f"atlandı (görüntü yok: {hata})")
        return None
    p = Pano(ayar, cikis=None, mod="pencere")
    p.kok.withdraw()
    return p


def _bekle(pano, sn=1.4):
    son = time.monotonic() + sn
    while time.monotonic() < son:
        pano.kok.update()
        time.sleep(0.05)


def test_pano_cizilir():
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p)
        assert p.c.find_all(), "tuval boş"
        plan = p._plan(p.t.al())
        assert plan and plan["kartlar"], "yerleşim boş"
        p.ciz()
        p.kok.update()
        assert not p._max_kaydir or p._max_kaydir >= 0
    finally:
        p.kapat()


def test_buyutec():
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.2)
        p.mercek = (p.w // 2, p.h // 2)
        p._mercek_ciz(p.t.al())
        assert p.c.find_withtag("mercek"), "büyüteç çizilmedi"
        # bekçi zamanlayıcı (imleç yok) büyüteci gizlemeli
        p.mercek_yer = None
        p._mercek_denetle()
        assert not p.c.find_withtag("mercek"), "büyüteç gizlenmedi"
    finally:
        p.kapat()


def test_terminal_gecisi():
    p = _pano_olustur()
    if p is None:
        return
    try:
        _bekle(p, 1.0)
        p.gorunum_degistir("terminal")
        assert p.terminal is not None, "terminal başlamadı"
        p.terminal.baslat()
        _bekle(p, 1.0)
        p.gorunum_degistir("pano")
        assert p.gorunum == "pano"
    finally:
        p.kapat()


def test_kaydirma():
    p = _pano_olustur(kartlar=None)
    if p is None:
        return
    try:
        _bekle(p, 1.2)
        p.ciz()
        if p._max_kaydir > 0:
            p.kaydir = p._max_kaydir
            p.ciz()
            assert abs(p.cek.kaydir - p._max_kaydir) < 1
    finally:
        p.kapat()


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
