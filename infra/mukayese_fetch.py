"""
Yıllar arası mukayese için yıl kapanışlarını çeker.

İki sekme aynı tabloyu besler (Trend & Oranlar gösterir, Yapay Zekâ Yorumu modele
gönderir), o yüzden çekme mantığı burada tektir — iki yerde ayrı yazılırsa rakamlar
zamanla ayrışır.

KAYNAK SEÇİMİ KRİTİK: alacak/borç/nakit MİZANDAN alınmaz, ilgili sekmelerin canlı
kaynağından gelir. Mizanın 120/320 bakiyeleri her kurulumda işlenmiyor; canlıda
Alıcılar -4.839 TL görünürken cari hesaplarda 11,4 milyon TL alacak vardı ve tablo
beş yıl boyunca sabit çıkıyordu. Canlı kaynak okunamazsa mizana düşülür.
"""

from __future__ import annotations

from collections.abc import Callable

from domain.ai_yorum import YilKapanis
from domain.gelir_tablosu import GelirTablosu, build_gelir_tablosu
from domain.mizan_bilanco import Bilanco, build_bilanco
from domain.tahsilat_alacak import TahsilatAlacak, build_tahsilat_alacak
from domain.trend import build_finansal_oranlar
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import (
    fetch_acik_kalemler,
    fetch_cari_vade_gun,
    fetch_doviz_ozet,
    fetch_gelir_tablosu,
    fetch_mizan,
    fetch_nakit_bakiye_gl,
)

# Okuma hataları: bir yıl veritabanında yoksa sorgu hata değil boş döner, ama şema
# farkı gerçek hata verebilir — ikisinde de o yılı atlarız, rapor komple düşmez.
_OKUMA_HATALARI = (MikroAPIError, ValueError, KeyError, TypeError)

# 300 Banka Kredileri (KV), 303 UV kredilerin anapara taksitleri, 400 Banka Kredileri (UV).
_KREDI_ANA = {"300", "303", "400"}


def _banka_kredisi(b: Bilanco) -> float:
    """Kredi borçluluğunun yıllar arası trendi — pasifte kredi hesaplarının toplamı."""
    return sum(s.tutar for s in b.pasif if s.ana in _KREDI_ANA)


def kapanis_kur(yil: int, *, tam: bool, b: Bilanco, gt: GelirTablosu,
                doviz: dict[str, float] | None = None,
                ta: TahsilatAlacak | None = None,
                nakit_gl: float | None = None) -> YilKapanis:
    """Çekilmiş parçalardan bir yılın karşılaştırma satırını kurar (saf birleştirme)."""
    _, ozet = build_finansal_oranlar(b)
    d = doviz or {}
    return YilKapanis(
        yil=yil, tam=tam,
        net_satis=gt.net_satislar, brut_kar=gt.brut_kar,
        faaliyet_kari=gt.faaliyet_kari, net_kar=gt.net_kar,
        nakit=ozet["nakit"] if nakit_gl is None else nakit_gl,
        alacak=ozet["alacak"] if ta is None else ta.alacak_toplam,
        borc=0.0 if ta is None else ta.borc_toplam,
        alacak_gecikmis=0.0 if ta is None else ta.alacak_gecikmis,
        stok=ozet["stok"], kvyk=ozet["kvyk"], uvyk=ozet["uvyk"], donen=ozet["donen"],
        ozkaynak=ozet["ozkaynak"], aktif_toplam=ozet["aktif_toplam"],
        banka_kredisi=_banka_kredisi(b), smm=gt.smm, maliyet_eksik=gt.maliyet_eksik,
        faaliyet_gideri=gt.faaliyet_gideri, finansman_gideri=gt.finansman_gideri,
        satis_usd=d.get("satis_usd", 0.0), kur_son=d.get("kur_son", 0.0))


def _dene(fn, varsayilan=None):
    """Yardımcı kaynak okunamazsa yıl komple düşmesin — o kalem eksik kalır."""
    try:
        return fn()
    except _OKUMA_HATALARI:
        return varsayilan


def yil_kapanisi(client: MikroClient, yil: int, *, bit: str | None = None,
                 tam: bool = True, vade_gun: dict | None = None,
                 ta: TahsilatAlacak | None = None) -> YilKapanis:
    """
    Tek bir yılın kapanış fotoğrafı.

    `bit` verilmezse 31 Aralık kullanılır (kapanmış yıl). `ta` verilirse yeniden
    çekilmez — odak yılda Alacak & Borç zaten çekilmiş olur.
    """
    bas = f"{yil}-01-01"
    son = bit or f"{yil}-12-31"
    b = build_bilanco(fetch_mizan(client, son), asof=son)
    gt = build_gelir_tablosu(fetch_gelir_tablosu(client, bas, son), bas=bas, bit=son)
    if ta is None:
        ta = _dene(lambda: build_tahsilat_alacak(
            fetch_acik_kalemler(client, son, bas, son),
            vade_gun_map=vade_gun or {}, bas=bas, bit=son, top_n=1))
    return kapanis_kur(
        yil, tam=tam, b=b, gt=gt,
        doviz=_dene(lambda: fetch_doviz_ozet(client, bas, son), {}),
        ta=ta, nakit_gl=_dene(lambda: fetch_nakit_bakiye_gl(client, son)))


def yillari_cek(
    client: MikroClient,
    yillar: list[int],
    *,
    odak_bit: str = "",
    odak_tam: bool = True,
    odak_ta: TahsilatAlacak | None = None,
    bildir: Callable[[str], None] | None = None,
) -> list[YilKapanis]:
    """
    Verilen yılların kapanışlarını çeker; veritabanında olmayan yıllar sessizce düşer.

    Listenin SONU odak yıldır: bitişi bugünle sınırlı olabilir (devam eden yıl) ve
    Alacak & Borç verisi zaten çekilmiş olabilir.
    """
    if not yillar:
        return []
    odak = max(yillar)
    vade_gun = _dene(lambda: fetch_cari_vade_gun(client), {}) or {}
    out: list[YilKapanis] = []
    gecmis = [y for y in sorted(yillar) if y != odak]

    for sira, y in enumerate(gecmis, 1):
        if bildir:
            bildir(f"{y} yılı mukayese için çekiliyor… ({sira}/{len(gecmis)})")
        k = _dene(lambda y=y: yil_kapanisi(client, y, vade_gun=vade_gun))
        if k is not None and k.dolu:   # boş yıl sıfır satırı olarak tabloya girmesin
            out.append(k)

    if bildir and gecmis:
        bildir(f"{odak} yılı mukayeseye ekleniyor…")
    odak_k = _dene(lambda: yil_kapanisi(
        client, odak, bit=odak_bit or None, tam=odak_tam,
        vade_gun=vade_gun, ta=odak_ta))
    if odak_k is not None:
        out.append(odak_k)
    return out
