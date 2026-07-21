"""
Tahmin — yerel Qt görünümü (ileriye dönük nakit tahmini).

İki ihtimali sade Türkçe ile yan yana anlatır:
  • EN KÖTÜ İHTİMAL — bugünkü açık alacak/borçlar; yeni satış varsayılmaz (vade takvimi).
  • NORMAL BEKLENTİ — her ay ortalama satış devam ederse (düzenlenebilir senaryo).
Gerçek durum ikisinin arasında olur. Terimler bilinçli olarak Türkçe ve yalındır
(runway / what-if gibi İngilizce ifadeler kullanılmaz).
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import tl
from domain.runway import RunwayTakvim
from domain.tahmin import Tahmin
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _kpi_card
from ui.gercek_durum_view import NEG, POZ, _card, _renk, _satir_label
from ui.styles import PRIMARY_SOFT

_AY_KISA = ("Oca", "Şub", "Mar", "Nis", "May", "Haz",
            "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")


def _ay_str(yyyymm: str) -> str:
    try:
        y, m = int(yyyymm[:4]), int(yyyymm[5:7])
        return f"{_AY_KISA[m - 1]} {y}"
    except (ValueError, IndexError):
        return yyyymm


def _kotu_ozet(rt: RunwayTakvim) -> str:
    """En kötü ihtimalin tek cümlelik özeti."""
    if rt.tukenme_ay is not None:
        return f"paran <b>{_ay_str(rt.tukenme_ay)}</b> ayında biter (eksiye düşer)"
    return (f"paran {rt.ufuk_ay} ay boyunca yeter "
            f"(en düşük {tl(rt.en_dusuk_nakit)})")


def _normal_ozet(t: Tahmin) -> str:
    """Normal beklentinin tek cümlelik özeti."""
    n = len(t.aylar)
    if t.en_dusuk_nakit < 0:
        return (f"nakit yine de <b>{t.en_dusuk_ay}</b> ayında eksiye düşüyor "
                f"({tl(t.en_dusuk_nakit)})")
    return f"{n} ay sonunda nakitin <b>{tl(t.son_nakit)}</b> olur"


def _iki_ihtimal_karti(rt: RunwayTakvim | None, t: Tahmin) -> QFrame:
    """'Bu iki tablo ne?' sorusunu kökten çözen sade açıklama kartı."""
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(9)

    giris = QLabel("Nakitin nasıl gideceğini <b>iki ihtimalle</b> gösteriyoruz:")
    giris.setTextFormat(Qt.TextFormat.RichText)
    giris.setWordWrap(True)
    giris.setStyleSheet("color: #374151; font-size: 13px; background: transparent;")
    v.addWidget(giris)

    def _satir(renk: str, bg: str, kenar: str, etiket: str, aciklama: str, ozet: str) -> QFrame:
        # Object-name ile kapsanır: aksi halde QSS 'QFrame' kuralı QLabel'lara da
        # (QLabel, QFrame'den türer) yansıyıp "iç içe çerçeveler" görünürdü.
        f = QFrame()
        f.setObjectName("ihtimalBlok")
        f.setStyleSheet(
            "QFrame#ihtimalBlok { background: %s; border: none; "
            "border-left: 3px solid %s; border-radius: 8px; }" % (bg, kenar)
        )
        fl = QVBoxLayout(f)
        fl.setContentsMargins(14, 11, 14, 11)
        fl.setSpacing(3)
        ust = QLabel(f"<span style='color:{renk};'>●</span> <b>{etiket}</b> — {aciklama}")
        ust.setTextFormat(Qt.TextFormat.RichText)
        ust.setWordWrap(True)
        ust.setStyleSheet(f"color: {renk}; font-size: 13px; background: transparent; border: none;")
        fl.addWidget(ust)
        alt = QLabel(f"→ {ozet}")
        alt.setTextFormat(Qt.TextFormat.RichText)
        alt.setWordWrap(True)
        alt.setStyleSheet(
            "color: #374151; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        fl.addWidget(alt)
        return f

    if rt is not None and rt.aylar:
        v.addWidget(_satir(
            NEG, "#fdf0f0", "#e79a9a", "En kötü ihtimal",
            "bugün elindeki alacak/borçlarla, <u>hiç yeni satış olmazsa</u>",
            _kotu_ozet(rt)))
    v.addWidget(_satir(
        POZ, "#eef7f1", "#9cc9ac", "Normal beklenti",
        "her ay ortalama satışın <u>devam ederse</u>",
        _normal_ozet(t)))

    kapanis = QLabel(
        "Gerçek durum çoğu zaman bu ikisinin <b>arasında</b> olur. "
        "Kötü ihtimale hazırlıklı ol; normalde bundan iyi gidersin."
    )
    kapanis.setTextFormat(Qt.TextFormat.RichText)
    kapanis.setWordWrap(True)
    kapanis.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
    v.addWidget(kapanis)

    if rt is not None and rt.gider_eksik:
        uy = QLabel(
            "⚠ Maaş / gider / kredi ödemeleri Mikro'dan tam okunamadı; "
            "«en kötü ihtimal» gerçekte olduğundan iyimser görünebilir."
        )
        uy.setWordWrap(True)
        uy.setStyleSheet("color: #8a5a00; font-size: 11.5px; font-weight: 600; background: transparent;")
        v.addWidget(uy)

    return _card("NAKİT NE OLUR? — İKİ İHTİMAL", inner)


def _kotu_tablo(rt: RunwayTakvim) -> QFrame:
    """En kötü ihtimal: ay-ay girecek − çıkacak → kalan nakit."""
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(7)
    g.setColumnStretch(0, 1)
    for c, bs in ((1, "Girecek"), (2, "Çıkacak"), (3, "Aylık Fark"), (4, "Kalan Nakit")):
        g.addWidget(_satir_label(bs, renk=MUTED, boyut=11, bold=True, sag=True), 0, c)
    for i, a in enumerate(rt.aylar, start=1):
        g.addWidget(_satir_label(_ay_str(a.ay), bold=True), i, 0)
        g.addWidget(_satir_label(tl(a.giren) if a.giren > 0.005 else "—", sag=True,
                                 renk=POZ if a.giren > 0.005 else FAINT), i, 1)
        g.addWidget(_satir_label(tl(a.cikan) if a.cikan > 0.005 else "—", sag=True,
                                 renk=NEG if a.cikan > 0.005 else FAINT), i, 2)
        g.addWidget(_satir_label(("+" if a.net >= 0 else "") + tl(a.net), sag=True,
                                 renk=_renk(a.net)), i, 3)
        g.addWidget(_satir_label(tl(a.nakit), sag=True, bold=True, renk=_renk(a.nakit)), i, 4)
    kredi_s = f" + kredi taksidi {tl(rt.aylik_kredi)}" if rt.aylik_kredi > 0.005 else ""
    gider_s = f" + düzenli gider {tl(rt.aylik_gider)}" if rt.aylik_gider > 0.005 else ""
    not_lbl = _satir_label(
        f"Çıkacak = satıcılara açık borçlar (vadesine göre){gider_s}{kredi_s}. "
        "Girecek = müşterilerden açık alacaklar (vadesine göre). Vadesi geçmiş birikim tek "
        "aya yığılmaz, 3 aya yayılır. Bu tablo yeni satış saymaz — bu yüzden «Girecek» "
        "birkaç ay sonra biter; gerçek durum bundan iyi olur (bkz. «normal beklenti»).",
        renk=FAINT, boyut=11)
    not_lbl.setWordWrap(True)
    g.addWidget(not_lbl, len(rt.aylar) + 1, 0, 1, 5)
    return _card("① EN KÖTÜ İHTİMAL  ·  ay ay nakit (yeni satış yok)", inner)


def _tablo_panel(t: Tahmin) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(6)
    g.setColumnStretch(0, 1)

    for c, b in ((0, "Ay"), (1, "Girecek (satış)"), (2, "Çıkacak (mal + gider)"),
                 (3, "Aylık Fark"), (4, "Kalan Nakit")):
        g.addWidget(_satir_label(b, renk=MUTED, boyut=11, bold=True,
                                 sag=(c != 0)), 0, c)
    r = 1
    for a in t.aylar:
        cikis = a.ciro - a.net_kar  # mal maliyeti + aylık sabit gider
        g.addWidget(_satir_label(_ay_str(a.ay) if len(a.ay) >= 7 else a.ay,
                                 renk="#374151"), r, 0)
        g.addWidget(_satir_label(tl(a.ciro), sag=True, renk=POZ), r, 1)
        g.addWidget(_satir_label(tl(cikis), sag=True, renk=NEG), r, 2)
        g.addWidget(_satir_label(("+" if a.net_kar >= 0 else "") + tl(a.net_kar),
                                 sag=True, renk=_renk(a.net_kar)), r, 3)
        g.addWidget(_satir_label(tl(a.nakit), sag=True, bold=True, renk=_renk(a.nakit)), r, 4)
        r += 1
    not_lbl = _satir_label(
        "Çıkacak = satılan malın maliyeti + aylık sabit gider (yeni mal alımı bunun içinde). "
        "Aylık Fark = Girecek − Çıkacak. Kalan Nakit = önceki ay + aylık fark.",
        renk=FAINT, boyut=11)
    not_lbl.setWordWrap(True)
    g.addWidget(not_lbl, r, 0, 1, 5)
    return _card("② NORMAL BEKLENTİ  ·  ay ay tahmin (satış devam eder)", inner)


class _TahminChart(QWidget):
    """Aylık ciro (çubuk) + nakit (çizgi) grafiği — QPainter."""

    def __init__(self, t: Tahmin, parent=None) -> None:
        super().__init__(parent)
        self._aylar = t.aylar
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        sol, sag, ust, alt = 8, 8, 14, 26
        cw, ch = w - sol - sag, h - ust - alt
        if not self._aylar or cw <= 0 or ch <= 0:
            p.setPen(QPen(QColor(FAINT)))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Tahmin yok")
            p.end()
            return
        ciro = [a.ciro for a in self._aylar]
        nakit = [a.nakit for a in self._aylar]
        min_v = min(min(ciro, default=0.0), min(nakit, default=0.0), 0.0)
        max_v = max(max(ciro, default=0.0), max(nakit, default=0.0), 0.0)
        span = (max_v - min_v) or 1.0
        n = len(self._aylar)
        grup_w = cw / n
        bar_w = min(22.0, grup_w * 0.5)

        def y_of(v):
            return ust + ch * ((max_v - v) / span)

        p.setPen(QPen(QColor("#cbd5e1"), 1, Qt.PenStyle.DashLine))
        zy = y_of(0.0)
        p.drawLine(int(sol), int(zy), int(sol + cw), int(zy))
        # ciro çubukları
        for i, c in enumerate(ciro):
            cx = sol + grup_w * i + grup_w / 2
            vy = y_of(c)
            p.fillRect(QRectF(cx - bar_w / 2, min(vy, zy), bar_w, max(1.0, abs(vy - zy))),
                       QColor("#bfdbfe"))
        # nakit çizgisi
        p.setPen(QPen(QColor(ACCENT), 2))
        pts = []
        for i, nk in enumerate(nakit):
            cx = sol + grup_w * i + grup_w / 2
            pts.append((cx, y_of(nk)))
        for i in range(1, len(pts)):
            p.drawLine(int(pts[i - 1][0]), int(pts[i - 1][1]), int(pts[i][0]), int(pts[i][1]))
        p.setPen(QPen(QColor(MUTED)))
        p.setFont(QFont("Segoe UI", 7))
        for i, a in enumerate(self._aylar):
            ay_kisa = a.ay[2:] if len(a.ay) >= 7 else a.ay
            p.drawText(QRectF(sol + grup_w * i, h - alt + 4, grup_w, alt - 6),
                       Qt.AlignmentFlag.AlignCenter, ay_kisa)
        p.end()


def _grafik_panel(t: Tahmin) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    lej = QLabel(
        f"<span style='color:#99f6e4;'>■</span> Aylık ciro &nbsp;&nbsp;"
        f"<span style='color:{ACCENT};'>▬</span> Nakit (birikimli)"
    )
    lej.setStyleSheet("font-size: 11px; background: transparent;")
    lej.setTextFormat(Qt.TextFormat.RichText)
    v.addWidget(lej)
    v.addWidget(_TahminChart(t))
    return _card("CİRO VE NAKİT GRAFİĞİ  ·  normal beklenti", inner)


def _bolum_basligi(metin: str, renk: str) -> QLabel:
    lbl = QLabel(metin)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {renk}; font-size: 12px; font-weight: 800; letter-spacing: 0.3px; "
        "background: transparent; margin-top: 6px;")
    return lbl


def build_tahmin_widget(
    t: Tahmin, firma: str = "", runway: RunwayTakvim | None = None,
) -> QWidget:
    """Bir Tahmin'den görünüm üretir; runway (en kötü ihtimal) verilirse ikisini birlikte gösterir."""
    content = QWidget()
    content.setObjectName("tahminContent")
    content.setStyleSheet("QWidget#tahminContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    var_runway = runway is not None and runway.aylar

    # 0) "Bu iki tablo ne?" — sade açıklama kartı (en tepede)
    root.addWidget(_iki_ihtimal_karti(runway, t))

    # 1) En kötü ihtimal tablosu (vade takvimi)
    if var_runway:
        root.addWidget(_bolum_basligi(
            "① EN KÖTÜ İHTİMAL — hiç yeni satış olmazsa", NEG))
        root.addWidget(_kotu_tablo(runway))

    # 2) Normal beklenti (düzenlenebilir senaryo)
    root.addWidget(_bolum_basligi(
        "② NORMAL BEKLENTİ — her ay ortalama satış devam ederse", POZ))

    v = t.varsayim
    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    ilk = t.aylar[0].ay if t.aylar else ""
    son = t.aylar[-1].ay if t.aylar else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>{ilk} → {son} ({len(t.aylar)} ay)"
        f"{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Varsayım: {v.ozet()}. "
        f"Soldaki panelden rakamları değiştirip «Hesapla»ya basabilirsin.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, v.baslangic_ay, kaynak="canli"))

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card(f"TOPLAM CİRO ({len(t.aylar)} AY)", tl(t.toplam_ciro), PRIMARY_SOFT, ACCENT))
    nk_bg, nk_vr = ("#e8f6ee", POZ) if t.toplam_net >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("TOPLAM NET KÂR", tl(t.toplam_net), nk_bg, nk_vr))
    sn_bg, sn_vr = ("#e8f6ee", POZ) if t.son_nakit >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("DÖNEM SONU NAKİT", tl(t.son_nakit), sn_bg, sn_vr))
    ed_bg, ed_vr = ("#fdecec", NEG) if t.en_dusuk_nakit < 0 else ("#fff7ed", "#b45309")
    kpi.addWidget(_kpi_card(f"EN DÜŞÜK NAKİT ({t.en_dusuk_ay})", tl(t.en_dusuk_nakit), ed_bg, ed_vr))
    root.addLayout(kpi)

    if t.en_dusuk_nakit < 0:
        uyari = QLabel(
            f"⚠ <b>Normal gidişte bile nakit {t.en_dusuk_ay} ayında eksiye düşüyor</b> "
            f"({tl(t.en_dusuk_nakit)}). Büyüme, kâr oranı veya gideri gözden geçir ya da "
            "kredi/finansman planla."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdecec; border: 1px solid #f0b4b4; border-radius: 8px; "
            "color: #8a1c1c; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)

    root.addWidget(_grafik_panel(t))
    root.addWidget(_tablo_panel(t))
    root.addStretch(1)
    return content
