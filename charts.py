"""
Matplotlib grafik üreticileri — ay bazlı mimari.
"""

from __future__ import annotations

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from analyzer import MonthlyAnalysisReport
from metric_labels import metric_kaynak, metric_short
from parse_utils import format_tl
from period_utils import analiz_ayi_label

PALETTE = ["#4fc3f7", "#81c784", "#ffb74d", "#e57373", "#ba68c8"]
FIG_SIZE = (8, 4.5)
FIG_DPI = 110

CHART_INFO: dict[str, tuple[str, str]] = {
    "nakit": ("Nakit Akış Özeti", ""),
    "pl": ("Aylık Kâr/Zarar Köprüsü", "aylik_net_kar"),
    "gider": ("Muavin Gider Kırılımı", "operasyonel_gider"),
    "cari": ("120 / 320 Cari Durumu", "tahsil_edilemeyen"),
    "plan": ("Tahsilat ve Ödeme Planı", "vade_net"),
    "trend": ("Önceki Aya Göre", "aylik_net_kar"),
}

CHART_SUBTITLES: dict[str, str] = {
    "nakit": "Dönem başı, giriş, çıkış ve dönem sonu; banka ekstresi (seçilen ay)",
    "cari": "Dönem sonuna kadar satış/alış faturası − kümülatif banka tahsilat/ödemesi",
}


def chart_display_info(key: str) -> tuple[str, str]:
    """Grafik başlığı ve kaynak açıklaması."""
    title, metric_key = CHART_INFO[key]
    if key in CHART_SUBTITLES:
        return title, CHART_SUBTITLES[key]
    if metric_key:
        return title, metric_kaynak(metric_key)
    return title, ""


def create_figure(figsize=FIG_SIZE, facecolor="#1a1d23") -> Figure:
    return Figure(figsize=figsize, dpi=FIG_DPI, facecolor=facecolor)


def _compact_tl(value: float) -> str:
    av = abs(value)
    if av >= 1_000_000:
        text = f"{av / 1_000_000:.1f}M"
    elif av >= 1_000:
        text = f"{av / 1_000:.0f}K"
    else:
        text = f"{av:.0f}"
    return f"-{text}" if value < 0 else text


def _style_axes(ax) -> None:
    ax.set_facecolor("#252830")
    ax.tick_params(colors="#9aa0a8", labelsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: _compact_tl(v)))
    for spine in ax.spines.values():
        spine.set_color("#5f6368")


def _bar_value_labels(ax, bars, values: list[float], *, horizontal: bool = False) -> None:
    for bar, val in zip(bars, values):
        label = format_tl(val)
        if horizontal:
            x = bar.get_width()
            y = bar.get_y() + bar.get_height() / 2
            ha = "left" if x >= 0 else "right"
            offset = 4 if x >= 0 else -4
            ax.text(
                x + offset, y, label, va="center", ha=ha,
                color="#e8eaed", fontsize=8,
            )
        else:
            h = bar.get_height()
            y = bar.get_y() + h if hasattr(bar, "get_y") and h < 0 else h
            if h < 0:
                y = h
                va = "top"
            else:
                va = "bottom"
            ax.text(
                bar.get_x() + bar.get_width() / 2, y, label,
                ha="center", va=va, color="#e8eaed", fontsize=8,
            )


def chart_nakit_akis(report: MonthlyAnalysisReport) -> Figure:
    nakit = report.nakit_akis
    fig = create_figure()
    ax = fig.add_subplot(111)
    labels = ["Dönem Başı", "Girişler", "Çıkışlar", "Dönem Sonu"]
    values = [
        nakit.donem_basi_mevcut,
        nakit.giris_transfer_haric or nakit.donem_ici_girisler,
        -(nakit.cikis_transfer_haric or nakit.donem_ici_cikislar),
        nakit.donem_sonu_net_nakit,
    ]
    colors = [
        PALETTE[0],
        PALETTE[1],
        PALETTE[3],
        PALETTE[4] if values[3] >= 0 else PALETTE[3],
    ]
    bars = ax.bar(labels, values, color=colors)
    ax.axhline(0, color="#5f6368", linewidth=0.8)
    ax.set_title("Nakit Akış Özeti", color="#e8eaed", fontsize=12, pad=10)
    _style_axes(ax)
    _bar_value_labels(ax, bars, values)
    fig.tight_layout()
    return fig


