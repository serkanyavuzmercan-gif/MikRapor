"""
Bulgular motoru — ham rapor sayılarını kural-tabanlı, aksiyona dönük yorumlara çevirir.

Amaç: bir işletme sahibi ekrandaki rakamlara bakıp "ee, ne yapayım?" demesin. Motor,
rapor modellerinden (şimdilik GercekDurum) eşik + kıyas kurallarıyla en önemli 1-3 bulguyu
çıkarır; her bulgu bir başlık + açıklama + (varsa) somut öneri taşır.

Saf fonksiyon (Mikro/DB/GUI yok) — kolay test edilir; UI yalnızca sonucu çizer.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.ortak import tl, yuzde

# Eşikler — tek yerde, ayarlanabilir.
MARJ_DUSUK_ESIK = 10.0        # al-sat marjı bu %'in altındaysa "düşük"
STOK_BAGLANMA_ORANI = 0.05    # stoğa bağlanan para satışın bu oranını aşarsa haber
BORC_ALACAK_KAT = 1.5         # borç, alacağın bu katını aşarsa uyarı

# Şiddet → sıralama önceliği (küçük = daha kritik, önce gösterilir).
SIDDET_SIRA = {"kritik": 0, "uyari": 1, "bilgi": 2, "iyi": 3}


@dataclass
class Bulgu:
    """Tek bir yorum: şiddet + başlık + açıklama + (opsiyonel) öneri."""
    siddet: str          # "kritik" | "uyari" | "bilgi" | "iyi"
    baslik: str
    metin: str
    oneri: str = ""


def gercek_durum_bulgulari(gd, *, en_fazla: int = 3) -> list[Bulgu]:
    """Nakit & Kârlılık modelinden en önemli bulguları üretir (en fazla `en_fazla`)."""
    b: list[Bulgu] = []

    # 1) Nakit eriyor mu? (dönem içi net nakit akışı)
    if gd.nakit_net < -0.005:
        b.append(Bulgu(
            "kritik", "Nakit eriyor",
            f"Bu dönemde kasadan/bankadan net {tl(-gd.nakit_net)} çıktı "
            f"(giriş, çıkışı karşılamadı).",
            "Tahsilatı hızlandır, öteleyebileceğin ödemeleri ertele.",
        ))
    elif gd.nakit_net > 0.005:
        b.append(Bulgu(
            "iyi", "Nakit akışı pozitif",
            f"Bu dönemde nakit net +{tl(gd.nakit_net)} arttı.",
        ))

    # 2) İşletme sermayesi negatif mi?
    if gd.net_isletme_sermayesi < -0.005:
        b.append(Bulgu(
            "kritik", "İşletme sermayen negatif",
            f"Nakit + alacak, kısa vadeli borçlarını {tl(-gd.net_isletme_sermayesi)} "
            f"tutarında aşamıyor — kısa vadede nakit sıkışması riski.",
            "Vadeleri dengele; kısa vadeli borcu uzun vadeliye çevirmeyi değerlendir.",
        ))

    # 3) Al-sat marjı düşük mü?
    #    Resmi brüt marj sağlıklıysa fiili marjın düşük görünmesinin sebebi fiyatlama
    #    değil stok değişimidir; "marjın düşük" demek yanlış alarm olur (4. kural anlatır).
    resmi_saglikli = gd.resmi_brut_marj is not None and gd.resmi_brut_marj >= MARJ_DUSUK_ESIK
    if gd.gercek_satis > 0.005 and gd.gercek_brut_marj < MARJ_DUSUK_ESIK and not resmi_saglikli:
        b.append(Bulgu(
            "uyari", "Al-sat marjın düşük",
            f"Satış−alış marjın yalnızca {yuzde(gd.gercek_brut_marj)}. "
            f"Giderleri karşılamakta zorlanabilirsin.",
            "Satış fiyatı/iskonto ve alış maliyetlerini gözden geçir.",
        ))

    # 4) Dönemde para stoğa mı bağlandı? (resmi ile fiili marjı ayıran asıl kalem)
    #    Eskiden "resmi ve fiili marj ayrışıyor, kâr yanıltıcı olabilir" diyordu; bu
    #    normal bir muhasebe farkını usulsüzlük gibi okutuyordu. Asıl haber stok.
    if gd.maliyet_koprusu is not None and gd.gercek_satis > 0.005 \
            and abs(gd.maliyet_koprusu) >= gd.gercek_satis * STOK_BAGLANMA_ORANI:
        if gd.maliyet_koprusu > 0:
            b.append(Bulgu(
                "uyari", "Para stoğa bağlandı",
                f"Aldığın malın {tl(gd.maliyet_koprusu)} tutarındaki kısmı satılmadı, "
                f"stoğa eklendi. Fiili al-sat marjının resmi brüt marjdan düşük "
                f"görünmesinin sebebi bu.",
                "Yavaş dönen kalemleri ayıkla; stok devir hızını Mukayese & Oranlar'dan izle.",
            ))
        else:
            b.append(Bulgu(
                "bilgi", "Stoktan satış yapıldı",
                f"Sattığın malın {tl(-gd.maliyet_koprusu)} tutarındaki kısmı önceki "
                f"dönemlerden geldi; bu dönem o kadar mal almadın.",
                "",
            ))

    # 5) Borç, alacağı belirgin aşıyor mu?
    if gd.borc > 0.005 and gd.borc > gd.alacak * BORC_ALACAK_KAT:
        b.append(Bulgu(
            "uyari", "Borçların alacaklarını aşıyor",
            f"Satıcı borcun {tl(gd.borc)}, müşteri alacağın {tl(gd.alacak)} — "
            f"ödeme yükün tahsilatının üstünde.",
            "Tahsilat takvimini ödeme takvimine göre öne çek.",
        ))

    # 6) Veri eksikse dürüstçe söyle (güven)
    if gd.veri_eksik:
        b.append(Bulgu(
            "bilgi", "Veri kısmi",
            "Dönemde stok hareketi eksik/sınıflandırılamadı — bulgular kısmi olabilir.",
            "Dönem/çalışma yılını ve kayıt tarzını (Ayarlar) kontrol et.",
        ))

    b.sort(key=lambda x: SIDDET_SIRA.get(x.siddet, 9))
    return b[:en_fazla]
