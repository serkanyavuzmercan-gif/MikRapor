"""
Stok hareketi teşhisi — evraktip kırılımı (fiili satış/alış neden şişiyor?).

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2026-01-01 2026-06-28

Bir hareket türünün toplamı akla yatmıyorsa (canlıda tip=0/evraktip=12 için
3,3 trilyon TL) o türü yıl yıl ve en büyük satırlarıyla açar:

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2021-01-01 2025-12-31 0 12

Stok hareketinde maliyet kolonu var mı (kapanış beklemeden brüt kâr çıkar mı)?

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py --kolonlar

Kolon VAR; peki dolu mu ve birim mi satır toplamı mı? (asıl karar bu)

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2026-01-01 2026-07-28 --maliyet
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
    fetch_stok_maliyet_teshis,
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

SATIS_TIP = 1                      # sth_tip: 0 = giriş/alış, 1 = çıkış/satış
_SATIS_EVRAKTIP = {1, 4}           # satış irsaliyesi, satış faturası (sarf fişi değil)
_MALIYET_KOLON = ("ana", "alternatif", "orjinal")
# Maliyet güncellemesi çalıştırılmamışsa kolon 0'dır; 0'ı maliyet sanmak brüt marjı
# %100 gösterir. Satırların bu kadarı dolu değilse kolon kullanılmaz.
_ASGARI_DOLULUK = 90.0
# Ticaret firmasında brüt marj bu aralığın dışına çıkıyorsa yorum yanlıştır:
# eksi marj «maliyet satış tutarını aşıyor», %90 üstü «maliyet neredeyse sıfır» demek.
_MAKUL_MARJ = (0.0, 90.0)


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


def _maliyet_teshisi(cfg: MikroConfig, bas: str, bit: str) -> None:
    """
    Maliyet kolonu brüt kâr için kullanılabilir mi? — canlı veriye sorar.

    Kapanış fişi işlenmeden brüt kâr göstermek istiyoruz; şart, satış satırının
    kendi maliyetini taşıması. İki soru: kolon dolu mu, ve birim mi satır toplamı mı.
    """
    rows = donem_satirlari(cfg, bas, bit, fetch_stok_maliyet_teshis)
    satis = [r for r in rows if int(_f(r.get("sth_tip", r.get("STH_TIP")))) == SATIS_TIP]
    if not satis:
        print("\nMALİYET TEŞHİSİ: dönemde satış hareketi yok — daha geniş bir aralık verin.")
        return

    def al(r: dict, ad: str) -> float:
        return _f(r.get(ad, r.get(ad.upper())))

    # 1) Boşluk nerede? Maliyetsiz satır satış değil sarf/depo fişi olabilir.
    print(f"\nMALİYET TEŞHİSİ — çıkış (satış) hareketleri ({bas} → {bit})\n")
    print(f"  {'evraktip':>8}  {'satır':>8} {'tutar':>20} {'ana dolu %':>11}  açıklama")
    ev_top: dict[int, list[float]] = {}
    for r in satis:
        ev = int(al(r, "sth_evraktip"))
        t = ev_top.setdefault(ev, [0.0, 0.0, 0.0])
        t[0] += al(r, "adet")
        t[1] += al(r, "tutar")
        t[2] += al(r, "ana_dolu")
    for ev, (adet, tutar, dolu) in sorted(ev_top.items(), key=lambda kv: -kv[1][1]):
        ad = _EVRAK_AD.get((SATIS_TIP, ev), "?")
        gercek = "  ← gerçek satış" if ev in _SATIS_EVRAKTIP else ""
        print(f"  {ev:>8}  {int(adet):>8} {tl(tutar):>20} "
              f"{dolu / adet * 100 if adet else 0:>10.1f}%  {ad}{gercek}")

    # 2) Yorum YALNIZ gerçek satış evraklarından: sarf fişinin maliyeti olmaması normal,
    #    onu doluluk oranına katmak kolonu haksız yere «kullanılamaz» yapıyordu.
    sec = [r for r in satis if int(al(r, "sth_evraktip")) in _SATIS_EVRAKTIP]
    if not sec:
        print("\n  Satış irsaliyesi/faturası hareketi yok — yorum yapılamaz.")
        return
    satis_toplam = sum(al(r, "tutar") for r in sec)
    adet_toplam = sum(al(r, "adet") for r in sec)

    print(f"\n  Satış irsaliyesi + faturası: {tl(satis_toplam)} · "
          f"{int(adet_toplam):,} satır".replace(",", "."))
    print("\n  YORUM (satış tutarına göre brüt marj):")
    aday: list[tuple[float, str, str, float]] = []
    for kolon in _MALIYET_KOLON:
        duz = sum(al(r, f"{kolon}_duz") for r in sec)
        carpim = sum(al(r, f"{kolon}_carpim") for r in sec)
        dolu = sum(al(r, f"{kolon}_dolu") for r in sec)
        oran = dolu / adet_toplam * 100 if adet_toplam else 0.0
        if oran < _ASGARI_DOLULUK:
            print(f"    {kolon:<12} satış satırlarının %{oran:.1f}'i dolu → KULLANILAMAZ")
            continue
        for etiket, mal in (("satır toplamı", duz), ("birim × miktar", carpim)):
            marj = (satis_toplam - mal) / satis_toplam * 100 if satis_toplam else 0.0
            makul = "  ← MAKUL" if _MAKUL_MARJ[0] <= marj <= _MAKUL_MARJ[1] else ""
            print(f"    {kolon:<12} %{oran:>5.1f} dolu  {etiket:<15} "
                  f"SMM {tl(mal):>18}  brüt marj %{marj:>6.1f}{makul}")
            if makul:
                aday.append((abs(marj - 25.0), kolon, etiket, marj))

    print()
    if not aday:
        print("  → Hiçbir yorum makul bir marj vermiyor. Maliyet kolonu bu kurulumda")
        print("    güvenilir değil; brüt kâr canlı veriden hesaplanmamalı.")
        return
    aday.sort()
    _, kolon, etiket, marj = aday[0]
    print(f"  → KULLANILABİLİR: {kolon}, «{etiket}» olarak okunmalı (brüt marj %{marj:.1f}).")
    print("    Bunu bildirin; Nakit & Kârlılık ve mukayese tablosu kapanış fişi beklemeden")
    print("    gerçek brüt kârı ve GERÇEK STOĞU gösterecek şekilde bağlanacak.")


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
    if "--maliyet" in sys.argv:
        _maliyet_teshisi(cfg, bas, bit)
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
