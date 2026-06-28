"""
Stok hareketi teşhisi — evraktip kırılımı (gerçek satış/alış neden şişiyor?).

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2026-01-01 2026-06-28
"""

from __future__ import annotations

import sys
from datetime import date

from config import load_config
from gercek_durum import _siniflandir_stok
from mikro_api import MikroClient
from mikro_fetch import fetch_stok_ozet
from mizan_bilanco import tl

_EVRAK_AD = {
    (0, 3): "alış faturası",
    (0, 12): "alış irsaliyesi / depo girişi",
    (1, 1): "satış irsaliyesi",
    (1, 4): "satış faturası",
    (1, 16): "sarf fişi",
}


def _f(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    bas = sys.argv[1] if len(sys.argv) > 1 else f"{date.today().year}-01-01"
    bit = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    print(f"Stok teşhisi — {bas} → {bit} (firma {cfg.firma_kodu}, yıl {cfg.calisma_yili})\n")
    rows = fetch_stok_ozet(MikroClient(cfg), bas, bit)
    if not rows:
        print("UYARI: 0 satır — dönemde hareket yok veya şema hatası.\n")
        return

    print("EVRAKTİP KIRILIMI (ham):")
    print(f"  {'tip':>3} {'evrak':>5}  {'adet':>8}  {'tutar':>18}  açıklama")
    for r in sorted(rows, key=lambda x: -_f(x.get("tutar", x.get("TUTAR")))):
        tip = int(_f(r.get("sth_tip", r.get("STH_TIP"))))
        ev = int(_f(r.get("sth_evraktip", r.get("STH_EVRAKTIP"))))
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        adet = int(_f(r.get("adet", r.get("ADET"))))
        ad = _EVRAK_AD.get((tip, ev), "?")
        print(f"  {tip:>3} {ev:>5}  {adet:>8}  {tl(tutar):>18}  {ad}")

    for baz in ("sevk", "fatura"):
        s = _siniflandir_stok(rows, baz)
        print(f"\nÖZET — satış bazı «{baz}»:")
        print(f"  Gerçek satış     {tl(s['satis']):>18}")
        print(f"  Gerçek alış      {tl(s['alis']):>18}")
        print(f"  Brüt             {tl(s['satis'] - s['alis']):>18}")
        if baz == "sevk":
            print(f"  (alış irsaliyesi {tl(s['alis_irsaliye'])} toplama DAHİL DEĞİL — çift sayım önlenir)")

    print("\nNOT: Mikro'da aynı mal hem irsaliye hem faturada stok hareketi oluşturursa")
    print("     ikisini toplamak alışı ~2 kat şişirir. Gerçek Durum alışta yalnız faturayı sayar.")


if __name__ == "__main__":
    main()
