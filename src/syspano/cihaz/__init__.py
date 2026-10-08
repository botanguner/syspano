"""Cihaz toplayıcıları. Sıra, arayüzde kartların sırasını da belirler."""

from . import (cpu, bellek, sicaklik, pil, gpu, disk, ag, surecler, servisler,
               guc, yedek, sistem)

# (anahtar, modül) — Toplayici bunları sırayla çağırır
TOPLAYICILAR = (
    ("sistem", sistem),
    ("cpu", cpu),
    ("bellek", bellek),
    ("sicaklik", sicaklik),
    ("pil", pil),
    ("gpu", gpu),
    ("disk", disk),
    ("ag", ag),
    ("surecler", surecler),
    ("servisler", servisler),
    ("guc", guc),
    ("yedek", yedek),
)
