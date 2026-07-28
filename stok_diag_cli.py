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

İrsaliye + fatura toplanınca satış iki kez mi sayılıyor?

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2026-01-01 2026-07-28 --fatura

Depodaki stok, mizanın 153'üne alternatif olabilir mi? (kümülatif, canlı)

    .\\.venv\\Scripts\\python.exe stok_diag_cli.py 2026-01-01 2026-07-28 --bakiye
"""

from __future__ import annotations

import sys
from datetime import date

from domain.gercek_durum import _siniflandir_stok
from domain.mizan_bilanco import tl
from domain.ortak import to_float as _f
from infra.config import MikroConfig, load_config, load_gercek_durum_ayarlar
from infra.mikro_fetch import (
    AYKIRI_SATIR_MALIYETI,
    fetch_stok_bakiye_teshis,
    fetch_stok_depo_kirilimi,
    fetch_stok_evraktip_tepe,
    fetch_stok_evraktip_yillik,
    fetch_stok_fatura_ortakligi,
    fetch_stok_faturalasma,
    fetch_stok_kapsam,
    fetch_stok_maliyet_teshis,
    fetch_stok_maliyet_yonu,
    fetch_stok_ozet,
    fetch_tablo_kolonlari,
)
from infra.mukayese_fetch import donem_parcalari, donem_satirlari, yil_client
from infra.veritabani import katalog

_EVRAK_AD = {
    (0, 3): "alış faturası",
    (0, 12): "alış irsaliyesi / depo girişi",
    (1, 1): "satış irsaliyesi",
    (1, 4): "satış faturası",
    (1, 16): "sarf fişi",
}

# Bir evrak türünün satır başı ortalaması, GENEL satır başı ortalamanın bu katından
# büyükse şüphelidir. Mutlak TL sınırı («2 milyon») kurulum bağımlıdır: küçük firmada
# hiçbir şey yakalamaz, büyük firmada gerçek faturayı bozuk ilan eder. Canlıda evraktip
# 12'nin satır başı ~238 milyon TL, geneli ~1.100 TL idi — yaklaşık 216 bin kat.
_AYKIRI_GRUP_KAT = 100.0

SATIS_TIP = 1                      # sth_tip: 0 = giriş/alış, 1 = çıkış/satış
_SATIS_EVRAKTIP = {1, 4}           # satış irsaliyesi, satış faturası (sarf fişi değil)
_MALIYET_KOLON = ("ana", "alternatif", "orjinal")
# Faturalanmış irsaliye kadar fatura satırı da varsa kopyalama modeli demektir.
# Damgalama modelinde fatura satırı bunun çok altında kalır (canlıda 262 / 17.914).
_KOPYA_ESIGI = 0.5
# Maliyet güncellemesi çalıştırılmamışsa kolon 0'dır; 0'ı maliyet sanmak brüt marjı
# %100 gösterir. Satırların bu kadarı dolu değilse kolon kullanılmaz.
_ASGARI_DOLULUK = 90.0
_SIFIR_TL = 0.005
# Boş satırların ölçülen net etkisi canlı değerin bu payını aşıyorsa rakam bağlanmaz.
_AZAMI_DUZELTME_PAYI = 5.0
# Ticaret firmasında brüt marj bu aralığın dışına çıkıyorsa yorum yanlıştır:
# eksi marj «maliyet satış tutarını aşıyor», %90 üstü «maliyet neredeyse sıfır» demek.
_MAKUL_MARJ = (0.0, 90.0)
# Ay deseni: boşluk zamanlama sorunuysa SON aylarda toplanır, sistematikse dağılır.
_SON_AY_PENCERE = 2
# İki bağımsız maliyet yöntemi bu kadar yakınsa ölçüm iç tutarlı sayılır.
_MUTABAKAT_TOLERANS = 0.10
# Faturaların bu oranından azı çakışıyorsa mükerrerlik yok sayılır. Canlıda 5.494
# faturadan 1'i çakışıyordu (%0,02) ve «ortak > 0» eşiği «Yalnız Fatura'ya geç»
# diyordu — o ayar satışı 20,5 milyondan 1,1 milyona düşürürdü.
_CAKISMA_ESIGI = 1.0
# Girişlerin bu oranından azı dışarıdan geliyorsa evraktip tamamen iç nakildir.
_DISARIDAN_ESIGI = 1.0


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
    elif satir_sayisi and birim > toplam / satir_sayisi * _AYKIRI_GRUP_KAT:
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

    # 3) Boşluk AY AY nerede? Belirleyici soru bu. Mikro'da sth_maliyet_* kolonlarını
    #    «Maliyet Güncelleme» toplu işi doldurur. Boşluk son aylarda toplanıyorsa kolon
    #    sağlamdır, yalnız iş en son o tarihte çalıştırılmıştır — kapanmış aylar
    #    kullanılabilir. Boşluk her aya dağılmışsa kolonun kendisi güvenilmezdir.
    aylik: dict[str, list[float]] = {}
    for r in sec:
        ay = str(r.get("ay", r.get("AY")) or "")[:7]
        t = aylik.setdefault(ay, [0.0, 0.0])
        t[0] += al(r, "adet")
        t[1] += al(r, "ana_dolu")
    print("\n  AY AY DOLULUK (satış irsaliyesi + faturası):")
    print(f"    {'ay':>7} {'satır':>8} {'dolu':>8} {'dolu %':>8}")
    for ay in sorted(aylik):
        adet, dolu = aylik[ay]
        oran = dolu / adet * 100 if adet else 0.0
        isaret = "  ← boş" if oran < _ASGARI_DOLULUK else ""
        print(f"    {ay:>7} {int(adet):>8} {int(dolu):>8} {oran:>7.1f}%{isaret}")

    print("\n  YORUM (satış tutarına göre brüt marj):")
    makul_olcum: list[tuple[str, str, float, float]] = []
    for kolon in _MALIYET_KOLON:
        duz = sum(al(r, f"{kolon}_duz") for r in sec)
        carpim = sum(al(r, f"{kolon}_carpim") for r in sec)
        dolu = sum(al(r, f"{kolon}_dolu") for r in sec)
        oran = dolu / adet_toplam * 100 if adet_toplam else 0.0
        # Doluluk yetersiz olsa bile rakamı GÖSTERİYORUZ: «birim mi satır toplamı mı»
        # sorusunun cevabı doluluktan bağımsızdır ve bu tabloda okunur.
        for etiket, mal in (("satır toplamı", duz), ("birim × miktar", carpim)):
            marj = (satis_toplam - mal) / satis_toplam * 100 if satis_toplam else 0.0
            makul = "  ← makul" if _MAKUL_MARJ[0] <= marj <= _MAKUL_MARJ[1] else ""
            print(f"    {kolon:<12} %{oran:>5.1f} dolu  {etiket:<15} "
                  f"SMM {tl(mal):>18}  brüt marj %{marj:>6.1f}{makul}")
            if makul:
                makul_olcum.append((kolon, etiket, mal, marj))
        print()

    _maliyet_hukmu(aylik, makul_olcum, satis_toplam, adet_toplam)


def _maliyet_hukmu(
    aylik: dict[str, list[float]],
    olcum: list[tuple[str, str, float, float]],
    satis_toplam: float,
    adet_toplam: float,
) -> None:
    """Ay deseni + kolonlar arası mutabakattan hüküm — iki ayrı soru, iki ayrı cevap."""
    oranlar = [d / a * 100 for a, d in aylik.values() if a]
    genel = sum(d for _, d in aylik.values()) / adet_toplam * 100 if adet_toplam else 0.0

    # SORU 1: boşluk NE ZAMAN? Mikro'da «Maliyet Güncelleme» toplu işi geriye dönük
    # doldurur; iş bir tarihten beri çalışmıyorsa boşluk SON aylarda toplanır. Boşluk
    # her aya eşit dağılmışsa sebep zamanlama değil, satırların kendisidir.
    if genel >= _ASGARI_DOLULUK:
        print(f"  → Doluluk %{genel:.1f} — kolon yeterince dolu.")
    elif oranlar and min(oranlar[-_SON_AY_PENCERE:]) < min(oranlar[:-_SON_AY_PENCERE] or [100.0]):
        print("  → Boşluk SON aylarda toplanıyor: Mikro'da «Maliyet Güncelleme» bir")
        print("    süredir çalıştırılmamış. Çalıştırılınca kolon kullanılabilir hâle gelir.")
    else:
        yayilim = max(oranlar) - min(oranlar) if oranlar else 0.0
        print(f"  → Boşluk HER AYA dağılmış (doluluk %{genel:.1f}, aylar arası fark "
              f"yalnız {yayilim:.1f} puan).")
        print("    Yani sebep «maliyet güncellemesi geç kaldı» değil; satırların yaklaşık")
        print(f"    %{100 - genel:.0f}'i sistematik olarak maliyetsiz. Muhtemel sebepler:")
        print("    stok takibi olmayan hizmet/işçilik kalemleri, promosyon-numune çıkışları,")
        print("    ya da eksi stoktan satış (Mikro maliyeti hesaplayamaz).")

    # SORU 2: kolonlar birbirini tutuyor mu? Bağımsız iki maliyet yöntemi aynı rakama
    # yakınsıyorsa ölçüm iç tutarlıdır — tek kolona bakıp karar vermekten çok daha güçlü.
    # HEPSİNİN uyuşmasını aramıyoruz: canlıda «orjinal» 5,2 milyonda tek başına kalıp
    # (ana 11,7M · alternatif 12,1M) gerçek mutabakatı gizliyordu. En kalabalık uyuşan
    # kümeyi alıyoruz; aykırı kolon hem hükmü hem alt sınırı bozmasın.
    kume = _uyusan_kume(olcum)
    if len(kume) >= 2:
        ad = " · ".join(f"{k} ({e})" for k, e, _, _ in kume)
        print(f"\n  → MUTABAKAT: {ad}")
        print(f"    aynı rakama yakınsıyor ({tl(min(o[2] for o in kume))} – "
              f"{tl(max(o[2] for o in kume))}). Bağımsız iki maliyet yöntemi aynı şeyi")
        print("    söylüyor; ölçüm iç tutarlı. Dışarıda kalan kolon aykırı değerdir.")
    if kume:
        alt_sinir = min(o[2] for o in kume)
        marj = (satis_toplam - alt_sinir) / satis_toplam * 100 if satis_toplam else 0.0
        print(f"\n  SMM EN AZ {tl(alt_sinir)} — boş satırlar bu rakamı yalnız ARTIRIR.")
        print("  Dolayısıyla mizan stoğu en az bu kadar şişik ve gerçek brüt marj")
        print(f"  %{marj:.1f}'in ALTINDA. Bunlar tahmin değil, tek yönlü sınır.")


def _uyusan_kume(
    olcum: list[tuple[str, str, float, float]],
) -> list[tuple[str, str, float, float]]:
    """Birbirine `_MUTABAKAT_TOLERANS` kadar yakın en kalabalık ölçüm kümesi."""
    en_iyi: list[tuple[str, str, float, float]] = []
    for merkez in olcum:
        yakin = [o for o in olcum
                 if max(o[2], merkez[2]) > 0
                 and abs(o[2] - merkez[2]) / max(o[2], merkez[2]) <= _MUTABAKAT_TOLERANS]
        if len(yakin) > len(en_iyi):
            en_iyi = yakin
    return en_iyi


def _fatura_ortakligi(cfg: MikroConfig, bas: str, bit: str, fatura_tutar: float) -> None:
    """
    Kalan tek soru: evraktip 4 satırları irsaliyelerle AYNI faturaya mı ait?

    Damgalama modeli anlaşılsa bile bu açık kalıyordu. Aynı faturaysa o tutar iki kez
    sayılır; ayrı faturaysa irsaliyesiz doğrudan satıştır ve toplama girmelidir.
    """
    satirlar = donem_satirlari(cfg, bas, bit, fetch_stok_fatura_ortakligi)
    if not satirlar:
        return
    irs = sum(_f(r.get("irsaliye_fatura", r.get("IRSALIYE_FATURA"))) for r in satirlar)
    fat = sum(_f(r.get("fatura_fatura", r.get("FATURA_FATURA"))) for r in satirlar)
    bir = sum(_f(r.get("birlesik_fatura", r.get("BIRLESIK_FATURA"))) for r in satirlar)
    ortak = irs + fat - bir
    print(f"\n  Tekil fatura: irsaliyelerden {int(irs):,} · fatura satırlarından "
          f"{int(fat):,} · birleşik {int(bir):,}".replace(",", "."))
    # ORAN'a bakıyoruz, sıfıra değil. Canlıda 5.494 faturadan 1'i çakışıyordu ve eski
    # eşik (ortak > 0) «Yalnız Fatura'ya geç» diyordu — o ayar satışı 20,5 milyondan
    # 1,1 milyona düşürürdü. Tek bir karma evrak, ayar değiştirmek için sebep değildir.
    oran = ortak / bir * 100 if bir else 0.0
    if oran <= _CAKISMA_ESIGI:
        print("  → Kümeler pratikte AYRIK: fatura satırları irsaliyelerin kopyası değil,")
        print("    irsaliyesiz doğrudan satışlar. İrsaliye + fatura toplamı MÜKERRER")
        print("    DEĞİL; «Satış: İrsaliye+Fatura» ayarı doğru.")
        if ortak > 0:
            print(f"    ({int(ortak)} fatura hem irsaliye hem fatura satırı taşıyor — "
                  f"%{oran:.2f}, ihmal edilebilir.)")
    else:
        print(f"  → Faturaların %{oran:.1f}'i HEM irsaliye HEM fatura satırı taşıyor: o kadarı")
        print(f"    iki kez sayılıyor (fatura satırlarının üst sınırı {tl(fatura_tutar)}).")
        print("    «Satış: Yalnız Fatura» ayarına geçmeyi değerlendirin.")


def _alis_teshisi(cfg: MikroConfig, bas: str, bit: str, kova: dict) -> None:
    """
    ALIŞ tarafı: irsaliye ile fatura arasındaki fark gerçek mal mı, kopya mı, transfer mi?

    Satışta faturalaşmanın kopya yaratmadığını damgadan kanıtladık (17.430 irsaliyeye
    karşı 262 fatura satırı). Alışta oran bambaşka: 6.592 irsaliyeye karşı 2.492 fatura.
    Bu, mekanizmanın alışta farklı işlediğini düşündürüyor ve MARJI DOĞRUDAN ETKİLER:

      • Fark gerçek maldan geliyorsa → alışımız eksik sayılıyor, marj OLDUĞUNDAN YÜKSEK
      • Fark faturalaşan irsaliyenin kopyasıysa → şu anki sayım doğru
      • Fark depolar arası transferse → alış değil, hiç sayılmamalı

    evraktip 12'nin Mikro'daki adı «alış irsaliyesi / DEPO GİRİŞİ» — üçüncü ihtimal
    gerçek ve tek başına farkı açıklayabilir.
    """
    irs_fat = kova.get((12, 1), [0.0, 0.0])
    irs_bek = kova.get((12, 0), [0.0, 0.0])
    fatura = [sum(v[0] for (ev, _), v in kova.items() if ev == 3),
              sum(v[1] for (ev, _), v in kova.items() if ev == 3)]
    irs_top = irs_fat[1] + irs_bek[1]
    if irs_top <= 0.005 and fatura[1] <= 0.005:
        return

    print(f"\n  Alış irsaliyesi   {tl(irs_top):>20}  "
          f"({tl(irs_fat[1])} faturalanmış + {tl(irs_bek[1])} bekleyen)")
    print(f"  Alış faturası     {tl(fatura[1]):>20}")
    print(f"  FARK              {tl(irs_top - fatura[1]):>20}")

    depo = donem_satirlari(
        cfg, bas, bit, lambda c, b, e: fetch_stok_depo_kirilimi(c, b, e, 0, 12))
    dis = ic = 0.0
    for r in depo:
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        if int(_f(r.get("transfer", r.get("TRANSFER")))):
            ic += tutar
        else:
            dis += tutar
    print(f"\n  Bunun {tl(dis)} kadarı DIŞARIDAN gelen mal (çıkış deposu yok),")
    print(f"        {tl(ic)} kadarı DEPOLAR ARASI transfer (iki depo da dolu).")

    print()
    toplam_depo = dis + ic
    # ÖNCE «hepsi transfer mi» sorusu. Eski sıralama dışarıdan gelen malın alış
    # faturasına YAKIN olmasını arıyordu; canlıda dışarıdan gelen 0,00 çıkınca o koşul
    # tutmadı ve teşhis, kendi bastığı «%100 transfer» satırını görmezden gelip
    # «açıklanamıyor» dedi. Veri cevabı vermişti, hüküm okuyamadı.
    if toplam_depo > 0.005 and dis / toplam_depo * 100 <= _DISARIDAN_ESIGI:
        print("  → Bu evraktipin TAMAMI depolar arası transfer: hiçbirinin çıkış deposu")
        print("    boş değil, yani dışarıdan gelen mal bu koda hiç girmiyor. Demek ki")
        print("    satın alınan mal doğrudan FATURAYLA depoya giriyor.")
        print("    Şu anki sayım (yalnız fatura) DOĞRU; marj etkilenmiyor ve")
        print("    «alış irsaliyesi» satırı aslında alış değil, iç nakildir.")
    elif ic > 0.005 and abs(dis - fatura[1]) <= 0.05 * max(fatura[1], 1.0):
        print("  → Fark DEPO TRANSFERİNDEN geliyor: dışarıdan gelen mal ile alış faturası")
        print("    örtüşüyor. Şu anki sayım (yalnız fatura) doğru, marj etkilenmiyor.")
    elif irs_fat[0] > 0 and fatura[0] < irs_fat[0] * _KOPYA_ESIGI:
        print("  → DAMGALAMA MODELİ: faturalaşan irsaliye yerinde duruyor, ayrıca fatura")
        print("    satırı yaratılmıyor. O hâlde depoya giren mal irsaliye tutarıdır ve")
        print("    ALIŞIMIZ EKSİK SAYILIYOR — fiili marj olduğundan yüksek görünüyor.")
        print("    «Alış: İrsaliye» ayarına geçmeyi değerlendirin.")
    else:
        print("  → Fark ne transferle ne damgayla açıklanıyor. Faturalanmamış irsaliye")
        print(f"    ({tl(irs_bek[1])}) henüz faturası gelmemiş mal olabilir: fiilen")
        print("    depodadır ama maliyeti kayda girmemiştir. Mikro'da birkaç bekleyen")
        print("    irsaliyeyi açıp gerçek mal mı diye bakın.")


# sth_tip: 0 giriş, 1 çıkış. Başka bir değer çıkarsa YÖNÜ BİLİNMİYOR demektir —
# canlıda üçüncü bir tip vardı ve «çıkış» diye etiketlenip tabloda iki kez göründü.
_YON_AD = {0: "giriş", 1: "çıkış"}


def _kapsam_satiri(client, bit: str, bas: str) -> tuple[str, int]:
    """Bu PENCEREDE ilk hareket ne zaman, kaç satır var."""
    rows = fetch_stok_kapsam(client, bit, bas)
    if not rows:
        return "", 0
    r = rows[0]
    ilk = str(r.get("ilk", r.get("ILK")) or "")[:10]
    adet = int(_f(r.get("adet", r.get("ADET"))))
    print(f"  firma {client.cfg.firma_kodu:>4}  {bas} → {bit}  "
          f"ilk hareket {ilk or '—':>10}  {adet:>9,} satır".replace(",", "."))   # tl() yok
    return ilk, adet


def _yon_topla(client, bit: str, bas: str, birikim: dict[int, list[float]]) -> None:
    """Maliyeti boş satırları YÖNE göre biriktirir (sth_tip: 0 giriş, 1 çıkış)."""
    for r in fetch_stok_maliyet_yonu(client, bit, bas):
        def al(ad: str, satir=r) -> float:
            return _f(satir.get(ad, satir.get(ad.upper())))

        t = birikim.setdefault(int(al("tip")), [0.0, 0.0, 0.0, 0.0])
        t[0] += al("bos_satir")
        t[1] += al("bos_miktar")
        t[2] += al("dolu_miktar")
        t[3] += al("dolu_maliyet")


def _yon_dok(birikim: dict[int, list[float]]) -> float | None:
    """
    Boş satırların net maliyete ölçülen etkisi; yön bilinmiyorsa None.

    Net maliyet = giren − çıkan olduğu için eksik bir GİRİŞ satırı stoğu düşük, eksik
    bir ÇIKIŞ satırı YÜKSEK gösterir. Yön bilinmeden doluluk oranı bir şey söylemez:
    canlıda boş satırların %84'ü çıkıştaydı, yani canlı rakam mizanla AYNI yönde şişikti.
    """
    if not birikim:
        print("  Yön sorgusu boş döndü.")
        return None
    print(f"  {'yön':>10}  {'boş satır':>10}  {'boş miktar':>14}  {'birim maliyet':>16}"
          f"  {'eksik TL (tahmin)':>20}")
    duzeltme = 0.0
    belirsiz = 0.0          # yönü bilinmeyen satırların TL karşılığı — işareti bilinmez
    olculebilir = True
    for tip in sorted(birikim):
        bos_satir, bos_miktar, dolu_miktar, dolu_maliyet = birikim[tip]
        ad = _YON_AD.get(tip, f"tip {tip} (?)")
        birim = dolu_maliyet / dolu_miktar if dolu_miktar else 0.0
        eksik = bos_miktar * birim
        if bos_satir and not birim:
            olculebilir = False
        if tip in _YON_AD:
            duzeltme += eksik if tip == 0 else -eksik
        else:
            belirsiz += abs(eksik)
        # Sayılar önce biçimlenir; tl() çıktısını toplu replace bozardı.
        satir_no = f"{int(bos_satir):,}".replace(",", ".")
        miktar_s = f"{bos_miktar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f"  {ad:>10}  {satir_no:>10}  {miktar_s:>14}"
              f"  {tl(birim):>16}  {tl(eksik):>20}")
    if not olculebilir:
        print("\n  Birim maliyeti çıkmayan satır var — net düzeltme hesaplanamıyor.")
        return None
    print(f"\n  Ölçülen net düzeltme  {tl(duzeltme):>18}"
          "   (eksik giriş − eksik çıkış)")
    if belirsiz > _SIFIR_TL:
        # GİZLEMİYORUZ: yönü bilinmeyen kısım hesaplanamaz ama ÖLÇÜLMÜŞ bir sınırı var.
        print(f"  Yönü bilinmeyen pay   ± {tl(belirsiz):>16}   (işareti bilinmediği için"
              " düzeltmeye girmedi)")
    return duzeltme


def _bakiye_teshisi(client, cfg: MikroConfig, bit: str) -> None:
    """
    Canlı stok değeri mizanın 153'üne alternatif olabilir mi?

    Stok SEVİYESİ kümülatiftir — şirketin ilk gününden bugüne bütün hareketlerin
    toplamı. Mikro yılları ayrı veritabanlarına böldüğü için KATALOĞUN TAMAMI okunur ve
    pencereler donem_parcalari ile çakışmadan bölünür (bir yıl iki veritabanında birden
    olabilir; sınırsız okumak o yılı iki kez sayardı).

    AYKIRI SATIRLAR AYRI GÖSTERİLİR: canlıda tek bir kayıt (07.12.2023, 2 adet mala
    3,3 trilyon TL) 390 bin satırın toplamını tek başına ele geçiriyordu. Elenen de
    yazılır — sessizce atılan bir rakam, yanlış rakamdan iyi değildir.

    Şu şartların hepsi doğru olmadan cevap EVET değildir: bütün pencereler okundu,
    aykırı satır kalmadı, maliyet kolonu yeterince dolu, boş satırların yönü biliniyor
    ve net etkisi önemsiz.
    """
    yil = int(bit[:4])
    kapsamlar = [k for k in katalog(cfg) if k.ilk_yil <= yil]
    ilk_yil = min((k.ilk_yil for k in kapsamlar), default=yil)
    tarih_bas = f"{ilk_yil}-01-01"

    print(f"\nSTOK BAKİYE TEŞHİSİ — {bit} itibarıyla (kümülatif: {tarih_bas} →)\n")
    print("VERİTABANLARI — stok seviyesi hepsinin toplamıdır\n")
    alanlar = ("miktar", "maliyet", "tutar", "adet", "maliyet_dolu",
               "aykiri_satir", "aykiri_maliyet", "temiz_maliyet", "temiz_miktar")
    toplam = dict.fromkeys(alanlar, 0.0)
    yon: dict[int, list[float]] = {}
    en_erken = ""
    okunan = 0
    for c, p_bas, p_bit in donem_parcalari(cfg, tarih_bas, bit):
        ilk, adet = _kapsam_satiri(c, p_bit, p_bas)
        if ilk and (not en_erken or ilk < en_erken):
            en_erken = ilk
        if not adet:
            continue
        okunan += 1
        for r in fetch_stok_bakiye_teshis(c, p_bit, p_bas):
            for ad in alanlar:
                toplam[ad] += _f(r.get(ad, r.get(ad.upper())))
        _yon_topla(c, p_bit, p_bas, yon)

    if not okunan:
        print("\n  Hiçbir veritabanından stok hareketi okunamadı.")
        return

    adet, dolu = toplam["adet"], toplam["maliyet_dolu"]
    ham, temiz = toplam["maliyet"], toplam["temiz_maliyet"]
    aykiri_satir = int(toplam["aykiri_satir"])
    print(f"\n  Hareket satırı        {int(adet):>18,}".replace(",", "."))
    print(f"  Maliyet kolonu dolu   {dolu / adet * 100 if adet else 0:>17.1f}%")
    print(f"  Net miktar (giren−çıkan) {toplam['miktar']:>18,.2f}")
    print(f"  Net maliyet (ham)     {tl(ham):>18}")
    print(f"  Net sth_tutar         {tl(toplam['tutar']):>18}   (alışta maliyet, satışta")
    print(f"  {'':22}{'':18}    satış fiyatı — stok değeri DEĞİL)")
    # Sayı ayrı biçimlenir: tl() Türkçe ondalık üretir, cümlenin tamamında
    # virgül→nokta değiştirmek o rakamı bozardı (canlıda «2.000.000.00» çıktı).
    sayi = f"{aykiri_satir:,}".replace(",", ".")
    print(f"\n  Aykırı satır (>{tl(AYKIRI_SATIR_MALIYETI)}/satır)  {sayi:>8}")
    print(f"  {'Aykırıların net etkisi':<22}{tl(toplam['aykiri_maliyet']):>18}")
    print(f"  Temiz net maliyet     {tl(temiz):>18}   ← stok değeri adayı")

    print("\nEKSİK MALİYETİN YÖNÜ  (aykırılar birim maliyete girmez)\n")
    duzeltme = _yon_dok(yon)

    mizan = _dene_mizan(client, bit)
    if mizan is not None:
        print(f"\n  Mizan 15x stoğu       {tl(mizan):>18}")
        print(f"  Fark (mizan − temiz)  {tl(mizan - temiz):>18}")
        if duzeltme is not None:
            print(f"  Düzeltilmiş canlı     {tl(temiz + duzeltme):>18}")
            print(f"  Düzeltilmiş fark      {tl(mizan - temiz - duzeltme):>18}")

    print()
    if en_erken and en_erken[:4] > str(ilk_yil):
        print(f"  → DİKKAT: katalog {ilk_yil}'den başlıyor ama en erken stok hareketi")
        print(f"    {en_erken}. Öncesi ya yok ya da başka bir veritabanında —")
        print("    kümülatif eksik olabilir.")
    if aykiri_satir:
        print(f"  → HAYIR: {aykiri_satir} aykırı satır var (net etkisi "
              f"{tl(toplam['aykiri_maliyet'])}).")
        print("    Bunlar Mikro'da düzeltilmeden hiçbir stok rakamı güvenilir değil.")
        return
    oran = dolu / adet * 100 if adet else 0.0
    if oran < _ASGARI_DOLULUK:
        print(f"  → HAYIR: maliyet kolonu %{oran:.1f} dolu; eksik satırlar hem girişte hem")
        print("    çıkışta olduğu için net değerin yönü kestirilemez. Stok satırı «—» kalmalı.")
        return
    if duzeltme is None:
        print("  → HAYIR: boş satırların net etkisi ölçülemedi.")
        return
    pay = abs(duzeltme) / abs(temiz) * 100 if abs(temiz) > _SIFIR_TL else 100.0
    if pay > _AZAMI_DUZELTME_PAYI:
        print(f"  → HAYIR: boş satırların net etkisi {tl(duzeltme)}, temiz değerin %{pay:.1f}'i.")
        print("    Bu kadar oynayan bir rakam mizanın yerine konulamaz.")
        return
    print(f"  → EVET: aykırı satır yok, maliyet %{oran:.1f} dolu ve boş satırların net")
    print(f"    etkisi temiz değerin yalnız %{pay:.1f}'i. «Düzeltilmiş canlı» bağlanabilir.")


def _dene_mizan(client, bit: str) -> float | None:
    """Kıyas için mizanın 15x toplamı; okunamazsa None (teşhis yine de basılır)."""
    try:
        from domain.mizan_bilanco import build_bilanco
        from infra.mikro_fetch import fetch_mizan
        b = build_bilanco(fetch_mizan(client, bit), asof=bit)
        return sum(s.tutar for s in b.aktif if s.ana[:2] == "15")
    except Exception:  # noqa: BLE001 — teşhis aracı, kıyas satırı atlanır
        return None


def _faturalasma_teshisi(cfg: MikroConfig, bas: str, bit: str) -> None:
    """
    İrsaliye + fatura toplanınca satış iki kez sayılıyor mu?

    İş akışı: önce irsaliye, sonra carinin bekleyen irsaliyeleri toplu faturalaşıyor.
    İrsaliye satırı silinmiyor. Faturalaştırma AYRI bir stok hareketi yaratıyorsa
    toplam mükerrer; mevcut satırı damgalayıp geçiyorsa toplam doğru. `sth_fat_uid`
    o damga — sayı tahminiyle değil damgayla karar veriyoruz.
    """
    rows = donem_satirlari(cfg, bas, bit, fetch_stok_faturalasma)
    satis = [r for r in rows if int(_f(r.get("sth_tip", r.get("STH_TIP")))) == SATIS_TIP]
    alis = [r for r in rows if int(_f(r.get("sth_tip", r.get("STH_TIP")))) == 0]
    if not satis:
        print("\nFATURALAŞMA TEŞHİSİ: dönemde satış hareketi yok.")
        return

    def al(r: dict, ad: str) -> float:
        return _f(r.get(ad, r.get(ad.upper())))

    print(f"\nFATURALAŞMA TEŞHİSİ — çıkış hareketleri ({bas} → {bit})\n")
    print(f"  {'evraktip':>8} {'damga':>12}  {'satır':>8} {'tutar':>20}  açıklama")
    kova: dict[tuple[int, int], list[float]] = {}
    for r in satis:
        anahtar = (int(al(r, "sth_evraktip")), int(al(r, "faturalandi")))
        t = kova.setdefault(anahtar, [0.0, 0.0])
        t[0] += al(r, "adet")
        t[1] += al(r, "tutar")
    for (ev, fat), (adet, tutar) in sorted(kova.items()):
        damga = "faturalanmış" if fat else "—"
        print(f"  {ev:>8} {damga:>12}  {int(adet):>8} {tl(tutar):>20}  "
              f"{_EVRAK_AD.get((SATIS_TIP, ev), '?')}")

    irs_fat = kova.get((1, 1), [0.0, 0.0])       # faturalanmış irsaliye
    irs_bek = kova.get((1, 0), [0.0, 0.0])       # bekleyen irsaliye
    fatura = [sum(v[0] for (ev, _), v in kova.items() if ev == 4),
              sum(v[1] for (ev, _), v in kova.items() if ev == 4)]
    irs_top = irs_fat[1] + irs_bek[1]

    print(f"\n  İrsaliye toplam   {tl(irs_top):>20}  "
          f"({tl(irs_fat[1])} faturalanmış + {tl(irs_bek[1])} bekleyen)")
    print(f"  Fatura toplam     {tl(fatura[1]):>20}")

    print()
    if irs_fat[0] > 0 and fatura[0] < irs_fat[0] * _KOPYA_ESIGI:
        print("  → DAMGALAMA MODELİ: faturalaşan irsaliyeler yerinde duruyor ve ayrıca")
        print("    fatura satırı YARATILMIYOR. Faturalanmamış irsaliyeler de fiilen")
        print("    depodan çıkmış maldır, satışa dahil edilmeleri yerinde.")
        _fatura_ortakligi(cfg, bas, bit, fatura[1])

    # ALIŞ TARAFI da sorulmalı: satışta doğrulanan davranış alışta geçerli olmayabilir.
    # Canlıda satışta 262/17.914 iken alışta 2.492/6.592 — oran bambaşka.
    if alis:
        print("\n  ALIŞ TARAFI")
        alis_kova: dict[tuple[int, int], list[float]] = {}
        for r in alis:
            anahtar = (int(al(r, "sth_evraktip")), int(al(r, "faturalandi")))
            t = alis_kova.setdefault(anahtar, [0.0, 0.0])
            t[0] += al(r, "adet")
            t[1] += al(r, "tutar")
        _alis_teshisi(cfg, bas, bit, alis_kova)
    elif fatura[0] >= irs_fat[0] * _KOPYA_ESIGI and irs_fat[0] > 0:
        print("  → KOPYALAMA MODELİ ŞÜPHESİ: faturalanmış irsaliye kadar fatura satırı da")
        print("    var. İkisini toplamak satışı ~2 kat şişirir. «Satış: Yalnız Fatura»")
        print("    ayarına geçin (Nakit & Kârlılık → Hesaplama Kuralları).")
    else:
        print("  → Faturalanmış irsaliye satırı yok. Ya bu dönemde hiç faturalaştırma")
        print("    yapılmamış ya da bu kurulumda damga (sth_fat_uid) kullanılmıyor;")
        print("    ikinci durumda mükerrerlik bu yoldan ölçülemez.")


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
    if "--fatura" in sys.argv:
        _faturalasma_teshisi(cfg, bas, bit)
        return
    if "--bakiye" in sys.argv:
        _bakiye_teshisi(client, cfg, bit)
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
    # Ölçü verinin kendisinden: genel satır başı ortalama.
    genel_tutar = sum(v[0] for v in kirilim.values())
    genel_adet = sum(v[1] for v in kirilim.values())
    esik = (genel_tutar / genel_adet * _AYKIRI_GRUP_KAT) if genel_adet else 0.0
    supheli: list[tuple[int, int]] = []
    for (tip, ev), (tutar, adet_f) in sorted(kirilim.items(), key=lambda kv: -kv[1][0]):
        adet = int(adet_f)
        ad = _EVRAK_AD.get((tip, ev), "?")
        # Satır başı ortalama: bir mal hareketi satırının makul büyüklüğü.
        birim = tutar / adet if adet else 0.0
        if esik > 0 and birim > esik:
            ad += "  ← ŞÜPHELİ"
            supheli.append((tip, ev))
        print(f"  {tip:>3} {ev:>5}  {adet:>8}  {tl(tutar):>22}  {tl(birim):>16}  {ad}")
    for tip, ev in supheli:
        print(f"\nUYARI: tip={tip}/evraktip={ev} satır başı ortalaması genelin "
              f"{_AYKIRI_GRUP_KAT:.0f} katından fazla ({tl(esik)} üstü) —")
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
