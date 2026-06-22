"""
Kural tabanlı yönetim tavsiyeleri.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from analyzer import MonthlyAnalysisReport, format_tl
from operational_analyzer import (
    HARICI_MAAS_ORAN_ESIK,
    KARGO_BRUT_KAR_ESIK,
    MAAS_MIZAN_FARK_ESIK,
    SGK_BRUT_ORAN_MAX,
    SGK_BRUT_ORAN_MIN,
)
from plan_mutabakat import MUTABAKAT_ORAN_ESIK, MUTABAKAT_TUTAR_ESIK

DUSUK_MARJ_ESIK = 10.0
YUKSEK_CIRO_ESIK = 50000.0
SADECE_ALIS_ESIK = 100000.0
YUKSEK_TASIYICI_KARGO_ESIK = 50000.0
GIDER_YOGUNLASMA_ORAN = 0.25
NET_KAR_KOTULESME_ESIK = 0.30
GIDER_ARTIS_ESIK = 0.25


@dataclass
class Recommendation:
    kategori: str
    oncelik: str
    baslik: str
    aciklama: str
    ilgili_hesaplar: list[str] = field(default_factory=list)


_ONCELIK_SIRA = {"yüksek": 0, "orta": 1, "düşük": 2}


def _add(
    items: list[Recommendation],
    kategori: str,
    oncelik: str,
    baslik: str,
    aciklama: str,
    hesaplar: list[str] | None = None,
) -> None:
    items.append(
        Recommendation(
            kategori=kategori,
            oncelik=oncelik,
            baslik=baslik,
            aciklama=aciklama,
            ilgili_hesaplar=hesaplar or [],
        )
    )


def build_recommendations(report: MonthlyAnalysisReport) -> list[Recommendation]:
    """Rapor verilerine göre eylem odaklı tavsiyeler üretir."""
    from risk_analyzer import build_risk_recommendations

    recs: list[Recommendation] = list(build_risk_recommendations(report))
    pl = report.aylik_pl
    ia = pl.isletme
    cfo = report.cfo_uyarilari

    if pl.aylik_net_kar < 0:
        _add(
            recs,
            "Genel",
            "yüksek",
            "Aylık faaliyet zararı",
            f"Seçilen ay net zarar {format_tl(abs(pl.aylik_net_kar))}. "
            f"Gelir ve gider kalemleri acilen gözden geçirilmeli.",
        )

    if report.ay_karsilastirma:
        k = report.ay_karsilastirma
        if abs(k.net_kar_onceki) > 1:
            net_degisim = (k.net_kar - k.net_kar_onceki) / abs(k.net_kar_onceki)
            if net_degisim <= -NET_KAR_KOTULESME_ESIK:
                _add(
                    recs,
                    "Trend",
                    "yüksek",
                    "Net kâr önceki aya göre belirgin düştü",
                    f"Net kâr {format_tl(k.net_kar_onceki)} → {format_tl(k.net_kar)} "
                    f"(%{abs(net_degisim) * 100:.0f} kötüleşme).",
                )
        if k.gider_onceki > 1:
            gider_artis = (k.gider - k.gider_onceki) / k.gider_onceki
            if gider_artis >= GIDER_ARTIS_ESIK:
                _add(
                    recs,
                    "Trend",
                    "orta",
                    "Operasyonel gider önceki aya göre arttı",
                    f"Gider {format_tl(k.gider_onceki)} → {format_tl(k.gider)} "
                    f"(+%{gider_artis * 100:.0f}).",
                )

    if report.plan_mutabakat:
        pm = report.plan_mutabakat
        if pm.tahsilat_plan_acik > 0 or pm.tahsil_edilemeyen > 0:
            fark = abs(pm.tahsilat_fark)
            base = max(pm.tahsilat_plan_acik, pm.tahsil_edilemeyen, 1.0)
            if fark >= MUTABAKAT_TUTAR_ESIK or fark / base >= MUTABAKAT_ORAN_ESIK:
                _add(
                    recs,
                    "Plan",
                    "orta",
                    "Tahsilat planı ile yaşlandırma farklı",
                    f"Plan anlık bakiye {format_tl(pm.tahsilat_plan_acik)}, "
                    f"yaşlandırma {format_tl(pm.tahsil_edilemeyen)} "
                    f"(fark {format_tl(fark)}). Kaynaklar farklı anlam taşır.",
                )
        if pm.odeme_plan_acik > 0 or pm.odenmeyen > 0:
            fark = abs(pm.odeme_fark)
            base = max(pm.odeme_plan_acik, pm.odenmeyen, 1.0)
            if fark >= MUTABAKAT_TUTAR_ESIK or fark / base >= MUTABAKAT_ORAN_ESIK:
                _add(
                    recs,
                    "Plan",
                    "orta",
                    "Ödeme planı ile yaşlandırma farklı",
                    f"Plan anlık bakiye {format_tl(pm.odeme_plan_acik)}, "
                    f"yaşlandırma {format_tl(pm.odenmeyen)} "
                    f"(fark {format_tl(fark)}).",
                )

    for kalem in pl.muavin_gider_kalemleri[:8]:
        if pl.toplam_operasyonel_gider <= 0:
            break
        oran = kalem.tutar / pl.toplam_operasyonel_gider
        if oran >= GIDER_YOGUNLASMA_ORAN:
            _add(
                recs,
                "Gider",
                "orta",
                f"Gider yoğunlaşması: {kalem.hesap_adi[:40]}",
                f"{kalem.hesap_kodu} toplam giderin %{oran * 100:.1f}'ini oluşturuyor "
                f"({format_tl(kalem.tutar)}).",
                [kalem.hesap_kodu],
            )

    if report.yaslandirma.toplam_tahsil_edilemeyen > 0:
        _add(
            recs,
            "Tahsilat",
            "yüksek",
            "Tahsil edilemeyen satışlar",
            f"Toplam {format_tl(report.yaslandirma.toplam_tahsil_edilemeyen)} "
            f"bankaya yansımamış satış faturası var; tahsilat takibi önceliklendirilmeli.",
        )

    if report.yaslandirma.toplam_odenmeyen > 0:
        _add(
            recs,
            "Ödeme",
            "orta",
            "Ödenmeyen alış faturaları",
            f"Toplam {format_tl(report.yaslandirma.toplam_odenmeyen)} ödenmemiş alış; "
            f"nakit planlaması yapılmalı.",
        )

    if report.eslesme.aciklanamayan_giderler:
        _add(
            recs,
            "Veri",
            "yüksek",
            "Kayıt dışı banka çıkışları",
            f"{len(report.eslesme.aciklanamayan_giderler)} çıkış muavin veya faturada "
            f"karşılık bulamadı; eşleşme skoru %{report.eslesme.eslesme_skoru_pct:.1f}.",
        )

    if cfo.nakit_donusum_hizi_pct < 50 and cfo.nakit_donusum_hizi_pct > 0:
        _add(
            recs,
            "Nakit",
            "orta",
            "Düşük nakit dönüşüm hızı",
            f"Faturalı satışların yalnızca %{cfo.nakit_donusum_hizi_pct:.1f}'i "
            f"banka tahsilatına dönüşmüş.",
        )

    if cfo.sirket_omru_ay is not None and cfo.sirket_omru_ay < 3:
        if cfo.runway_modu == "zarar":
            runway_aciklama = (
                f"Mevcut nakit ile yaklaşık {cfo.sirket_omru_ay:.1f} ay sürdürülebilir "
                f"(zarar modu: nakit / aylık net zarar)."
            )
        else:
            runway_aciklama = (
                f"Mevcut nakit ile yaklaşık {cfo.sirket_omru_ay:.1f} ay gider karşılanabilir "
                f"(kâr modu: nakit / aylık gider)."
            )
        _add(
            recs,
            "Likidite",
            "yüksek",
            "Kısa nakit ömrü (runway)",
            runway_aciklama,
        )

    tp = report.tahsilat_plan
    op = report.tediye_plan
    if tp and tp.vadesi_gecen > 100000:
        _add(
            recs,
            "Tahsilat",
            "yüksek",
            "Vadesi geçen tahsilat planı",
            f"Plan dosyasında vadesi geçen tahsilat {format_tl(tp.vadesi_gecen)}; "
            f"acil tahsilat takibi gerekli.",
        )
    if op and op.vadesi_gelmeyen > 500000:
        _add(
            recs,
            "Ödeme",
            "orta",
            "Yaklaşan ödeme yükü",
            f"Ödeme planında vadesi gelmeyen tutar {format_tl(op.vadesi_gelmeyen)}; "
            f"nakit planlaması yapılmalı.",
        )
    if report.vade_net is not None and report.vade_net < 0:
        _add(
            recs,
            "Likidite",
            "yüksek",
            "Negatif vade neti",
            f"Vadesi gelmeyen ödemeler tahsilattan {format_tl(abs(report.vade_net))} "
            f"fazla; likidite baskısı riski.",
        )
    elif report.vade_net is not None and report.vade_net > 0:
        _add(
            recs,
            "Likidite",
            "düşük",
            "Pozitif vade neti",
            f"Vadesi gelmeyen tahsilat ödemelerden {format_tl(report.vade_net)} fazla.",
        )

    fk = report.fatura_kar
    if fk:
        for kalem in fk.en_dusuk_marj:
            if kalem.kar_marji_pct >= 0:
                continue
            _add(
                recs,
                "Kar Marjı",
                "yüksek",
                f"Zararlı satış: {kalem.stok_adi[:35]}",
                f"{kalem.label} — marj %{kalem.kar_marji_pct:.1f}.",
                [kalem.stok_kodu],
            )
        for kalem in fk.eslesen_kalemler:
            if 0 <= kalem.kar_marji_pct < DUSUK_MARJ_ESIK and kalem.satis_net_tutar >= YUKSEK_CIRO_ESIK:
                _add(
                    recs,
                    "Kar Marjı",
                    "orta",
                    f"Düşük marjlı yüksek hacim: {kalem.stok_adi[:35]}",
                    f"Marj %{kalem.kar_marji_pct:.1f}, satış {format_tl(kalem.satis_net_tutar)}.",
                    [kalem.stok_kodu],
                )
        if fk.sadece_alis_tutar >= SADECE_ALIS_ESIK:
            _add(
                recs,
                "Kar Marjı",
                "düşük",
                "Satılmayan stok birikimi",
                f"{fk.sadece_alis_stok_sayisi} kodda yalnızca alış "
                f"({format_tl(fk.sadece_alis_tutar)}).",
            )

    if ia:
        if ia.kargo_gider_mizan > 0 and ia.kargo_fatura_alis > ia.kargo_gider_mizan * 1.5:
            _add(
                recs,
                "Muhasebe",
                "yüksek",
                "Kargo muhasebe dağıtım kontrolü",
                f"Muavin kargo {format_tl(ia.kargo_gider_mizan)}, fatura kargo "
                f"{format_tl(ia.kargo_fatura_alis)}; 730/760/770 dağıtımı kontrol edilmeli.",
            )
        if ia.kargo_tasiyici_ozet:
            toplam = sum(t.tutar for t in ia.kargo_tasiyici_ozet)
            if toplam >= YUKSEK_TASIYICI_KARGO_ESIK:
                _add(
                    recs,
                    "Kargo",
                    "orta",
                    "Yüksek taşıyıcı cari maliyeti",
                    f"Taşıyıcı faturaları toplam {format_tl(toplam)}.",
                )
        if ia.ticari_brut_kar > 0 and ia.kargo_brut_kar_orani >= KARGO_BRUT_KAR_ESIK:
            _add(
                recs,
                "Kargo",
                "orta",
                "Kargo / brüt kâr oranı yüksek",
                f"Kargo gösterge brüt kârın %{ia.kargo_brut_kar_orani * 100:.1f}'i.",
            )
        if ia.toplam_harici_maas_girilen > 0:
            oran = (
                ia.toplam_harici_maas_girilen / ia.toplam_maas_girilen
                if ia.toplam_maas_girilen > 0
                else 0.0
            )
            oncelik = "orta" if oran >= HARICI_MAAS_ORAN_ESIK else "düşük"
            _add(
                recs,
                "İşletme",
                oncelik,
                "Harici maaş ödemesi",
                f"Harici maaş {format_tl(ia.toplam_harici_maas_girilen)} "
                f"(toplam maaşın %{oran * 100:.1f}'i); deftere yansımaz.",
            )
        if ia.brut_ucret_mizan > 0 and ia.toplam_resmi_maas_girilen > 0:
            fark = abs(ia.brut_ucret_mizan - ia.toplam_resmi_maas_girilen)
            if fark >= MAAS_MIZAN_FARK_ESIK:
                _add(
                    recs,
                    "İşletme",
                    "düşük",
                    "Resmi maaş / muavin 770.01 farkı",
                    f"Girilen resmi {format_tl(ia.toplam_resmi_maas_girilen)}, "
                    f"muavin 770.01 {format_tl(ia.brut_ucret_mizan)}.",
                )
        if ia.sgk_primi_mizan > 0 and ia.brut_ucret_mizan > 0:
            sgk_oran = ia.sgk_primi_mizan / ia.brut_ucret_mizan
            if sgk_oran < SGK_BRUT_ORAN_MIN:
                _add(
                    recs,
                    "Muhasebe",
                    "yüksek",
                    "SGK eksik tahakkuk şüphesi",
                    f"SGK/brüt oranı %{sgk_oran * 100:.1f} (min %10 beklenir).",
                )
            elif sgk_oran > SGK_BRUT_ORAN_MAX:
                _add(
                    recs,
                    "İşletme",
                    "düşük",
                    "SGK oranı olağandışı yüksek",
                    f"SGK/brüt oranı %{sgk_oran * 100:.1f}.",
                )

    recs.sort(key=lambda r: (_ONCELIK_SIRA.get(r.oncelik, 9), r.kategori))
    return recs


def build_executive_wrap_up(
    report: MonthlyAnalysisReport,
    recommendations: list[Recommendation] | None = None,
) -> list[str]:
    """Tavsiyelerden kapsamlı son özet maddeleri üretir."""
    recs = recommendations if recommendations is not None else report.recommendations
    pl = report.aylik_pl
    nakit = report.nakit_akis
    lines = [
        f"Analiz ayı: {report.analiz_ayi} ({report.context.donem_metin}).",
        f"Aylık net kâr/zarar: {format_tl(pl.aylik_net_kar)}.",
        f"Dönem sonu nakit: {format_tl(nakit.donem_sonu_net_nakit)}.",
        report.cfo_uyarilari.ozet_metin,
    ]
    if report.fatura_kar:
        fk = report.fatura_kar
        lines.append(
            f"Ticari brüt kâr: {format_tl(fk.toplam_brut_kar)}, marj %{fk.agirlikli_marj_pct:.1f}."
        )
    if report.vade_net is not None:
        lines.append(f"Vade neti (plan): {format_tl(report.vade_net)}.")
    yuksek = [r for r in recs if r.oncelik == "yüksek"]
    if yuksek:
        lines.append("")
        lines.append("Öncelikli aksiyonlar:")
        for rec in yuksek[:5]:
            lines.append(f"• [{rec.kategori}] {rec.aciklama}")
    elif not recs:
        lines.append("Kritik uyarı tespit edilmedi.")
    return lines
