"""
Yıllar arası mukayese için yıl kapanışlarını çeker.

İki sekme aynı tabloyu besler (Trend & Oranlar gösterir, Yapay Zekâ Yorumu modele
gönderir), o yüzden çekme mantığı burada tektir — iki yerde ayrı yazılırsa rakamlar
zamanla ayrışır.

KAYNAK SEÇİMİ KRİTİK: alacak/borç/nakit MİZANDAN alınmaz, ilgili sekmelerin canlı
kaynağından gelir. Mizanın 120/320 bakiyeleri her kurulumda işlenmiyor; canlıda
Alıcılar -4.839 TL görünürken cari hesaplarda 11,4 milyon TL alacak vardı ve tablo
beş yıl boyunca sabit çıkıyordu. Canlı kaynak okunamazsa mizana düşülür.

HER YIL ÖNCE KENDİ ÇALIŞMA YILIYLA DENENİR: Mikro auth gövdesinde CalismaYili gider ve
sunucu isteği O YILIN veritabanına yönlendirir. Tek bir client ile geçmiş yılları
sorgulamak, tarih süzgeci doğru olsa bile hep aynı veritabanını okur — canlıda 2021
ile 2025 bilançosu kuruşu kuruşuna aynı çıkıyordu.

VERİTABANINI ASIL SEÇEN FİRMA KODUDUR. Ayarlarda birden çok firma kodu tanımlıysa
(canlıda 20 → 2020-2025, 26 → 2026+) her yıl kendi veritabanından okunur; eşleme
infra.veritabani kataloğundan gelir.

AMA O YILIN VERİTABANI OLMAYABİLİR (tek veritabanında birkaç yıl tutan kurulumlar).
O yüzden yıl bazlı deneme başarısız olur ya da boş dönerse SEÇİLİ çalışma yılıyla
tekrar denenir. İkisi de boşsa yıl atlanır. Yıl bazlı denemeyi tek yol yapmak canlıda
tabloyu komple düşürmüştü — iki yıl seçilmesine rağmen mukayese çıkmıyordu.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date

from domain.ai_yorum import YilKapanis
from domain.gelir_tablosu import GelirTablosu, build_gelir_tablosu
from domain.mizan_bilanco import Bilanco, build_bilanco
from domain.tahsilat_alacak import TahsilatAlacak, build_tahsilat_alacak
from domain.trend import build_finansal_oranlar
from infra.config import MikroConfig
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import (
    fetch_acik_kalemler,
    fetch_cari_vade_gun,
    fetch_doviz_ozet,
    fetch_gelir_tablosu,
    fetch_mizan,
    fetch_nakit_bakiye_gl,
    fetch_nakit_ozet_ve_aylik,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from infra.veritabani import katalog, yil_icin_firma

# Okuma hataları: bir yıl veritabanında yoksa sorgu hata değil boş döner, ama şema
# farkı gerçek hata verebilir — ikisinde de o yılı atlarız, rapor komple düşmez.
_OKUMA_HATALARI = (MikroAPIError, ValueError, KeyError, TypeError)

# 300 Banka Kredileri (KV), 303 UV kredilerin anapara taksitleri, 400 Banka Kredileri (UV).
_KREDI_ANA = {"300", "303", "400"}


class YilVeritabaniHatasi(ValueError):
    """İstenen yıl için kapsamı Mikro'dan doğrulanmış veritabanı yok."""


def yil_donemleri(bas: str, bit: str) -> list[tuple[int, str, str]]:
    """Tarih aralığını, her biri tek bir takvim yılında kalan parçalara ayırır.

    Mikro'da geçmiş yıl çoğu kurulumda ayrı firma/veritabanındadır. Bu yüzden
    ``2025-07-28..2026-07-28`` gibi bir aralık tek istemciyle okunmamalıdır:
    2025 parçası 2025 istemcisiyle, 2026 parçası 2026 istemcisiyle çekilir.
    """
    ilk, son = date.fromisoformat(bas), date.fromisoformat(bit)
    if ilk > son:
        raise ValueError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")

    out: list[tuple[int, str, str]] = []
    yil = ilk.year
    while yil <= son.year:
        parca_bas = ilk if yil == ilk.year else date(yil, 1, 1)
        parca_son = son if yil == son.year else date(yil, 12, 31)
        out.append((yil, parca_bas.isoformat(), parca_son.isoformat()))
        yil += 1
    return out


