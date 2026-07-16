"""
Nakit & Kârlılık sekmesi — firma bazlı hesaplama kuralları.

Varsayılan profil: irsaliyeli satış, alış faturası, nakit GL, alacak/borç cari.
  satış irsaliye+fatura, alış yalnız fatura, nakit GL, alacak/borç cari.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from config import _read_config_data, save_config_data


@dataclass
class GercekDurumAyarlar:
    """Mikro kayıt tarzına göre Nakit & Kârlılık motoru kuralları."""

    satis_bazi: str = "sevk"           # sevk | fatura
    alis_bazi: str = "fatura"          # fatura | irsaliye | ikisi
    nakit_kaynak: str = "gl"           # gl | cari | otomatik
    alacak_borc_kaynak: str = "cari"   # cari | gl
    banka_kredi_haric: bool = True     # 300.* ve ban_hesap_tip=1 nakitten hariç
    musteri_avans_goster: bool = True  # müşteri avansı satırını göster

    @classmethod
    def varsayilan(cls) -> GercekDurumAyarlar:
        return cls()

    @classmethod
    def from_dict(cls, data: dict | None) -> GercekDurumAyarlar:
        if not data:
            return cls.varsayilan()
        return cls(
            satis_bazi=str(data.get("satis_bazi", "sevk") or "sevk"),
            alis_bazi=str(data.get("alis_bazi", "fatura") or "fatura"),
            nakit_kaynak=str(data.get("nakit_kaynak", "gl") or "gl"),
            alacak_borc_kaynak=str(data.get("alacak_borc_kaynak", "cari") or "cari"),
            banka_kredi_haric=bool(data.get("banka_kredi_haric", True)),
            musteri_avans_goster=bool(data.get("musteri_avans_goster", True)),
        )

    def ozet(self) -> str:
        """Durum çubuğu / başlık için kısa özet."""
        sat = "İrsaliye+Fatura" if self.satis_bazi == "sevk" else "Yalnız Fatura"
        alis = {"fatura": "Alış Fatura", "irsaliye": "Alış İrsaliye", "ikisi": "Alış İrs.+Fat."}
        nak = {"gl": "Nakit GL", "cari": "Nakit Cari", "otomatik": "Nakit Otomatik"}
        ab = "Cari" if self.alacak_borc_kaynak == "cari" else "GL"
        return f"Satış: {sat} · {alis.get(self.alis_bazi, self.alis_bazi)} · {nak.get(self.nakit_kaynak, self.nakit_kaynak)} · Alacak/Borç: {ab}"


def load_gercek_durum_ayarlar() -> GercekDurumAyarlar:
    data = _read_config_data()
    return GercekDurumAyarlar.from_dict(data.get("gercek_durum"))


def save_gercek_durum_ayarlar(ayarlar: GercekDurumAyarlar) -> None:
    data = _read_config_data()
    data["gercek_durum"] = asdict(ayarlar)
    save_config_data(data)


# UI etiketleri (dialog)
SATIS_BAZI_SECENEKLERI = [
    ("sevk", "İrsaliye + Fatura (sevk ağırlıklı firmalar)"),
    ("fatura", "Yalnız Fatura (fatura ile stok çıkışı)"),
]
ALIS_BAZI_SECENEKLERI = [
    ("fatura", "Yalnız Alış Faturası (önerilen — çift sayımı önler)"),
    ("irsaliye", "Yalnız Alış İrsaliyesi (depo girişi)"),
    ("ikisi", "İrsaliye + Fatura (dikkat: aynı mal iki kez sayılabilir)"),
]
NAKIT_KAYNAK_SECENEKLERI = [
    ("gl", "GL mizan (102/100/108) — muhasebe bakiyesi"),
    ("cari", "Cari hareket — Mikro banka modülü birikimi"),
    ("otomatik", "Otomatik — cari çok şişikse GL kullan"),
]
ALACAK_BORC_SECENEKLERI = [
    ("cari", "Cari hareket (Mikro cari listesi)"),
    ("gl", "GL mizan (120 / 320)"),
]
