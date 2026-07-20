"""
Sade dil sözlüğü — finansal jargonu esnafın anlayacağı günlük dile çevirir.

Değerlendirmedeki "formül-tekrarı açıklamalar bilinmeyeni bilinmeyenle tanımlıyor"
eleştirisine yanıt: her oran/terim, formülü değil NE İŞE YARADIĞINI ve (varsa) sağlıklı
aralığını anlatır. Saf veri + getter — kolay test edilir, UI yalnızca gösterir.
"""

from __future__ import annotations

# Oran kodu → sade açıklama (ne işe yarar + sağlıklı aralık). Formül tekrarı DEĞİL.
SADE_ORAN: dict[str, str] = {
    "cari": "Kısa vadeli borçlarını dönen varlıklarınla ödeyebilme gücün. 1'in üstü iyi, 1,5–2 rahat.",
    "asit": "Stoklarını satmadan, sadece nakit ve alacaklarınla kısa vadeli borç ödeme gücün. "
            "1 civarı sağlıklı.",
    "nakit_oran": "Sadece kasandaki/bankadaki parayla kısa vadeli borcunun ne kadarını hemen "
                  "ödeyebilirsin. 0,20 ve üstü rahat.",
    "borc_oz": "Kendi paranın (özkaynak) kaç katı borcun var. 1'in altı sağlıklı; "
               "yükseldikçe risk artar.",
    "oz_oran": "İşletmenin yüzde kaçı kendi paranla (borçsuz) dönüyor. Yüksek olması güçlüdür.",
    "kv_oran": "Varlıklarının yüzde kaçı 1 yıl içinde ödenecek borç. Düşük olması rahatlıktır.",
    "donen_oran": "Varlıklarının yüzde kaçı 1 yıl içinde nakde dönebilir (kasa, alacak, stok). "
                  "Yüksek = daha akışkan.",
}

# Genel terim/kısaltma → sade açıklama (bölüm başlıkları, KPI, kısaltmalar).
SADE_TERIM: dict[str, str] = {
    "KVYK": "Kısa Vadeli Yabancı Kaynaklar: 1 yıl içinde ödenecek borçlar.",
    "UVYK": "Uzun Vadeli Yabancı Kaynaklar: 1 yıldan uzun vadeli borçlar.",
    "SMM": "Satılan Malın Maliyeti: sattığın ürünlerin sana olan maliyeti.",
    "DSO": "Ortalama tahsilat süresi: bir satışın parasını ortalama kaç günde tahsil ediyorsun.",
    "DPO": "Ortalama ödeme süresi: bir alışın parasını ortalama kaç günde ödüyorsun.",
    "ÖZKAYNAK": "İşletmenin borçları düşüldükten sonra sana kalan kısmı (senin payın).",
    "DÖNEN VARLIK": "1 yıl içinde nakde dönebilecek varlıklar: kasa, banka, alacak, stok.",
    "REESKONT": "Vadeli alacak/borcun bugünkü değere indirilmesi (faiz ayıklama).",
}


def sade_oran(kod: str) -> str:
    """Oran kodu için sade açıklama; yoksa boş string."""
    return SADE_ORAN.get(kod, "")


def sade_terim(terim: str) -> str:
    """Terim için sade açıklama (büyük/küçük harf duyarsız); yoksa boş string."""
    t = (terim or "").strip()
    return SADE_TERIM.get(t) or SADE_TERIM.get(t.upper(), "")