def donem_parcalari(
    cfg: MikroConfig, bas: str, bit: str,
    *, bildir: Callable[[str], None] | None = None,
    ad: str = "hareketler",
) -> Iterator[tuple[MikroClient, str, str]]:
    """
    Dönemi yıllara bölüp her parça için KENDİ veritabanının istemcisini verir.

    Yalnız AKIŞ sorguları için: dönem içi hareketleri gruplayarak döndüren sorgular
    (gelir tablosu 6xx hareketleri, stok hareketleri, GL nakit hareketleri). Bunların
    tüketicileri satırları toplayarak yediği için aynı hesap/ay iki parçadan da gelse
    doğru toplanır — parçalar takvim yılında ayrıldığı için ay/tarih de çakışmaz.

    BAKİYE/FOTOĞRAF sorguları bölünemez — onlar tek bir tarihe aittir ve bitişin
    veritabanından okunur (mizan, kapanış nakdi, cari bakiye, açık kalemler).

    Tek parça varsa fazladan hiçbir şey yapılmaz; tek veritabanlı kurulum eskisi gibi.
    """
    parcalar = yil_donemleri(bas, bit)
    for sira, (yil, p_bas, p_bit) in enumerate(parcalar, 1):
        if bildir and len(parcalar) > 1:
            bildir(f"{yil} veritabanından {ad} çekiliyor… ({sira}/{len(parcalar)})")
        yield yil_client(cfg, yil), p_bas, p_bit


def donem_satirlari(
    cfg: MikroConfig, bas: str, bit: str,
    cek: Callable[[MikroClient, str, str], list[dict]],
    *, bildir: Callable[[str], None] | None = None,
    ad: str = "hareketler",
) -> list[dict]:
    """Tek bir akış sorgusunu dönemin bütün veritabanlarından okuyup birleştirir."""
    out: list[dict] = []
    for c, p_bas, p_bit in donem_parcalari(cfg, bas, bit, bildir=bildir, ad=ad):
        out.extend(cek(c, p_bas, p_bit))
    return out


def donem_toplami(
    cfg: MikroConfig, bas: str, bit: str,
    cek: Callable[[MikroClient, str, str], float],
) -> float:
    """
    Dönem boyunca TOPLANABİLİR tek bir sayıyı yıl yıl okuyup toplar (ör. nakit deltası).

    Delta bir SUM olduğu için parçalarının toplamı bütünün toplamına eşittir; bakiye
    veya oran gibi bölünemez büyüklükler için KULLANILMAZ.
    """
    return sum(cek(c, p_bas, p_bit)
               for c, p_bas, p_bit in donem_parcalari(cfg, bas, bit))