def chart_kar_zarar_koprusu(report: MonthlyAnalysisReport) -> Figure:
    pl = report.aylik_pl
    fig = create_figure()
    ax = fig.add_subplot(111)
    labels = ["Brüt Kâr", "Operasyonel Gider", "Harici Maaş", "Net Kâr/Zarar"]
    values = [
        pl.brut_kar,
        -pl.toplam_operasyonel_gider,
        -pl.toplam_harici_maas,
        pl.aylik_net_kar,
    ]
    colors = [
        PALETTE[1] if v >= 0 else PALETTE[3] for v in values
    ]
    colors[-1] = PALETTE[0] if pl.aylik_net_kar >= 0 else PALETTE[3]
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values, color=colors)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, color="#e8eaed")
    ax.axvline(0, color="#5f6368", linewidth=0.8)
    ax.set_title("Aylık Kâr/Zarar Köprüsü", color="#e8eaed", fontsize=12, pad=10)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: _compact_tl(v)))
    ax.set_facecolor("#252830")
    ax.tick_params(colors="#9aa0a8", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#5f6368")
    _bar_value_labels(ax, bars, values, horizontal=True)
    fig.tight_layout()
    return fig


def chart_gider_yatay(report: MonthlyAnalysisReport) -> Figure:
    kalemler = report.aylik_pl.muavin_gider_kalemleri[:8]
    fig = create_figure(figsize=(8, max(4.5, len(kalemler) * 0.45 + 1.5)))
    ax = fig.add_subplot(111)
    if not kalemler:
        ax.text(0.5, 0.5, "Gider verisi yok", ha="center", va="center", color="#9aa0a8")
        ax.set_axis_off()
        return fig
    labels = [
        f"{k.hesap_kodu} — {k.hesap_adi[:28]}" if k.hesap_adi else k.hesap_kodu
        for k in kalemler
    ]
    values = [k.tutar for k in kalemler]
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values, color=PALETTE[: len(values)])
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, color="#e8eaed", fontsize=8)
    ax.set_title("Muavin Gider Kırılımı (730/760/770)", color="#e8eaed", fontsize=12, pad=10)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: _compact_tl(v)))
    ax.set_facecolor("#252830")
    ax.tick_params(colors="#9aa0a8", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#5f6368")
    _bar_value_labels(ax, bars, values, horizontal=True)
    fig.tight_layout()
    return fig


def chart_cari_120_320(report: MonthlyAnalysisReport) -> Figure:
    yas = report.yaslandirma
    fig = create_figure()
    ax = fig.add_subplot(111)
    labels = ["Tahsil Edilemeyen\n(120)", "Ödenmeyen\n(320)"]
    values = [yas.toplam_tahsil_edilemeyen, yas.toplam_odenmeyen]
    colors = [PALETTE[1], PALETTE[3]]
    bars = ax.bar(labels, values, color=colors)
    ax.set_title("120 / 320 Cari Durumu", color="#e8eaed", fontsize=12, pad=10)
    _style_axes(ax)
    _bar_value_labels(ax, bars, values)
    fig.tight_layout()
    return fig


def chart_plan_vade(report: MonthlyAnalysisReport) -> Figure:
    fig = create_figure()
    ax = fig.add_subplot(111)
    tp = report.tahsilat_plan
    op = report.tediye_plan
    if not tp and not op:
        ax.text(0.5, 0.5, "Plan verisi yok", ha="center", va="center", color="#9aa0a8")
        ax.set_axis_off()
        return fig

    labels: list[str] = []
    gecen: list[float] = []
    gelmeyen: list[float] = []
    if tp and tp.hesap_sayisi:
        labels.append("Tahsilat (120)")
        gecen.append(tp.vadesi_gecen)
        gelmeyen.append(tp.vadesi_gelmeyen)
    if op and op.hesap_sayisi:
        labels.append("Ödeme (320)")
        gecen.append(op.vadesi_gecen)
        gelmeyen.append(op.vadesi_gelmeyen)

    x = range(len(labels))
    ax.bar(x, gecen, label="Vadesi geçen", color=PALETTE[3])
    ax.bar(x, gelmeyen, bottom=gecen, label="Vadesi gelmeyen", color=PALETTE[1])
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, color="#e8eaed")
    ax.set_title("Tahsilat ve Ödeme Planı", color="#e8eaed", fontsize=12, pad=10)
    _style_axes(ax)
    ax.legend(facecolor="#252830", edgecolor="#5f6368", labelcolor="#e8eaed", fontsize=8)
    fig.tight_layout()
    return fig


def chart_ay_karsilastirma(report: MonthlyAnalysisReport) -> Figure:
    k = report.ay_karsilastirma
    fig = create_figure(figsize=(9, 5))
    ax = fig.add_subplot(111)
    if not k:
        ax.text(0.5, 0.5, "Önceki ay verisi yok", ha="center", va="center", color="#9aa0a8")
        ax.set_axis_off()
        return fig

    labels = ["Net Kâr", "Brüt Kâr", "Gider", "Dönem Sonu Nakit"]
    bu_ay = [k.net_kar, k.brut_kar, k.gider, k.nakit_sonu]
    onceki = [k.net_kar_onceki, k.brut_kar_onceki, k.gider_onceki, k.nakit_sonu_onceki]
    x = range(len(labels))
    width = 0.35
    ax.bar([i - width / 2 for i in x], bu_ay, width, label="Bu Ay", color=PALETTE[0])
    ax.bar([i + width / 2 for i in x], onceki, width, label=analiz_ayi_label(k.onceki_ayi), color=PALETTE[2])
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, color="#e8eaed", fontsize=9)
    onceki_label = analiz_ayi_label(k.onceki_ayi)
    ax.set_title(
        f"Önceki Aya Göre ({onceki_label} vs güncel)",
        color="#e8eaed",
        fontsize=12,
        pad=10,
    )
    ax.axhline(0, color="#5f6368", linewidth=0.8)
    _style_axes(ax)
    ax.legend(facecolor="#252830", edgecolor="#5f6368", labelcolor="#e8eaed", fontsize=8)
    fig.tight_layout()
    return fig


def build_all_charts(report: MonthlyAnalysisReport) -> dict[str, Figure]:
    charts = {
        "nakit": chart_nakit_akis(report),
        "pl": chart_kar_zarar_koprusu(report),
        "gider": chart_gider_yatay(report),
        "cari": chart_cari_120_320(report),
    }
    if report.tahsilat_plan or report.tediye_plan:
        charts["plan"] = chart_plan_vade(report)
    if report.ay_karsilastirma:
        charts["trend"] = chart_ay_karsilastirma(report)
    return charts
