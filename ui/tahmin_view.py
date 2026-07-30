"""
Tahmin — yerel Qt görünümü (ileriye dönük nakit tahmini).

İki ihtimali sade Türkçe ile anlatır — ÖNCE BEKLENEN, sonra kötü:
  • NORMAL BEKLENTİ — her ay ortalama satış devam ederse (düzenlenebilir senaryo).
  • EN KÖTÜ İHTİMAL — bugünkü açık alacak/borçlar; yeni satış varsayılmaz (vade takvimi).

Sıra bilinçli: kullanıcı önce işin normal seyrini görür, kötü ihtimal onun altında bir
kontrol olarak durur. Tersi, raporu felaket senaryosuyla açmak demekti.

Terimler bilinçli olarak Türkçe ve yalındır (runway / what-if gibi İngilizce ifadeler
kullanılmaz).
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import tl
from domain.ortak import tl0
from domain.runway import RunwayTakvim
from domain.tahmin import Tahmin
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _fit_height, _kpi_card
from ui.gercek_durum_view import NEG, POZ, _agac, _c, _card, _ic, _renk, _tsatir
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
    """
    Normal beklentinin tek cümlelik özeti — ÖNCE SONUÇ.

    Eskiden dip varsa yalnız dip yazılıyordu ve 12 aylık projeksiyonun nereye vardığı
    hiç söylenmiyordu. Kullanıcının ifadesiyle: «tamam 8'de düşüyor ama bana ne 8'den,
    sonunu söyle». Sonuç önce gelir, dip onun niteleyicisidir.
    """
    n = len(t.aylar)
    son = f"{n} ay sonunda nakitin <b>{tl(t.son_nakit)}</b> olur"
    if t.en_dusuk_nakit >= 0:
        return son
    return (f"{son} — ama arada <b>{t.eksi_ay_sayisi} ay</b> eksiye düşüyor "
            f"(en düşük {_ay_str(t.en_dusuk_ay)}: {tl(t.en_dusuk_nakit)})")


def _nakit_uyarisi(t: Tahmin) -> tuple[str, bool]:
    """
    Nakit uyarısı — (metin, ağır mı). Uyarı yoksa metin boş.

    İKİ DURUM AYRI. «Bir ay eksiye düşüp toparlamak» ile «eksiyle bitirmek» aynı şey
    değil; kullanıcının yapacağı iş de aynı değil. Eskiden ikisine de aynı kırmızı
    şeritle «büyüme, kâr oranı veya gideri gözden geçir» deniyordu — 12 ayı +6,2
    milyonla kapatan bir projeksiyonda ilk aydaki 112 binlik dip için verilecek tavsiye
    bu değil. Dibin sebebi kart ödemesiyse o da söylenir; sebebi bilinmeyen uyarı
    kullanıcıya iş vermez (kural 3b).
    """
    if t.en_dusuk_nakit >= 0:
        return "", False
    dip = f"{_ay_str(t.en_dusuk_ay)} ayında {tl(t.en_dusuk_nakit)}"
    if t.kalici_eksi:
        return (f"⚠ <b>Normal gidişte bile nakit eksiye düşüyor ve dönemi eksi "
                f"kapatıyor</b> ({len(t.aylar)} ay sonunda {tl(t.son_nakit)}; en düşük "
                f"{dip}). Büyüme, kâr oranı veya gideri gözden geçir ya da "
                "kredi/finansman planla.", True)
    sebep = ""
    ay = t.dip_ayi
    if t.dip_sebebi_kart and ay is not None:
        sebep = (f" Sebebi o ay ödenen kredi kartı borcu ({tl(ay.kart_borcu_odeme)}); "
                 "ödeme oranını düşürmek dibi kaldırır ama finansman maliyeti doğurur.")
    return (f"⚠ <b>Nakit {t.eksi_ay_sayisi} ay eksiye düşüyor</b> (en düşük {dip}), "
            f"sonra toparlıyor: {len(t.aylar)} ay sonunda {tl(t.son_nakit)}."
            f"{sebep} O ay için köprü finansman gerekebilir.", False)


def _iki_ihtimal_karti(rt: RunwayTakvim | None, t: Tahmin,
                       nakit_olculdu: bool = True) -> QFrame:
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

    v.addWidget(_satir(
        POZ, "#eef7f1", "#9cc9ac", "Normal beklenti",
        "her ay ortalama satışın <u>devam ederse</u>",
        _normal_ozet(t) if nakit_olculdu
        else "başlangıç nakdi ölçülemediği için nakit seviyesi hesaplanamıyor — "
             "soldaki «Bugünkü nakit» alanına yazın"))
    if rt is not None and rt.aylar:
        v.addWidget(_satir(
            NEG, "#fdf0f0", "#e79a9a", "En kötü ihtimal",
            "bugün elindeki alacak/borçlarla, <u>hiç yeni satış olmazsa</u>",
            _kotu_ozet(rt)))

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
    t = _agac(6, [(1, 108), (2, 118), (3, 108), (4, 118), (5, 120)])
    _tsatir(t, [_c(""), _c("Girecek", renk=MUTED, kalin=True, sag=True),
                _c("İşletme / borç", renk=MUTED, kalin=True, sag=True),
                _c("Kart borcu", renk=MUTED, kalin=True, sag=True),
                _c("Aylık Fark", renk=MUTED, kalin=True, sag=True),
                _c("Kalan Nakit", renk=MUTED, kalin=True, sag=True)])
    for a in rt.aylar:
        diger_cikan = a.cikan - a.kart_borcu_odeme
        _tsatir(t, [_c(_ay_str(a.ay), kalin=True),
                    _c(tl(a.giren) if a.giren > 0.005 else "—",
                       renk=POZ if a.giren > 0.005 else FAINT, sag=True),
                    _c(tl(diger_cikan) if diger_cikan > 0.005 else "—",
                       renk=NEG if diger_cikan > 0.005 else FAINT, sag=True),
                    _c(tl(a.kart_borcu_odeme) if a.kart_borcu_odeme > 0.005 else "—",
                       renk="#b45309" if a.kart_borcu_odeme > 0.005 else FAINT, sag=True),
                    _c(("+" if a.net >= 0 else "") + tl(a.net), renk=_renk(a.net), sag=True),
                    _c(tl(a.nakit), renk=_renk(a.nakit), kalin=True, sag=True)])
    _fit_height(t)

    kredi_s = f" + kredi taksidi {tl(rt.aylik_kredi)}" if rt.aylik_kredi > 0.005 else ""
    gider_s = f" + düzenli gider {tl(rt.aylik_gider)}" if rt.aylik_gider > 0.005 else ""
    kart_s = " + açık kredi kartı borcu ödeme planı" if rt.aylik_kart_borcu > 0.005 else ""
    notlar = [(
        f"İşletme / borç = satıcılara açık borçlar (vadesine göre){gider_s}{kredi_s}{kart_s}. "
        "Kart borcu sütunu mevcut açık kart borcu için senaryo ödemesini ayrıca gösterir. "
        "Girecek = müşterilerden açık alacaklar (vadesine göre). Vadesi geçmiş birikim tek "
        "aya yığılmaz, 3 aya yayılır. Bu tablo yeni satış saymaz — bu yüzden «Girecek» "
        "birkaç ay sonra biter; gerçek durum bundan iyi olur (bkz. «normal beklenti»).", FAINT)]
    return _card("② EN KÖTÜ İHTİMAL  ·  ay ay nakit (yeni satış yok)", _ic(t, notlar))


def _tablo_panel(t: Tahmin) -> QFrame:
    tr = _agac(6, [(1, 108), (2, 118), (3, 108), (4, 118), (5, 120)])
    _tsatir(tr, [_c(""), _c("Girecek", renk=MUTED, kalin=True, sag=True),
                 _c("İşletme çıkışı", renk=MUTED, kalin=True, sag=True),
                 _c("Kart borcu", renk=MUTED, kalin=True, sag=True),
                 _c("Aylık Fark", renk=MUTED, kalin=True, sag=True),
                 _c("Kalan Nakit", renk=MUTED, kalin=True, sag=True)])
    for a in t.aylar:
        cikis = a.ciro - a.net_kar  # mal maliyeti + aylık sabit gider
        _tsatir(tr, [_c(_ay_str(a.ay) if len(a.ay) >= 7 else a.ay),
                     _c(tl(a.ciro), renk=POZ, sag=True),
                     _c(tl(cikis), renk=NEG, sag=True),
                     _c(tl(a.kart_borcu_odeme) if a.kart_borcu_odeme > 0.005 else "—",
                        renk="#b45309" if a.kart_borcu_odeme > 0.005 else FAINT, sag=True),
                     _c(("+" if a.net_nakit >= 0 else "") + tl(a.net_nakit),
                        renk=_renk(a.net_nakit), sag=True),
                     _c(tl(a.nakit), renk=_renk(a.nakit), kalin=True, sag=True)])
    _fit_height(tr)

    notlar = [(
        "İşletme çıkışı = satılan malın maliyeti + aylık sabit gider (yeni mal alımı bunun içinde). "
        "Kart borcu, bugünkü açık kart bakiyesinin ayrı nakit ödemesidir; kârı değil nakdi etkiler. "
        "Aylık Fark = Girecek − İşletme çıkışı − Kart borcu. Kalan Nakit = önceki ay + aylık fark.", FAINT)]
    return _card("① NORMAL BEKLENTİ  ·  ay ay tahmin (satış devam eder)", _ic(tr, notlar))


# Çubuk rengi TEK yerde: efsane ile çubuk farklı renkteydi (efsane teal, çubuk mavi).
_CUBUK_RENK = "#bfdbfe"


def dip_isareti(nakit: list[float]) -> tuple[int, str]:
    """
    Grafikte işaretlenecek en düşük nakit noktası: (indeks, etiket).

    Yazı «2026-08'de nakit eksiye düşüyor (−111.974)» derken grafikte çizgi yalnız
    yukarı gidiyor gibi duruyordu. Sebep ölçek: dip −111.974, tavan 6,24 milyon, yani
    düşüş grafiğin %1,8'i kadar — gözle görülmüyor. Ölçeği bozup düşüşü abartmak yerine
    rakam noktanın yanına yazılıyor; grafikle yazı aynı şeyi söylüyor.
    """
    if not nakit:
        return 0, ""
    i = min(range(len(nakit)), key=lambda k: nakit[k])
    return i, f"en düşük {tl0(nakit[i])}"


class _TahminChart(QWidget):
    """
    Aylık tutar (çubuk) + kümülatif nakit (çizgi) grafiği — QPainter.

    Veri dışarıdan (ay, çubuk, çizgi) üçlüleri olarak gelir; böylece AYNI grafik hem
    normal beklenti (ciro) hem en kötü ihtimal (girecek) için kullanılabiliyor.
    Kullanıcı «grafiği her iki ihtimale de koy» dedi — haklıydı, kötü ihtimalin gidişatı
    tablodan okunmak zorunda kalıyordu.
    """

    def __init__(self, aylar: list[tuple[str, float, float]], parent=None) -> None:
        super().__init__(parent)
        self._aylar = aylar
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
        ciro = [satir[1] for satir in self._aylar]
        nakit = [satir[2] for satir in self._aylar]
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
                       QColor(_CUBUK_RENK))
        # nakit çizgisi — EKSİYE DÜŞEN PARÇA KIRMIZI.
        pts = []
        for i, nk in enumerate(nakit):
            cx = sol + grup_w * i + grup_w / 2
            pts.append((cx, y_of(nk)))
        for i in range(1, len(pts)):
            eksi = nakit[i] < 0 or nakit[i - 1] < 0
            p.setPen(QPen(QColor(NEG if eksi else ACCENT), 2))
            p.drawLine(int(pts[i - 1][0]), int(pts[i - 1][1]), int(pts[i][0]), int(pts[i][1]))

        # EN DÜŞÜK NOKTA İŞARETLENİR. Yazı «2026-08'de nakit eksiye düşüyor» derken
        # grafikte çizgi yalnız yukarı gidiyor gibi duruyordu: canlıda dip −111.974 TL
        # ama ölçek 6,36 milyon, yani düşüş grafiğin %1,8'i kadar — gözle görünmüyor.
        # Rakamı çizmek, ölçeği bozmadan yazıyla grafiği aynı şeyi söyletir.
        dip_i, etiket = dip_isareti(nakit)
        dip_v = nakit[dip_i]
        dx, dy = pts[dip_i]
        renk = QColor(NEG if dip_v < 0 else ACCENT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(renk)
        p.drawEllipse(QRectF(dx - 4, dy - 4, 8, 8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(renk))
        p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        gen = 118.0
        ex = min(max(sol, dx - gen / 2), sol + cw - gen)
        # Dip zaten alttaysa etiketi üste al, taşmasın.
        ey = dy + 6 if dy < ust + ch / 2 else dy - 20
        p.drawText(QRectF(ex, ey, gen, 14),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, etiket)

        p.setPen(QPen(QColor(MUTED)))
        p.setFont(QFont("Segoe UI", 7))
        for i, (ay, *_) in enumerate(self._aylar):
            ay_kisa = ay[2:] if len(ay) >= 7 else ay
            p.drawText(QRectF(sol + grup_w * i, h - alt + 4, grup_w, alt - 6),
                       Qt.AlignmentFlag.AlignCenter, ay_kisa)
        p.end()


def _grafik_panel(aylar: list[tuple[str, float, float]], *,
                  baslik: str, cubuk_ad: str) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    lej = QLabel(
        f"<span style='color:{_CUBUK_RENK};'>■</span> {cubuk_ad} &nbsp;&nbsp;"
        f"<span style='color:{ACCENT};'>▬</span> Nakit (birikimli)"
    )
    lej.setStyleSheet("font-size: 11px; background: transparent;")
    lej.setTextFormat(Qt.TextFormat.RichText)
    v.addWidget(lej)
    v.addWidget(_TahminChart(aylar))
    return _card(baslik, inner)


def _bolum_basligi(metin: str, renk: str) -> QLabel:
    lbl = QLabel(metin)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {renk}; font-size: 12px; font-weight: 800; letter-spacing: 0.3px; "
        "background: transparent; margin-top: 6px;")
    return lbl


def _nakit_kaynak_uyarisi(metin: str) -> QLabel:
    """Başlangıç nakdi beklenen kaynaktan gelmedi — amber, çünkü rakam kullanılabilir."""
    uy = QLabel(f"⚠ <b>Başlangıç nakdi:</b> {metin}")
    uy.setTextFormat(Qt.TextFormat.RichText)
    uy.setWordWrap(True)
    uy.setStyleSheet(
        "QLabel { background: #fdf3e0; border: 1px solid #f0d4a0; "
        "border-left: 3px solid #b45309; border-radius: 8px; color: #7a4e0e; "
        "padding: 10px 13px; font-size: 12px; }")
    return uy


def build_tahmin_widget(
    t: Tahmin, firma: str = "", runway: RunwayTakvim | None = None,
    nakit_notu: str = "", nakit_olculdu: bool = True,
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
    root.addWidget(_iki_ihtimal_karti(runway, t, nakit_olculdu))

    # Başlangıç nakdi beklenen kaynaktan gelmediyse SEBEBİ rakamın üstünde yazar
    # (kural 2). Projeksiyonun tamamı bu rakama dayanıyor; sessiz 0 en pahalı hata.
    if nakit_notu:
        root.addWidget(_nakit_kaynak_uyarisi(nakit_notu))

    # 1) ÖNCE NORMAL BEKLENTİ. Rapor kötü ihtimalle açılıyordu; işin normal seyrini
    #    görmeden felaket senaryosu okumak yanlış sırayla düşündürüyor. Kötü ihtimal
    #    altta, bir kontrol olarak durur.
    root.addWidget(_bolum_basligi(
        "① NORMAL BEKLENTİ — her ay ortalama satış devam ederse", POZ))

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
    # KART KARTI YALNIZ BORÇ VARSA. Kredi kartı kullanmayan firmada bu kutu her koşuda
    # sıfır gösteriyordu; kurulum bağımlı bir kalemi herkese göstermek kural 6'ya aykırı.
    if v.kart_borcu_acik > 0.005:
        faiz = (f" · finansman maliyeti: {tl(t.toplam_kart_finansman)}"
                if t.toplam_kart_finansman > 0.005 else "")
        kpi.addWidget(_kpi_card(
            "AÇIK KREDİ KARTI BORCU", tl(v.kart_borcu_acik), "#fff7ed", "#b45309",
            alt=f"{len(t.aylar)} ayda ödeme: {tl(t.toplam_kart_borcu_odeme)}{faiz}",
        ))
    if nakit_olculdu:
        sn_bg, sn_vr = ("#e8f6ee", POZ) if t.son_nakit >= 0 else ("#fdecec", NEG)
        kpi.addWidget(_kpi_card("DÖNEM SONU NAKİT", tl(t.son_nakit), sn_bg, sn_vr))
        ed_bg, ed_vr = ("#fdecec", NEG) if t.en_dusuk_nakit < 0 else ("#fff7ed", "#b45309")
        kpi.addWidget(_kpi_card(f"EN DÜŞÜK NAKİT ({_ay_str(t.en_dusuk_ay)})",
                                tl(t.en_dusuk_nakit), ed_bg, ed_vr))
    else:
        # Başlangıç nakdi ÖLÇÜLEMEDİ. Nakit seviyesi = başlangıç + akış olduğu için bu
        # iki rakam bilinmeyen kadar kaymış olur; kesin görünen bir tutar basmak kural 2
        # ihlali. Akış kartları (ciro, net kâr) gerçekten hesaplanıyor, onlar kalır.
        for baslik in ("DÖNEM SONU NAKİT", "EN DÜŞÜK NAKİT"):
            kpi.addWidget(_kpi_card(
                baslik, "—", "#f1f5f9", MUTED,
                alt="başlangıç nakdi ölçülemedi — soldaki «Bugünkü nakit»i yazın"))
    root.addLayout(kpi)

    uyari_metni, uyari_agir = _nakit_uyarisi(t) if nakit_olculdu else ("", False)
    if uyari_metni:
        uyari = QLabel(uyari_metni)
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        bg, kenar, yazi = (("#fdecec", "#f0b4b4", "#8a1c1c") if uyari_agir
                           else ("#fdf3e0", "#f0d090", "#8a5a00"))
        uyari.setStyleSheet(
            f"QLabel {{ background: {bg}; border: 1px solid {kenar}; border-radius: 8px; "
            f"color: {yazi}; padding: 11px 14px; font-size: 12px; }}"
        )
        root.addWidget(uyari)

    root.addWidget(_grafik_panel(
        [(a.ay, a.ciro, a.nakit) for a in t.aylar],
        baslik="CİRO VE NAKİT GRAFİĞİ  ·  normal beklenti",
        cubuk_ad="Aylık ciro"))
    root.addWidget(_tablo_panel(t))

    # 2) En kötü ihtimal — kendi grafiği ve tablosuyla, aynı okuma düzeninde.
    if var_runway:
        root.addWidget(_bolum_basligi(
            "② EN KÖTÜ İHTİMAL — hiç yeni satış olmazsa", NEG))
        root.addWidget(_grafik_panel(
            [(a.ay, a.giren, a.nakit) for a in runway.aylar],
            baslik="GİRECEK VE NAKİT GRAFİĞİ  ·  en kötü ihtimal",
            cubuk_ad="Aylık girecek"))
        root.addWidget(_kotu_tablo(runway))

    root.addStretch(1)
    return content
