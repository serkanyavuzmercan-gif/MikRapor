"""
Stok hareketi teşhisi — evraktip kırılımı (fiili satış/alış neden şişiyor?).

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2026-01-01 2026-06-28

Bir hareket türünün toplamı akla yatmıyorsa (canlıda tip=0/evraktip=12 için
3,3 trilyon TL) o türü yıl yıl ve en büyük satırlarıyla açar:

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2021-01-01 2025-12-31 0 12

Stok hareketinde maliyet kolonu var mı (kapanış beklemeden brüt kâr çıkar mı)?

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py --kolonlar
"""

from __future__ import annotations

import sys
from datetime import date

from domain.gercek_durum import _siniflandir_stok
from domain.mizan_bilanco import tl
from domain.ortak import to_float as _f
from infra.config import MikroConfig, load_config, load_gercek_durum_ayarlar
from infra.mikro_fetch import (
    fetch_stok_evraktip_tepe,
    fetch_stok_evraktip_yillik,
    fetch_stok_ozet,
    fetch_tablo_kolonlari,
)
from infra.mukayese_fetch import donem_satirlari, yil_client

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


def _detay(cfg: MikroConfig, bas: str, bit: str, tip: int, evraktip: int) -> None:
    """Tek bir hareket türünü aç: yıl yıl toplam + en büyük satırlar."""
    ad = _EVRAK_AD.get((tip, evraktip), "bilinmiyor")
    print(f"\nDETAY — tip={tip} evraktip={evraktip} ({ad})\n")

    yillik = donem_satirlari(
        cfg, bas, bit,
        lambda c, b, e: fetch_stok_evraktip_yillik(c, b, e, tip, evraktip))
    print(f"  {'yıl':>4} {'adet':>8} {'toplam tutar':>22} {'en büyük satır':>22} {'miktar':>16}")
    for r in yillik:
        print(f"  {int(_f(r.get('yil', r.get('YIL')))):>4} "
              f"{int(_f(r.get('adet', r.get('ADET')))):>8} "
              f"{tl(_f(r.get('tutar', r.get('TUTAR')))):>22} "
              f"{tl(_f(r.get('azami', r.get('AZAMI')))):>22} "
              f"{_f(r.get('miktar', r.get('MIKTAR'))):>16,.2f}")

    # Her veritabanı kendi en büyüklerini verir; hepsini toplayıp yeniden sıralıyoruz
    # ki liste dönemin GERÇEK tepesi olsun, veritabanı başına ilk 15 değil.
    tepe = sorted(
        donem_satirlari(cfg, bas, bit,
                        lambda c, b, e: fetch_stok_evraktip_tepe(c, b, e, tip, evraktip)),
        key=lambda r: -_f(r.get("sth_tutar", r.get("STH_TUTAR"))))[:15]
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


# Maliyet/fiyat taşıyabilecek kolon adlarında geçen parçalar. Amaç: kapanış
# beklemeden brüt kâr hesaplanabilir mi, onu görmek.
_MALIYET_IPUCU = ("maliyet", "fiyat", "tutar", "iskonto", "vergi", "doviz", "kur", "miktar")


def _kolonlari_dok(client, tablo: str) -> None:
    """Tablonun şemasını döker; maliyet/fiyat taşıyabilecek kolonları işaretler."""
    print(f"\n{tablo} — kolonlar\n")
    try:
        kolonlar = fetch_tablo_kolonlari(client, tablo)
    except Exception as exc:  # noqa: BLE001 — teşhis aracı, sebebi yazıp geç
        print(f"   okunamadı: {exc}")
        return
    if not kolonlar:
        print("   kolon bulunamadı (tablo adı yanlış olabilir).")
        return

    ilgili = []
    for r in kolonlar:
        ad = str(r.get("kolon", r.get("KOLON", "")) or "")
        tip = str(r.get("tip", r.get("TIP", "")) or "")
        if any(ip in ad.lower() for ip in _MALIYET_IPUCU):
            ilgili.append((ad, tip))
    print(f"   toplam {len(kolonlar)} kolon; maliyet/fiyat olabilecekler:")
    for ad, tip in ilgili:
        print(f"      {ad:<34} {tip}")
    if not ilgili:
        print("      — yok —")
    print("\n   TÜM KOLONLAR:")
    adlar = [str(r.get("kolon", r.get("KOLON", "")) or "") for r in kolonlar]
    for i in range(0, len(adlar), 3):
        print("      " + "  ".join(f"{a:<32}" for a in adlar[i:i + 3]))


def main() -> None:
    # Bayrakları ayır: «--kolonlar» tarih sanılıp başlığa basılmasın.
    arg = [a for a in sys.argv[1:] if not a.startswith("--")]
    bas = arg[0] if arg else f"{date.today().year}-01-01"
    bit = arg[1] if len(arg) > 1 else date.today().isoformat()
    try:
        yil = date.fromisoformat(bit).year
        date.fromisoformat(bas)
    except ValueError as exc:
        print(f"Geçersiz tarih ({exc}) — YYYY-AA-GG bekleniyor.")
        return
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    # Veritabanını FİRMA KODU seçer. Seçili firmayla gitmek canlıda 2026'yı firma
    # 20'de (2020-2025) aratıp her rakamı sıfır gösteriyordu — program hangi yılı
    # nerede arayacağını kataloğdan bilir, teşhis aracı da aynı yolu kullanmalı.
    client = yil_client(cfg, yil)
    print(f"Stok teşhisi — {bas} → {bit} "
          f"(firma {client.cfg.firma_kodu}, yıl {client.cfg.calisma_yili})\n")
    if "--kolonlar" in sys.argv:
        _kolonlari_dok(client, "STOK_HAREKETLERI")
        return
    if len(arg) > 3:
        _detay(cfg, bas, bit, int(arg[2]), int(arg[3]))
        return
    rows = donem_satirlari(cfg, bas, bit, fetch_stok_ozet)
    if not rows:
        print("UYARI: 0 satır — dönemde hareket yok veya şema hatası.\n")
        return

    # Dönem birden çok veritabanına yayıldıysa aynı evraktip her yıldan bir satır
    # gelir; tablo tekrarlı görünmesin diye türe göre toplanır.
    kirilim: dict[tuple[int, int], list[float]] = {}
    for r in rows:
        anahtar = (int(_f(r.get("sth_tip", r.get("STH_TIP")))),
                   int(_f(r.get("sth_evraktip", r.get("STH_EVRAKTIP")))))
        top = kirilim.setdefault(anahtar, [0.0, 0.0])
        top[0] += _f(r.get("tutar", r.get("TUTAR")))
        top[1] += _f(r.get("adet", r.get("ADET")))

    print("EVRAKTİP KIRILIMI (ham):")
    print(f"  {'tip':>3} {'evrak':>5}  {'adet':>8}  {'tutar':>22}  {'satır başı':>16}  açıklama")
    supheli: list[tuple[int, int]] = []
    for (tip, ev), (tutar, adet_f) in sorted(kirilim.items(), key=lambda kv: -kv[1][0]):
        adet = int(adet_f)
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
