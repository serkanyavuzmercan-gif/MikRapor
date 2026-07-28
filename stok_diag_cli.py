"""
Stok hareketi teşhisi — evraktip kırılımı (fiili satış/alış neden şişiyor?).

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2026-01-01 2026-06-28

Bir hareket türünün toplamı akla yatmıyorsa (canlıda tip=0/evraktip=12 için
3,3 trilyon TL) o türü yıl yıl ve en büyük satırlarıyla açar:

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2021-01-01 2025-12-31 0 12
"""

from __future__ import annotations

import sys
from datetime import date

from domain.gercek_durum import _siniflandir_stok
from domain.mizan_bilanco import tl
from domain.ortak import to_float as _f
from infra.config import load_config, load_gercek_durum_ayarlar
from infra.mikro_api import MikroClient
from infra.mikro_fetch import (
    fetch_stok_evraktip_tepe,
    fetch_stok_evraktip_yillik,
    fetch_stok_ozet,
)

_EVRAK_AD = {
    (0, 3): "alış faturası",
    (0, 12): "alış irsaliyesi / depo girişi",
    (1, 1): "satış irsaliyesi",
    (1, 4): "satış faturası",
    (1, 16): "sarf fişi",
}

# Satır başına ortalama tutar bunun üzerindeyse rakam mal hareketi olamaz —
# canlıda evraktip 12 satır başına ~238 milyon TL çıkıyordu.
_MAKUL_SATIR_TUTARI = 2_000_000.0


def _s(row: dict, ad: str) -> str:
    v = row.get(ad, row.get(ad.upper()))
    return "" if v is None else str(v)[:22]


def _detay(client: MikroClient, bas: str, bit: str, tip: int, evraktip: int) -> None:
    """Tek bir hareket türünü aç: yıl yıl toplam + en büyük satırlar."""
    ad = _EVRAK_AD.get((tip, evraktip), "bilinmiyor")
    print(f"\nDETAY — tip={tip} evraktip={evraktip} ({ad})\n")

    yillik = fetch_stok_evraktip_yillik(client, bas, bit, tip, evraktip)
    print(f"  {'yıl':>4} {'adet':>8} {'toplam tutar':>22} {'en büyük satır':>22} {'miktar':>16}")
    for r in yillik:
        print(f"  {int(_f(r.get('yil', r.get('YIL')))):>4} "
              f"{int(_f(r.get('adet', r.get('ADET')))):>8} "
              f"{tl(_f(r.get('tutar', r.get('TUTAR')))):>22} "
              f"{tl(_f(r.get('azami', r.get('AZAMI')))):>22} "
              f"{_f(r.get('miktar', r.get('MIKTAR'))):>16,.2f}")

    tepe = fetch_stok_evraktip_tepe(client, bas, bit, tip, evraktip)
    toplam = sum(_f(r.get("tutar", r.get("TUTAR"))) for r in yillik)
    tepe_toplam = sum(_f(r.get("sth_tutar", r.get("STH_TUTAR"))) for r in tepe)
    print(f"\n  EN BÜYÜK {len(tepe)} SATIR "
          f"(toplamın %{(tepe_toplam / toplam * 100) if toplam else 0:.1f}'i):")
    print(f"  {'tarih':>10} {'evrak':>14} {'stok kodu':>22} "
          f"{'miktar':>14} {'tutar':>22}")
    for r in tepe:
        evrak = f"{_s(r, 'sth_evrakno_seri')}{_s(r, 'sth_evrakno_sira')}"
        print(f"  {_s(r, 'tarih')[:10]:>10} {evrak:>14} {_s(r, 'sth_stok_kod'):>22} "
              f"{_f(r.get('sth_miktar', r.get('STH_MIKTAR'))):>14,.2f} "
              f"{tl(_f(r.get('sth_tutar', r.get('STH_TUTAR')))):>22}")
    satir_sayisi = sum(_f(r.get("adet", r.get("ADET"))) for r in yillik)
    birim = toplam / satir_sayisi if satir_sayisi else 0.0
    if toplam <= 0:
        return
    if tepe_toplam > 0.5 * toplam:
        print(f"\n  → Toplamın %{tepe_toplam / toplam * 100:.1f}'ini yukarıdaki birkaç satır "
              "taşıyor: BOZUK/AYKIRI KAYIT. Mikro'da o evrakı düzeltin.")
    elif birim > _MAKUL_SATIR_TUTARI:
        print(f"\n  → Tutar satırlara yayılmış ama satır başı {tl(birim)}: "
              "sth_tutar bu evraktipte TL tutarı olmayabilir.")
    else:
        print(f"\n  → Tutar {int(satir_sayisi):,} satıra yayılmış, satır başı {tl(birim)} — "
              "rakamlar normal.".replace(",", "."))
        print("     Yani bu gerçek ve sistematik bir hareket türü; sorun 'bozuk kayıt' değil,")
        print("     bu evrak tipinin NE olduğu. Mikro'da yukarıdaki evrak no'lardan birini açın.")


