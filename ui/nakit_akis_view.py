"""
Nakit Akış — yerel Qt görünümü.

Banka + kasa fiili hareketlerinden nakit akış tablosu: açılış → girişler → çıkışlar → kapanış,
kategori kırılımları (tahsilat, satıcı ödemesi, kredi, vergi…), kredi özeti ve aylık trend.
Kart/satır yardımcıları diğer sekmelerle paylaşılır.
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
from domain.nakit_akis import NakitAkis
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _kpi_card
from ui.gercek_durum_view import NEG, POZ, _card, _cizgi, _renk, _satir_label
from ui.styles import PRIMARY_SOFT
from ui.tahsilat_alacak_view import _oran_bar


def _ozet_panel(na: NakitAkis) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    g.setColumnStretch(0, 1)

    def satir(r, ad, deger, *, bold=False, renk="#374151"):
        g.addWidget(_satir_label(ad, bold=bold), r, 0)
        g.addWidget(_satir_label(deger, bold=bold, renk=renk, sag=True), r, 1)

    satir(0, "Açılış Nakit", tl(na.acilis_nakit), bold=True)
    satir(1, "Toplam Giriş (+)", tl(na.toplam_giris), renk=POZ)
    satir(2, "Toplam Çıkış (−)", tl(-na.toplam_cikis), renk=NEG)
    satir(3, "Net Nakit Akışı", tl(na.net_akis), bold=True, renk=_renk(na.net_akis))
    g.addWidget(_cizgi(), 4, 0, 1, 2)
    satir(5, "Kapanış Nakit", tl(na.kapanis_nakit), bold=True, renk=_renk(na.kapanis_nakit))
    if abs(na.mutabakat_farki) > max(1000.0, na.kapanis_nakit * 0.01):
        not_lbl = _satir_label(
            f"Mutabakat: açılış + net akış = {tl(na.kapanis_hesaplanan)}; gerçek kapanışla "
            f"{tl(na.mutabakat_farki)} fark (kur farkı / iç transfer / kapsam dışı hareket).",
            renk="#b45309", boyut=10)
        not_lbl.setWordWrap(True)
        g.addWidget(not_lbl, 6, 0, 1, 2)
    return _card("NAKİT AKIŞ ÖZETİ", inner)


def _kategori_panel(baslik: str, kategori: dict, toplam: float, renk: str,
                    diger_kirilim: list | None = None, diger_etiket: str = "Diğer") -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(9)
    g.setColumnStretch(1, 1)

    if not kategori:
        g.addWidget(_satir_label("Hareket yok.", renk=FAINT), 0, 0)
        return _card(baslik, inner)

    enb = max(kategori.values(), default=0.0) or 1.0
    r = 0
    for ad, tutar in kategori.items():
        g.addWidget(_satir_label(ad, renk="#374151"), r, 0)
        g.addWidget(_oran_bar(tutar / enb, renk), r, 1)
        g.addWidget(_satir_label(tl(tutar), sag=True, bold=True, renk=renk), r, 2)
        r += 1
        # "Diğer" satırının altına karşı-taraf kodu kırılımını döker (saklı kalmasın)
        if ad == diger_etiket and diger_kirilim:
            for prefix, t in diger_kirilim:
                g.addWidget(_satir_label(f"    ◦ {prefix or '?'} hesabı", renk=FAINT, boyut=11), r, 0)
                g.addWidget(_satir_label(tl(t), renk=FAINT, boyut=11, sag=True), r, 2)
                r += 1
    g.addWidget(_cizgi(), r, 0, 1, 3)
    r += 1
    g.addWidget(_satir_label("Toplam", bold=True), r, 0)
    g.addWidget(_satir_label(tl(toplam), sag=True, bold=True), r, 2)
    return _card(baslik, inner)


def _kredi_panel(na: NakitAkis) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    g.setColumnStretch(0, 1)

    def satir(r, ad, deger, *, bold=False, renk="#374151"):
        g.addWidget(_satir_label(ad, bold=bold), r, 0)
        g.addWidget(_satir_label(deger, bold=bold, renk=renk, sag=True), r, 1)

    satir(0, "Kredi Kullanımı (giriş)", tl(na.kredi_kullanim), renk=POZ)
    satir(1, "Kredi Ödemesi (çıkış)", tl(-na.kredi_odeme), renk=NEG)
    satir(2, "Net Kredi", tl(na.kredi_net), bold=True, renk=_renk(na.kredi_net))
    aciklama = (
        "Dönemde net borçlanma (kullanım > ödeme)." if na.kredi_net > 0.005 else
        "Dönemde net kredi geri ödemesi (borç azalıyor)." if na.kredi_net < -0.005 else
        "Dönemde kredi hareketi dengede / yok."
    )
    not_lbl = _satir_label(aciklama, renk=FAINT, boyut=11)
    not_lbl.setWordWrap(True)
    g.addWidget(not_lbl, 3, 0, 1, 2)
    return _card("KREDİ ÖZETİ", inner)


class _AylikChart(QWidget):
    """Aylık giriş/çıkış/net çubuk grafiği (QPainter, ek bağımlılık yok)."""

    def __init__(self, na: NakitAkis, parent=None) -> None:
        super().__init__(parent)
        self._aylar = na.aylik
        self.setMinimumHeight(200)
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
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Trend için veri yok")
            p.end()
            return
        seriler = [(a.giris, a.cikis, a.net) for a in self._aylar]
        min_v = min((min(g, c, n) for g, c, n in seriler), default=0.0)
        max_v = max((max(g, c, n) for g, c, n in seriler), default=0.0)
        min_v, max_v = min(min_v, 0.0), max(max_v, 0.0)
        span = (max_v - min_v) or 1.0
        n = len(self._aylar)
        grup_w = cw / n
        bar_w = min(16.0, grup_w / 4.2)
        renkler = (QColor("#15803d"), QColor("#b91c1c"), QColor(ACCENT))  # giriş/çıkış/net

        def y_of(v):
            return ust + ch * ((max_v - v) / span)

        p.setPen(QPen(QColor("#cbd5e1"), 1, Qt.PenStyle.DashLine))
        zy = y_of(0.0)
        p.drawLine(int(sol), int(zy), int(sol + cw), int(zy))
        p.setFont(QFont("Segoe UI", 7))
        for i, a in enumerate(self._aylar):
            cx = sol + grup_w * i + grup_w / 2
            for j, v in enumerate((a.giris, a.cikis, a.net)):
                bx = cx + (j - 1) * (bar_w + 2) - bar_w / 2
                vy = y_of(v)
                top = min(vy, zy)
                p.fillRect(QRectF(bx, top, bar_w, max(1.0, abs(vy - zy))), renkler[j])
            p.setPen(QPen(QColor(MUTED)))
            ay_kisa = a.ay[2:] if len(a.ay) >= 7 else a.ay
            p.drawText(QRectF(sol + grup_w * i, h - alt + 4, grup_w, alt - 6),
                       Qt.AlignmentFlag.AlignCenter, ay_kisa)
        p.end()


def _trend_panel(na: NakitAkis) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    lej = QLabel(
        f"<span style='color:#15803d;'>■</span> Giriş &nbsp;&nbsp;"
        f"<span style='color:#b91c1c;'>■</span> Çıkış &nbsp;&nbsp;"
        f"<span style='color:{ACCENT};'>■</span> Net"
    )
    lej.setStyleSheet("font-size: 11px; background: transparent;")
    lej.setTextFormat(Qt.TextFormat.RichText)
    v.addWidget(lej)
    v.addWidget(_AylikChart(na))
    return _card("AYLIK NAKİT AKIŞ TRENDİ", inner)


def build_nakit_akis_widget(na: NakitAkis, firma: str = "") -> QWidget:
    """Bir NakitAkis'ten QScrollArea içine konacak yerel görünüm üretir."""
    content = QWidget()
    content.setObjectName("naContent")
    content.setStyleSheet("QWidget#naContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>NAKİT AKIŞ &nbsp;·&nbsp; "
        f"{na.bas} → {na.bit} dönemi{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Banka ve kasadan fiilen geçen para — "
        f"karşı tarafına göre kategorize (tahsilat, satıcı ödemesi, kredi, vergi…). "
        f"Banka↔banka/kasa iç transferleri hariç.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    root.addWidget(head)

    if na.hareket_sayisi == 0:
        uyari = QLabel(
            "⚠ <b>Bu dönemde banka/kasa hareketi bulunamadı.</b> Mikro'da veri olan dönemi seçin; "
            "«Mikro Ayarları»'ndaki çalışma yılı ile dönem tarihleri uyumlu olmalı."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdf3e0; border: 1px solid #f0d090; border-radius: 8px; "
            "color: #8a5a00; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card("TOPLAM GİRİŞ", tl(na.toplam_giris), "#e8f6ee", POZ))
    kpi.addWidget(_kpi_card("TOPLAM ÇIKIŞ", tl(na.toplam_cikis), "#fdecec", NEG))
    nk_bg, nk_vr = ("#e8f6ee", POZ) if na.net_akis >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("NET NAKİT AKIŞI", tl(na.net_akis), nk_bg, nk_vr))
    kp_bg, kp_vr = (PRIMARY_SOFT, ACCENT) if na.kapanis_nakit >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("KAPANIŞ NAKİT", tl(na.kapanis_nakit), kp_bg, kp_vr))
    root.addLayout(kpi)

    row1 = QHBoxLayout()
    row1.setSpacing(20)
    row1.addWidget(_kategori_panel("GİRİŞLER", na.giris_kategori, na.toplam_giris, POZ,
                                   na.diger_giris_kirilim, "Diğer girişler"), 1)
    row1.addWidget(_kategori_panel("ÇIKIŞLAR", na.cikis_kategori, na.toplam_cikis, NEG,
                                   na.diger_cikis_kirilim, "Diğer çıkışlar"), 1)
    root.addLayout(row1)

    row2 = QHBoxLayout()
    row2.setSpacing(20)
    row2.addWidget(_ozet_panel(na), 1)
    row2.addWidget(_kredi_panel(na), 1)
    root.addLayout(row2)

    root.addWidget(_trend_panel(na))
    root.addStretch(1)
    return content