def donem_hareketleri(
    cfg: MikroConfig, bas: str, bit: str,
    *, bildir: Callable[[str], None] | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    Nakit & Kârlılık ve Trend sekmelerinin ortak akış seti.

    Dönüş: (stok, stok_aylık, nakit, nakit_aylık). Dördü de akış olduğu için dönem
    iki veritabanına yayıldığında parçaları birleştirilir. İki sekme aynı rakamı
    göstermek zorunda — çekme burada tektir.
    """
    stok_rows: list[dict] = []
    stok_aylik: list[dict] = []
    nakit_rows: list[dict] = []
    nakit_aylik: list[dict] = []
    for c, p_bas, p_bit in donem_parcalari(
            cfg, bas, bit, bildir=bildir, ad="stok ve nakit hareketleri"):
        stok_rows.extend(fetch_stok_ozet(c, p_bas, p_bit))
        stok_aylik.extend(fetch_stok_aylik(c, p_bas, p_bit))
        n_rows, n_aylik = fetch_nakit_ozet_ve_aylik(c, p_bas, p_bit)
        nakit_rows.extend(n_rows)
        nakit_aylik.extend(n_aylik)
    return stok_rows, stok_aylik, nakit_rows, nakit_aylik


def _banka_kredisi(b: Bilanco) -> float:
    """Kredi borçluluğunun yıllar arası trendi — pasifte kredi hesaplarının toplamı."""
    return sum(s.tutar for s in b.pasif if s.ana in _KREDI_ANA)


def kapanis_kur(yil: int, *, tam: bool, b: Bilanco, gt: GelirTablosu,
                bit: str = "",
                doviz: dict[str, float] | None = None,
                ta: TahsilatAlacak | None = None,
                nakit_gl: float | None = None) -> YilKapanis:
    """Çekilmiş parçalardan bir yılın karşılaştırma satırını kurar (saf birleştirme)."""
    _, ozet = build_finansal_oranlar(b)
    d = doviz or {}
    return YilKapanis(
        yil=yil, tam=tam, bit=bit,
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
        satis_usd=d.get("satis_usd", 0.0), kur_son=d.get("kur_son", 0.0),
        kur_ort=d.get("kur_ortalama", 0.0))


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
        yil, tam=tam, bit=son, b=b, gt=gt,
        doviz=_dene(lambda: fetch_doviz_ozet(client, bas, son), {}),
        ta=ta, nakit_gl=_dene(lambda: fetch_nakit_bakiye_gl(client, son)))


def ayni_gune_kirp(yil: int, odak_bit: str) -> tuple[str, bool]:
    """
    Geçmiş yılı, odak yılın bittiği AY-GÜNE kırpar. Dönüş: (bitiş, yıl tam mı).

    Odak yıl devam ederken geçmiş yılı TAM okumak elmayla armut kıyaslamaktır: canlıda
    27.07.2025-28.07.2026 seçilmişken 2025 sütunu 12 aylık, 2026 sütunu 7 aylıktı ve
    ciro «%59 düştü» görünüyordu. Aynı güne kırpınca kıyas yıldan yıla aynı pencereyi
    kullanır. Odak yıl tamamlanmışsa (31 Aralık) hepsi tam yıl kalır.
    """
    if not odak_bit or odak_bit.endswith("-12-31"):
        return f"{yil}-12-31", True
    ay, gun = int(odak_bit[5:7]), int(odak_bit[8:10])
    gun = min(gun, monthrange(yil, ay)[1])      # 29 Şubat her yıl yok
    return f"{yil}-{ay:02d}-{gun:02d}", False


def yil_client(cfg: MikroConfig, yil: int) -> MikroClient:
    """
    O yılın verisini taşıyan veritabanına bağlanan istemci.

    Veritabanını asıl seçen FİRMA KODUDUR; `calisma_yili` yalnız auth gövdesinde gider.

    İKİ AYRI DURUM, İKİ AYRI DAVRANIŞ:

    • Katalog DOLU ama istenen yıl hiçbir kapsamda değil → rapor DURUR. Birden çok
      veritabanı varken yanlışını seçmek sessizce yanlış rakam üretir; canlıda 2023'ü
      firma 26'da aramak tam olarak buydu.
    • Katalog BOŞ (hiç kod tanımlı değil ya da yoklama ağ hatasıyla düştü) → seçili
      firmayla devam edilir. Seçenek tek olduğunda «yanlışını seçmek» diye bir şey
      yoktur; burada durmak, geçici bir ağ hatasında programı komple kullanılamaz
      yapardı — mukayese tablosunun hiç çıkmaması sorunu tam da böyle doğmuştu.
    """
    temel = replace(cfg.normalized(), calisma_yili=yil)
    kapsamlar = katalog(cfg)
    kod = yil_icin_firma(kapsamlar, yil)
    if not kod:
        if kapsamlar:
            bulunan = ", ".join(
                f"{k.firma_kodu} ({k.ilk_yil}–{k.son_yil})" for k in kapsamlar)
            raise YilVeritabaniHatasi(
                f"{yil} yılı için kapsamı doğrulanmış veritabanı bulunamadı. "
                f"Bulunan kapsamlar: {bulunan}. Mikro Ayarları'ndan kodları kontrol edip "
                "‘Yılları Tara’ ile yeniden doğrulayın."
            )
        return MikroClient(temel)          # katalog kurulamadı → seçili firma
    temel = replace(temel, firma_kodu=kod)
    return MikroClient(temel)


def yillari_cek(
    cfg: MikroConfig,
    yillar: list[int],
    *,
    odak_client: MikroClient | None = None,
    odak_bit: str = "",
    odak_tam: bool = True,
    odak_ta: TahsilatAlacak | None = None,
    bildir: Callable[[str], None] | None = None,
) -> list[YilKapanis]:
    """
    Verilen yılların kapanışlarını çeker; veritabanında olmayan yıllar sessizce düşer.

    Her yıl KENDİ çalışma yılıyla sorgulanır (bkz. modül başlığı). Listenin SONU odak
    yıldır: bitişi bugünle sınırlı olabilir (devam eden yıl), Alacak & Borç verisi zaten
    çekilmiş olabilir ve çağıran kendi istemcisini verebilir.
    """
    if not yillar:
        return []
    odak = max(yillar)
    out: list[YilKapanis] = []
    gecmis = [y for y in sorted(yillar) if y != odak]

    for sira, y in enumerate(gecmis, 1):
        if bildir:
            bildir(f"{y} yılı mukayese için çekiliyor… ({sira}/{len(gecmis)})")
        k = _gecmis_yil(cfg, y, odak_bit)
        if k is not None and k.dolu:   # boş yıl sıfır satırı olarak tabloya girmesin
            out.append(k)

    if bildir and gecmis:
        bildir(f"{odak} yılı mukayeseye ekleniyor…")
    client = odak_client or yil_client(cfg, odak)
    odak_k = _dene(lambda: yil_kapanisi(
        client, odak, bit=odak_bit or None, tam=odak_tam,
        vade_gun=_dene(lambda: fetch_cari_vade_gun(client), {}) or {}, ta=odak_ta))
    if odak_k is not None:
        out.append(odak_k)
    return out


def _gecmis_yil(cfg: MikroConfig, yil: int, odak_bit: str = "") -> YilKapanis | None:
    """
    Geçmiş yıl yalnız kendi kapsamı doğrulanmış veritabanından okunur. Bitiş, odak
    yılın bittiği ay-güne kırpılır — kıyas aynı pencereden yapılsın.
    """
    son, tam = ayni_gune_kirp(yil, odak_bit)
    c = yil_client(cfg, yil)
    k = _dene(lambda: yil_kapanisi(
        c, yil, bit=son, tam=tam,
        vade_gun=_dene(lambda: fetch_cari_vade_gun(c), {}) or {}))
    return k if k is not None and k.dolu else None