def main() -> None:
    bas = sys.argv[1] if len(sys.argv) > 1 else f"{date.today().year}-01-01"
    bit = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    print(f"Stok teşhisi — {bas} → {bit} (firma {cfg.firma_kodu}, yıl {cfg.calisma_yili})\n")
    if len(sys.argv) > 4:
        _detay(MikroClient(cfg), bas, bit, int(sys.argv[3]), int(sys.argv[4]))
        return
    rows = fetch_stok_ozet(MikroClient(cfg), bas, bit)
    if not rows:
        print("UYARI: 0 satır — dönemde hareket yok veya şema hatası.\n")
        return

    print("EVRAKTİP KIRILIMI (ham):")
    print(f"  {'tip':>3} {'evrak':>5}  {'adet':>8}  {'tutar':>22}  {'satır başı':>16}  açıklama")
    supheli: list[tuple[int, int]] = []
    for r in sorted(rows, key=lambda x: -_f(x.get("tutar", x.get("TUTAR")))):
        tip = int(_f(r.get("sth_tip", r.get("STH_TIP"))))
        ev = int(_f(r.get("sth_evraktip", r.get("STH_EVRAKTIP"))))
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        adet = int(_f(r.get("adet", r.get("ADET"))))
        ad = _EVRAK_AD.get((tip, ev), "?")
        # Satır başı ortalama: bir mal hareketi satırının makul büyüklüğü.
        birim = tutar / adet if adet else 0.0
        if birim > _MAKUL_SATIR_TUTARI:
            ad += "  ← ŞÜPHELİ"
            supheli.append((tip, ev))
        print(f"  {tip:>3} {ev:>5}  {adet:>8}  {tl(tutar):>22}  {tl(birim):>16}  {ad}")
    for tip, ev in supheli:
        print(f"\nUYARI: tip={tip}/evraktip={ev} satır başına {tl(_MAKUL_SATIR_TUTARI)} üstü —")
        print(f"       bu bir mal tutarı olamaz. Aç:  stok_diag_cli.py {bas} {bit} {tip} {ev}")

    for baz in ("sevk", "fatura"):
        s = _siniflandir_stok(rows, baz, "fatura")
        print(f"\nÖZET — satış bazı «{baz}», alış fatura:")
        print(f"  Fiili satış     {tl(s['satis']):>18}")
        print(f"  Fiili alış      {tl(s['alis']):>18}")
        print(f"  Brüt             {tl(s['satis'] - s['alis']):>18}")

    a = load_gercek_durum_ayarlar()
    s = _siniflandir_stok(rows, a.satis_bazi, a.alis_bazi)
    print(f"\nÖZET — kayıtlı ayarlar ({a.ozet()}):")
    print(f"  Fiili satış     {tl(s['satis']):>18}")
    print(f"  Fiili alış      {tl(s['alis']):>18}")
    print(f"  Brüt             {tl(s['satis'] - s['alis']):>18}")
    if a.alis_bazi != "ikisi" and s["alis_irsaliye"] > 0.005:
        print(f"  (alış irsaliyesi {tl(s['alis_irsaliye'])} — toplama dahil değil)")

    print("\nNOT: Mikro'da aynı mal hem irsaliye hem faturada stok hareketi oluşturursa")
    print("     ikisini toplamak alışı ~2 kat şişirir. Nakit & Kârlılık alışta yalnız faturayı sayar.")


if __name__ == "__main__":
    main()
