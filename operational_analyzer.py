"""
İşletme parametreleri, kargo analizi ve operasyonel verimlilik metrikleri.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from fatura_analyzer import is_analiz_disı_stok_kodu
from parse_utils import format_tl

KARGO_KOD_PATTERN = re.compile(
    r"(^|\b)(KARGO|NAKLİYE|NAKLIYE|SEVKİYAT|SEVKIYAT|NAKLIYE\s*BEDEL)",
    re.IGNORECASE,
)
KARGO_ADI_PATTERN = re.compile(
    r"(^|\b)(KARGO|NAKLİYE|NAKLIYE|SEVKİYAT|SEVKIYAT|NAKLIYE\s*BEDEL)",
    re.IGNORECASE,
)
KARGO_MIZAN_ADI_PATTERN = re.compile(
    r"(kargo|nakliye|nakliyat|sevkiyat)",
    re.IGNORECASE,
)
KARGO_CARI_PATTERN = re.compile(
    r"(azim\s*ambar|"
    r"\baras\b|"
    r"zafer\s*kargo|"
    r"\bzafer\b|"
    r"yurti[cç]i|"
    r"yurtici|"
    r"\bkargo\b|"
    r"\bambar\b|"
    r"nakliye|"
    r"nakliyat|"
    r"remta[sş])",
    re.IGNORECASE,
)
PERSONEL_DEVLET_KEYWORDS = re.compile(
    r"(sgk|sosyal\s*güvenlik|işsizlik|issizlik|bordro|stopaj|damga)",
    re.IGNORECASE,
)
MAAS_MIZAN_FARK_ESIK = 5000.0
KARGO_BRUT_KAR_ESIK = 0.15
HARICI_MAAS_ORAN_ESIK = 0.15
SGK_BRUT_ORAN_MIN = 0.10
SGK_BRUT_ORAN_MAX = 0.25


@dataclass
class PersonelMaas:
    ad: str
    resmi_maas: float = 0.0
    harici_maas: float = 0.0

    @property
    def toplam(self) -> float:
        return self.resmi_maas + self.harici_maas


@dataclass
class GiderKalemi:
    hesap_kodu: str
    hesap_adi: str
    tutar: float


@dataclass
class PersonelGiderKalemi:
    hesap_kodu: str
    hesap_adi: str
    tutar: float
    kategori: str = ""


@dataclass
class KargoMizanKalemi:
    hesap_kodu: str
    hesap_adi: str
    tutar: float


@dataclass
class KargoTasiyiciOzet:
    cari_adi: str
    tutar: float


@dataclass
class IsletmeParametreleri:
    dukkan_metrekare: float = 0.0
    personel_maaslari: list[PersonelMaas] = field(default_factory=list)

    @property
    def personel_sayisi(self) -> int:
        return len(self.personel_maaslari)

    @property
    def toplam_resmi_maas(self) -> float:
        return sum(p.resmi_maas for p in self.personel_maaslari)

    @property
    def toplam_harici_maas(self) -> float:
        return sum(p.harici_maas for p in self.personel_maaslari)

    @property
    def toplam_maas(self) -> float:
        return sum(p.toplam for p in self.personel_maaslari)


KAR_TANIMLARI: list[str] = [
    "Aylık Analiz: Tüm göstergeler seçilen analiz ayına (YYYY-MM) göre hesaplanır.",
    "Ticari Brüt Kâr: Eşleşen alış–satış stok kodları; KDV hariç net tutar.",
    "Operasyonel Gider: Muavin 730/760/770 fiili hareket toplamı (borç − alacak).",
    "Gerçek Personel Maliyeti: Muavin 770.01/770.02 + kullanıcı harici maaş girişi.",
    "Aylık Net Kâr/Zarar: Brüt kâr − muavin 7xx giderleri − harici maaş.",
    "Nakit Akış: Banka hareketleri konsolide nakit havuzu; kâr kağıt üstündedir, nakit gerçektir.",
    "Kargo: Muavin kargo kalemleri + taşıyıcı cari alış faturaları; fatura öncelikli gösterge.",
    "Yaşlandırma: 120/320 cari kodu ile banka–fatura otomatik eşleştirme.",
]


@dataclass
class IsletmeAnalizi:
    toplam_resmi_maas_girilen: float = 0.0
    toplam_harici_maas_girilen: float = 0.0
    toplam_maas_girilen: float = 0.0
    yonetim_gider_mizan: float = 0.0
    brut_ucret_mizan: float = 0.0
    sgk_primi_mizan: float = 0.0
    issizlik_sigortasi_mizan: float = 0.0
    diger_personel_gider_mizan: float = 0.0
    toplam_devlet_yuku_mizan: float = 0.0
    toplam_personel_maliyeti_mizan: float = 0.0
    personel_gider_kalemleri: list[PersonelGiderKalemi] = field(default_factory=list)
    kargo_gider_mizan: float = 0.0
    kargo_mizan_kalemleri: list[KargoMizanKalemi] = field(default_factory=list)
    kargo_fatura_satis: float = 0.0
    kargo_fatura_alis: float = 0.0
    kargo_fatura_alis_stok: float = 0.0
    kargo_fatura_alis_cari: float = 0.0
    kargo_tasiyici_ozet: list[KargoTasiyiciOzet] = field(default_factory=list)
    kargo_gosterge_fatura: float = 0.0
    kargo_gosterge_kaynak: str = ""
    resmi_maas_mizan_fark: float = 0.0
    prim_ikramiye_tahmini: float = 0.0
    resmi_maas_esas: float = 0.0
    ticari_brut_kar: float = 0.0
    faaliyet_sonucu: float = 0.0
    toplam_gelir: float = 0.0
    toplam_gider: float = 0.0
    kargo_brut_kar_orani: float = 0.0
    kargo_ciro_orani: float = 0.0
    brut_kar_kargo_sonrasi: float = 0.0
    ciro_kisi: float | None = None
    gider_kisi: float | None = None
    brut_kar_kisi: float | None = None
    ciro_m2: float | None = None
    brut_kar_m2: float | None = None
    personel_sayisi: int = 0
    dukkan_metrekare: float = 0.0
    yorum: str = ""


def _is_kargo_mizan_kalem(hesap_kodu: str, hesap_adi: str) -> bool:
    kod = str(hesap_kodu).strip()
    ad = str(hesap_adi).strip()
    if kod == "770.08" or kod.startswith("770.08."):
        return True
    return bool(KARGO_MIZAN_ADI_PATTERN.search(ad))


def is_kargo_cari_adi(cari_adi: str) -> bool:
    """Alış faturasında taşıyıcı/nakliye cari adını tanır."""
    if "KAYNAKLIK" in str(cari_adi).upper():
        return False
    return bool(KARGO_CARI_PATTERN.search(str(cari_adi)))


def is_kargo_fatura_satir(
    stok_kodu: str,
    stok_adi: str,
    cari_adi: str = "",
    fatura_turu: str = "",
) -> bool:
    """Fatura satırının nakliye/kargo kalemi olup olmadığını belirler."""
    kod = str(stok_kodu).strip().upper()
    ad = str(stok_adi).strip().upper()
    if "KAYNAKLIK" in ad or "KAYNAKLIK" in kod:
        return False
    if KARGO_KOD_PATTERN.search(kod):
        return True
    if KARGO_ADI_PATTERN.search(ad):
        return True
    if fatura_turu == "alis" and cari_adi and is_kargo_cari_adi(cari_adi):
        return True
    return False


def _gider_kalemleri_list(gider_kalemleri: list[GiderKalemi] | object) -> list[GiderKalemi]:
    if isinstance(gider_kalemleri, list):
        return gider_kalemleri
    return [
        GiderKalemi(
            hesap_kodu=str(k.hesap_kodu),
            hesap_adi=str(k.hesap_adi),
            tutar=float(k.tutar),
        )
        for k in getattr(gider_kalemleri, "gider_kalemleri", []) or []
    ]


def _mizan_kargo_kalemleri(gider_kalemleri: list[GiderKalemi] | object) -> list[KargoMizanKalemi]:
    kalemler: list[KargoMizanKalemi] = []
    for k in _gider_kalemleri_list(gider_kalemleri):
        if _is_kargo_mizan_kalem(k.hesap_kodu, k.hesap_adi):
            kalemler.append(
                KargoMizanKalemi(
                    hesap_kodu=str(k.hesap_kodu),
                    hesap_adi=str(k.hesap_adi),
                    tutar=float(k.tutar),
                )
            )
    return sorted(kalemler, key=lambda x: x.hesap_kodu)


def _analyze_kargo_fatura(
    df: pd.DataFrame | None,
    fatura_turu: str,
) -> tuple[float, float, float, list[KargoTasiyiciOzet]]:
    """Stok nakliye, taşıyıcı cari ve toplam kargo tutarlarını döndürür."""
    if df is None or df.empty:
        return 0.0, 0.0, 0.0, []

    stok_total = 0.0
    cari_total = 0.0
    cari_map: dict[str, float] = {}

    for _, row in df.iterrows():
        kod = str(row.get("stok_kodu", ""))
        adi = str(row.get("stok_adi", ""))
        cari = str(row.get("cari_adi", ""))
        tutar = float(row.get("net_tutar", 0) or 0)

        stok_kargo = is_kargo_fatura_satir(kod, adi, cari_adi="", fatura_turu=fatura_turu)
        cari_kargo = (
            fatura_turu == "alis"
            and cari
            and is_kargo_cari_adi(cari)
        )

        if cari_kargo:
            cari_total += tutar
            key = cari.strip()
            cari_map[key] = cari_map.get(key, 0.0) + tutar
        elif stok_kargo:
            stok_total += tutar

    tasiyici = [
        KargoTasiyiciOzet(cari_adi=k, tutar=v)
        for k, v in sorted(cari_map.items(), key=lambda x: x[1], reverse=True)
    ]
    return stok_total, cari_total, stok_total + cari_total, tasiyici


def _mizan_gider_tutar(gider_kalemleri: list[GiderKalemi] | object, hesap_prefix: str) -> float:
    return sum(
        k.tutar for k in _gider_kalemleri_list(gider_kalemleri)
        if str(k.hesap_kodu).startswith(hesap_prefix)
    )


def _personel_kategori(hesap_kodu: str, hesap_adi: str) -> str:
    if _is_kargo_mizan_kalem(hesap_kodu, hesap_adi):
        return ""
    kod = str(hesap_kodu)
    if kod == "770.01" or kod.startswith("770.01."):
        return "brut_ucret"
    if kod == "770.02" or kod.startswith("770.02."):
        return "sgk"
    if kod == "770.03" or kod.startswith("770.03."):
        return "issizlik"
    ad = hesap_adi.lower()
    if PERSONEL_DEVLET_KEYWORDS.search(ad):
        return "devlet_yuku"
    if kod.startswith("770.0") and kod not in ("770.05", "770.08"):
        return "personel_diger"
    return ""


def _mizan_personel_giderleri(gider_kalemleri: list[GiderKalemi] | object) -> list[PersonelGiderKalemi]:
    kalemler: list[PersonelGiderKalemi] = []
    for k in _gider_kalemleri_list(gider_kalemleri):
        kod = str(k.hesap_kodu)
        if not kod.startswith("770"):
            continue
        kat = _personel_kategori(kod, k.hesap_adi)
        if kat:
            kalemler.append(
                PersonelGiderKalemi(
                    hesap_kodu=kod,
                    hesap_adi=k.hesap_adi,
                    tutar=k.tutar,
                    kategori=kat,
                )
            )
    return sorted(kalemler, key=lambda x: x.hesap_kodu)


def _build_yorum(sonuc: IsletmeAnalizi) -> str:
    parts: list[str] = []

    if sonuc.kargo_mizan_kalemleri:
        parts.append(
            f"Mizan kargo toplam {format_tl(sonuc.kargo_gider_mizan)} "
            f"({len(sonuc.kargo_mizan_kalemleri)} kalem)."
        )
    if sonuc.kargo_gosterge_kaynak:
        kaynak = "fatura alış" if sonuc.kargo_gosterge_kaynak == "fatura" else "mizan"
        parts.append(
            f"Kargo gösterge ({kaynak}): {format_tl(sonuc.kargo_gosterge_fatura)}."
        )
    if sonuc.ticari_brut_kar > 0 and sonuc.kargo_gosterge_fatura > 0:
        parts.append(
            f"Ticari brüt karın %{sonuc.kargo_brut_kar_orani * 100:.1f}'i "
            f"(gösterge brüt kar − kargo: {format_tl(sonuc.brut_kar_kargo_sonrasi)})."
        )
    if sonuc.kargo_fatura_alis > 0:
        parts.append(
            f"Alış faturası kargo: stok nakliye {format_tl(sonuc.kargo_fatura_alis_stok)}, "
            f"taşıyıcı cari {format_tl(sonuc.kargo_fatura_alis_cari)} "
            f"(mizan ile karşılaştırma amaçlı; toplamları doğrudan toplamayın)."
        )
    if sonuc.kargo_fatura_satis > 0:
        parts.append(
            f"Satış faturalarında nakliye/kargo satırları {format_tl(sonuc.kargo_fatura_satis)} "
            f"(müşteriye yansıtılan)."
        )

    if sonuc.personel_sayisi > 0 and sonuc.ciro_kisi is not None:
        parts.append(
            f"Personel başına ciro {format_tl(sonuc.ciro_kisi)}, "
            f"gider {format_tl(sonuc.gider_kisi or 0)}, "
            f"ticari brüt kar {format_tl(sonuc.brut_kar_kisi or 0)}."
        )

    if sonuc.dukkan_metrekare > 0 and sonuc.ciro_m2 is not None:
        parts.append(
            f"m² başına ciro {format_tl(sonuc.ciro_m2)}, "
            f"ticari brüt kar {format_tl(sonuc.brut_kar_m2 or 0)}."
        )

    if sonuc.toplam_resmi_maas_girilen > 0 or sonuc.toplam_harici_maas_girilen > 0:
        parts.append(
            f"Girilen maaş — resmi: {format_tl(sonuc.toplam_resmi_maas_girilen)}, "
            f"harici: {format_tl(sonuc.toplam_harici_maas_girilen)}, "
            f"toplam (nakit gösterge): {format_tl(sonuc.toplam_maas_girilen)}."
        )
        if sonuc.brut_ucret_mizan > 0:
            if sonuc.prim_ikramiye_tahmini > 0:
                parts.append(
                    f"Mizan 770.01 brüt ücretler {format_tl(sonuc.brut_ucret_mizan)}; "
                    f"mizan esas alındı, prim/ikramiye/kıdem yükü tahmini "
                    f"{format_tl(sonuc.prim_ikramiye_tahmini)}."
                )
            elif sonuc.resmi_maas_mizan_fark < -MAAS_MIZAN_FARK_ESIK:
                parts.append(
                    f"Mizan 770.01 brüt ücretler {format_tl(sonuc.brut_ucret_mizan)}; "
                    f"girilen resmi maaştan düşük (fark {format_tl(sonuc.resmi_maas_mizan_fark)})."
                )
            else:
                fark = sonuc.resmi_maas_mizan_fark
                parts.append(
                    f"Mizan 770.01 brüt ücretler {format_tl(sonuc.brut_ucret_mizan)}; "
                    f"resmi maaş farkı {format_tl(fark)}."
                )
        if sonuc.toplam_harici_maas_girilen > 0:
            parts.append(
                f"Harici maaş {format_tl(sonuc.toplam_harici_maas_girilen)} deftere yansımaz."
            )

    if sonuc.toplam_devlet_yuku_mizan > 0:
        parts.append(
            f"Mizan devlet yükü (SGK vb.): {format_tl(sonuc.toplam_devlet_yuku_mizan)}; "
            f"toplam personel maliyeti (mizan): {format_tl(sonuc.toplam_personel_maliyeti_mizan)}."
        )

    if not parts:
        parts.append("İşletme parametreleri girildiğinde verimlilik metrikleri hesaplanır.")
    return " ".join(parts)


def analyze_operasyonel(
    gider_kalemleri: list[GiderKalemi],
    params: IsletmeParametreleri | None,
    fatura_kar: object | None = None,
    alis_fatura_df: pd.DataFrame | None = None,
    satis_fatura_df: pd.DataFrame | None = None,
) -> IsletmeAnalizi:
    """Muavin gider kalemleri ve işletme parametreleriyle operasyonel analiz."""
    p = params or IsletmeParametreleri()
    ticari_brut = float(getattr(fatura_kar, "toplam_brut_kar", 0) or 0) if fatura_kar else 0.0
    kargo_mizan_kalemleri = _mizan_kargo_kalemleri(gider_kalemleri)
    kargo_mizan = sum(k.tutar for k in kargo_mizan_kalemleri)
    yonetim_770 = _mizan_gider_tutar(gider_kalemleri, "770")
    personel_kalemler = _mizan_personel_giderleri(gider_kalemleri)

    brut_ucret = sum(k.tutar for k in personel_kalemler if k.kategori == "brut_ucret")
    sgk = sum(k.tutar for k in personel_kalemler if k.kategori == "sgk")
    issizlik = sum(k.tutar for k in personel_kalemler if k.kategori == "issizlik")
    diger_devlet = sum(
        k.tutar for k in personel_kalemler
        if k.kategori in ("devlet_yuku", "personel_diger")
    )
    toplam_devlet = sgk + issizlik + diger_devlet
    toplam_personel_mizan = brut_ucret + toplam_devlet

    kargo_alis_stok, kargo_alis_cari, kargo_alis, tasiyici = _analyze_kargo_fatura(
        alis_fatura_df, "alis"
    )
    kargo_satis_stok, _, kargo_satis, _ = _analyze_kargo_fatura(satis_fatura_df, "satis")

    toplam_gider = sum(k.tutar for k in gider_kalemleri)
    toplam_gelir = ticari_brut
    faaliyet = ticari_brut - toplam_gider

    kargo_gosterge = kargo_alis if kargo_alis > 0 else kargo_mizan
    kargo_kaynak = "fatura" if kargo_alis > 0 else "mizan"
    kargo_oran = (kargo_gosterge / ticari_brut) if ticari_brut > 0 else 0.0
    kargo_ciro = (kargo_mizan / toplam_gelir) if toplam_gelir > 0 else 0.0

    resmi_esas = (
        brut_ucret if brut_ucret > p.toplam_resmi_maas else p.toplam_resmi_maas
    )
    maas_fark = brut_ucret - p.toplam_resmi_maas
    prim_tahmini = maas_fark if maas_fark > 0 else 0.0

    sonuc = IsletmeAnalizi(
        toplam_resmi_maas_girilen=p.toplam_resmi_maas,
        toplam_harici_maas_girilen=p.toplam_harici_maas,
        toplam_maas_girilen=p.toplam_maas,
        yonetim_gider_mizan=yonetim_770,
        brut_ucret_mizan=brut_ucret,
        sgk_primi_mizan=sgk,
        issizlik_sigortasi_mizan=issizlik,
        diger_personel_gider_mizan=diger_devlet,
        toplam_devlet_yuku_mizan=toplam_devlet,
        toplam_personel_maliyeti_mizan=toplam_personel_mizan,
        personel_gider_kalemleri=personel_kalemler,
        kargo_gider_mizan=kargo_mizan,
        kargo_mizan_kalemleri=kargo_mizan_kalemleri,
        kargo_fatura_satis=kargo_satis,
        kargo_fatura_alis=kargo_alis,
        kargo_fatura_alis_stok=kargo_alis_stok,
        kargo_fatura_alis_cari=kargo_alis_cari,
        kargo_tasiyici_ozet=tasiyici,
        kargo_gosterge_fatura=kargo_gosterge,
        kargo_gosterge_kaynak=kargo_kaynak,
        resmi_maas_mizan_fark=maas_fark,
        prim_ikramiye_tahmini=prim_tahmini,
        resmi_maas_esas=resmi_esas,
        ticari_brut_kar=ticari_brut,
        faaliyet_sonucu=faaliyet,
        toplam_gelir=toplam_gelir,
        toplam_gider=toplam_gider,
        kargo_brut_kar_orani=kargo_oran,
        kargo_ciro_orani=kargo_ciro,
        brut_kar_kargo_sonrasi=ticari_brut - kargo_gosterge,
        personel_sayisi=p.personel_sayisi,
        dukkan_metrekare=p.dukkan_metrekare,
    )

    if p.personel_sayisi > 0:
        sonuc.ciro_kisi = toplam_gelir / p.personel_sayisi
        sonuc.gider_kisi = toplam_gider / p.personel_sayisi
        sonuc.brut_kar_kisi = ticari_brut / p.personel_sayisi if ticari_brut else None

    if p.dukkan_metrekare > 0:
        sonuc.ciro_m2 = toplam_gelir / p.dukkan_metrekare
        sonuc.brut_kar_m2 = ticari_brut / p.dukkan_metrekare if ticari_brut else None

    sonuc.yorum = _build_yorum(sonuc)
    return sonuc


def analyze_isletme(
    gelir_gider: object,
    params: IsletmeParametreleri | None,
    fatura_kar: object | None = None,
    alis_fatura_df: pd.DataFrame | None = None,
    satis_fatura_df: pd.DataFrame | None = None,
) -> IsletmeAnalizi:
    """Geriye dönük uyumluluk: gelir_gider nesnesinden operasyonel analiz."""
    kalemler = _gider_kalemleri_list(gelir_gider)
    return analyze_operasyonel(
        kalemler, params, fatura_kar, alis_fatura_df, satis_fatura_df
    )


def _fatura_urun_tutar(df: pd.DataFrame | None) -> float:
    """MUH/AD-MUH hariç fatura net tutar toplamı."""
    if df is None or df.empty:
        return 0.0
    total = 0.0
    for _, row in df.iterrows():
        if is_analiz_disı_stok_kodu(str(row.get("stok_kodu", ""))):
            continue
        total += float(row.get("net_tutar", 0) or 0)
    return total
