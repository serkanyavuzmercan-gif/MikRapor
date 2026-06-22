"""
Merkezi gösterge etiketleri — ay bazlı CFO KPI'ları.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricLabel:
    key: str
    title: str
    formula: str
    source: str = ""

    @property
    def full_title(self) -> str:
        if self.formula and self.source:
            return f"{self.title} ({self.formula}; {self.source})"
        if self.formula:
            return f"{self.title} ({self.formula})"
        return self.title


METRICS: dict[str, MetricLabel] = {
    "aylik_net_kar": MetricLabel(
        "aylik_net_kar",
        "Aylık Net Kâr/Zarar",
        "brüt kâr − muavin 7xx − harici maaş",
        "seçilen analiz ayı",
    ),
    "nakit_akis": MetricLabel(
        "nakit_akis",
        "Nakit Akış Özeti",
        "dönem başı / giriş / çıkış / dönem sonu",
        "banka ekstresi",
    ),
    "nakit_donusum": MetricLabel(
        "nakit_donusum",
        "Nakit Dönüşüm Hızı",
        "120 banka giriş / ay satış faturası",
        "banka + fatura",
    ),
    "runway": MetricLabel(
        "runway",
        "Şirket Ömrü (Runway)",
        "kârda: nakit/gider; zararda: nakit/|net zarar|",
        "banka + muavin",
    ),
    "veri_eslesme": MetricLabel(
        "veri_eslesme",
        "Veri Eşleşme Skoru",
        "eşleşen banka çıkış (102 hariç) / toplam çıkış",
        "banka + muavin + fatura",
    ),
    "brut_kar": MetricLabel(
        "brut_kar",
        "Brüt Kâr (Fatura)",
        "eşleşen alış–satış stok marjı",
        "seçilen ay fatura",
    ),
    "operasyonel_gider": MetricLabel(
        "operasyonel_gider",
        "Operasyonel Gider (7xx)",
        "muavin gider hesapları toplamı",
        "seçilen ay muavin",
    ),
    "harici_maas": MetricLabel(
        "harici_maas",
        "Harici Maaş",
        "defter dışı personel ödemesi",
        "manuel girilen",
    ),
    "resmi_maas": MetricLabel(
        "resmi_maas",
        "Resmi Maaş",
        "bordro / deftere yazılan ücret",
        "manuel girilen aylık",
    ),
    "nakit_personel_yuku": MetricLabel(
        "nakit_personel_yuku",
        "Nakit Personel Yükü",
        "resmi maaş + harici maaş",
        "manuel girilen",
    ),
    "ic_transfer": MetricLabel(
        "ic_transfer",
        "Hesaplar Arası Transfer (102)",
        "banka giriş/çıkış — karşı hesap 102",
        "banka ekstresi",
    ),
    "tahsil_edilemeyen": MetricLabel(
        "tahsil_edilemeyen",
        "Tahsil Edilemeyen Satışlar",
        "dönem sonuna kadar 120 satış faturası − kümülatif 120 banka girişi",
        "fatura + banka",
    ),
    "odenmeyen": MetricLabel(
        "odenmeyen",
        "Ödenmeyen Alış Faturaları",
        "dönem sonuna kadar 320 alış faturası − kümülatif 320 banka çıkışı",
        "fatura + banka",
    ),
    "vade_net": MetricLabel(
        "vade_net",
        "Vade Neti",
        "vadesi gelmeyen tahsilat − vadesi gelmeyen ödeme",
        "120/320 plan",
    ),
    "likidite_plan": MetricLabel(
        "likidite_plan",
        "Likidite (Plan)",
        "plan tahsilat − plan ödeme",
        "anlık plan",
    ),
}


def metric_title(key: str) -> str:
    """Gösterge anahtarı için parantezli tam başlık döndürür."""
    m = METRICS.get(key)
    if m is None:
        return key
    return m.full_title


def metric_short(key: str) -> str:
    """Kısa başlık (parantezsiz)."""
    m = METRICS.get(key)
    return m.title if m else key


def metric_source(key: str) -> str:
    """Kaynak açıklaması."""
    m = METRICS.get(key)
    return m.source if m else ""


def metric_kaynak(key: str) -> str:
    """Tablo raporları için formül + kaynak sütunu metni."""
    m = METRICS.get(key)
    if m is None:
        return ""
    if m.formula and m.source:
        return f"{m.formula}; {m.source}"
    if m.formula:
        return m.formula
    return m.source
