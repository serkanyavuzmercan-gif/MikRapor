"""Tahmin sekmesi — geçmiş trendden önerilen, düzenlenebilir varsayımlarla projeksiyon."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from domain.gelir_tablosu import build_gelir_tablosu
from domain.gercek_durum import build_gercek_durum
from domain.kredi import (
    KART_BORCU_VARSAYILAN_ODEME_YUZDE,
    kredi_karti_borclarini_derle,
    kredi_karti_odeme_takvimi,
    kredi_takvimi_ay,
    taksitleri_derle,
)
from domain.mizan_bilanco import tl
from domain.nakit_akis import build_nakit_akis, nakit_bakiye, nakit_gl_ozetten
from domain.runway import RunwayTakvim, _ay_ekle, runway_takvim_kur
from domain.tahmin import (
    Tahmin,
    TahminVarsayim,
    build_tahmin,
    ogrenme_penceresi_bas,
    oner_varsayim,
    tahmin_csv,
)
from domain.tahsilat_alacak import build_tahsilat_alacak
from infra.config import MikroConfig
from infra.mikro_api import MikroAPIError
from infra.mikro_fetch import (
    fetch_acik_kalemler,
    fetch_bakiye_ozet,
    fetch_cari_bakiye,
    fetch_cari_vade_gun,
    fetch_gelir_tablosu,
    fetch_kredi_anapara,
    fetch_kredi_karti_borclari,
    fetch_kredi_taksitleri,
    fetch_nakit_akis_hareket,
    fetch_nakit_delta,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from infra.mukayese_fetch import (
    YilVeritabaniHatasi,
    donem_satirlari,
    donem_toplami,
    yil_client,
)
from ui.bilesenler import hos_geldin, para_spin, varsayilan_kayit_yolu, yuzde_spin
from ui.empty_state import DEFAULT_HERO_ASSET, HERO_SOLUK_OPACITY, build_soluk_arka_plan
from ui.rapor_tab import RaporTab, firma_getir
from ui.tahmin_pdf import export_tahmin_pdf
from ui.tahmin_view import build_tahmin_widget
from ui.worker import IsFonksiyonu
from ui.yukleniyor import YukleniyorEkrani

_PANEL_GENISLIK = 240
_RAIL_GENISLIK = 36


class TahminTab(RaporTab):
    """Geçmiş trendden otomatik önerip kullanıcının düzenlediği ileriye dönük projeksiyon."""

    EMOJI = "🔮"
    BASLIK = "Tahmin & Projeksiyon"
    ACIKLAMA = (
        "«Geçmişten Doldur» kâr oranı ve aylık ciroyu <b>son 12 ayın ortalamasından</b> önerir "
        "(tek çeyrek yanıltmasın diye).<br>"
        "Kaç ay ileriye bakılacağı sol paneldeki <b>Kaç ay ileri</b> ile ayarlanır; «Hesapla» ile tahmin üretilir.<br>"
        "<span style='color:#9aa0a8;'>Önce «Geçmişten Doldur», sonra rakamları değiştir.</span>")
    GETIR_ETIKET = "Geçmişten Doldur"
    BASLARKEN = "Geçmiş veri çekiliyor (satış, marj, nakit, gider)…"
    DONEM_ETIKET = "Geçmiş veri dönemi:"
    TARIH_GENISLIK = 120
    PDF_DESTEK = True
    HERO_ASSET = "empty-tahmin.png"

    _t: Tahmin | None = None
    _runway: RunwayTakvim | None = None

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _build(self) -> None:
        """Sol senaryo paneli + sağda empty/rapor içeriği."""
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sp_nakit = para_spin()
        self._sp_ciro = para_spin()
        self._sp_gider = para_spin()
        self._sp_kart_borc = para_spin()
        self._sp_kart_borc.setReadOnly(True)
        self._sp_kart_oran = yuzde_spin(0.0, 100.0)
        self._sp_kart_oran.setValue(KART_BORCU_VARSAYILAN_ODEME_YUZDE)
        self._sp_buyume = yuzde_spin(-50.0, 100.0)
        self._sp_marj = yuzde_spin(0.0, 100.0)
        self._sp_ufuk = QSpinBox()
        self._sp_ufuk.setRange(1, 36)
        self._sp_ufuk.setValue(12)
        self._sp_ufuk.setSuffix(" ay")

        for sp in (
            self._sp_nakit, self._sp_ciro, self._sp_gider, self._sp_kart_borc,
            self._sp_buyume, self._sp_marj, self._sp_kart_oran, self._sp_ufuk,
        ):
            sp.setMinimumWidth(0)
            sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            # Rakam değişince sağ taraf bayatlar; hesaplama anlık olduğu için
            # "yükleniyor" göstergesi yanıp söner — bunun yerine tazelik durumu
            # sürekli yazılır (kullanıcı "sağdaki değerler güncel mi?" diye sormasın).
            sp.valueChanged.connect(self._on_varsayim_degisti)

        alanlar = (
            ("Bugünkü nakit", self._sp_nakit),
            ("Aylık ortalama ciro", self._sp_ciro),
            ("Aylık büyüme", self._sp_buyume),
            ("Kâr oranı (brüt marj)", self._sp_marj),
            ("Aylık sabit gider", self._sp_gider),
            ("Mevcut kart borcu (canlı)", self._sp_kart_borc),
            ("Kart borcu aylık ödeme", self._sp_kart_oran),
            ("Kaç ay ileri", self._sp_ufuk),
        )
        self._senaryo = _SenaryoSolPanel(alanlar)
        self._btn_projekte = self._senaryo.btn_projekte
        self._btn_projekte.clicked.connect(self._on_projekte)
        root.addWidget(self._senaryo, 0)

        sag = QWidget()
        sag_lay = QVBoxLayout(sag)
        sag_lay.setContentsMargins(0, 0, 0, 0)
        sag_lay.setSpacing(0)

        self._stack = QStackedWidget()
        hero = (self.HERO_ASSET or "").strip() or DEFAULT_HERO_ASSET
        hero_fit = (self.HERO_FIT or "cover").strip() or "cover"
        self._empty = hos_geldin(
            self.EMOJI,
            self.BASLIK,
            self.ACIKLAMA,
            self.IPUCU,
            on_cta=self._on_getir,
            cta=self.GETIR_ETIKET,
            hero_asset=hero,
            hero_fit=hero_fit,
        )
        self._stack.addWidget(self._empty)

        self._icerik_sayfa = QWidget()
        self._icerik_sayfa.setObjectName("raporIcerikSayfa")
        self._icerik_sayfa.setStyleSheet("QWidget#raporIcerikSayfa { background: transparent; }")
        ic_lay = QGridLayout(self._icerik_sayfa)
        ic_lay.setContentsMargins(0, 0, 0, 0)
        ic_lay.setSpacing(0)
        self._arka = build_soluk_arka_plan(
            opacity=HERO_SOLUK_OPACITY, hero_asset=hero, hero_fit=hero_fit,
        )
        ic_lay.addWidget(self._arka, 0, 0)

        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        vp = self._view.viewport()
        vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        vp.setAutoFillBackground(False)
        vp.setStyleSheet("background: transparent;")
        ic_lay.addWidget(self._view, 0, 0)
        self._view.raise_()

        self._stack.addWidget(self._icerik_sayfa)

        # 2: yükleniyor ara ekranı (RaporTab._calistir bunu bekler)
        self._yukleniyor = YukleniyorEkrani(
            hero_asset=hero, hero_fit=hero_fit, ipucu=self.SURE_IPUCU)
        self._stack.addWidget(self._yukleniyor)

        self._stack.setCurrentIndex(0)
        sag_lay.addWidget(self._stack, stretch=1)
        root.addWidget(sag, 1)

    def _ust_alan(self, layout: QVBoxLayout) -> None:
        """Sol panel `_build` içinde; üst şerit yok."""
        del layout

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        ufuk = self._sp_ufuk.value()

        def is_fn(bildir) -> dict[str, Any]:
            # Veritabanını firma kodu seçer: dönemin bittiği yıl hangi
            # veritabanındaysa oraya bağlanılır (bkz. infra/veritabani.py).
            client = yil_client(cfg, int(bit[:4]))
            # Varsayımlar (kâr oranı, aylık ciro, büyüme) SON 12 AYIN ortalamasından
            # öğrenilir — tek çeyrek seçilse bile temsili olsun (stok dalgalanması
            # marjı tek çeyrekte %49'a çıkarabiliyor; 12 ayda gerçek ~%25'e oturur).
            ogr_bas = ogrenme_penceresi_bas(bas, bit)
            bildir("Geçmiş satış/kâr öğreniliyor (son 12 ay)…")
            # 12 aylık öğrenme penceresi neredeyse hep yıl sınırını aşar; AKIŞ olduğu
            # için her parça kendi veritabanından okunup birleştirilir. BAKİYE bölünmez.
            stok_rows = donem_satirlari(cfg, ogr_bas, bit, fetch_stok_ozet)
            stok_aylik = donem_satirlari(cfg, ogr_bas, bit, fetch_stok_aylik)
            gd = build_gercek_durum(
                stok_rows=stok_rows, stok_aylik=stok_aylik, bas=ogr_bas, bit=bit)
            bildir("Nakit bakiyesi ve hareketleri çekiliyor…")
            kapanis_rows = fetch_cari_bakiye(client, bit)
            # Başlangıç nakit GL'den (Bilanço "Nakit ve Benzerleri" ile birebir).
            # Cari-hareket nakiti döviz kuru yüzünden ~47 kat şişebiliyor (25M gibi
            # hayalet rakamlar) — GL okunamazsa ancak o zaman cari'ye düşülür.
            try:
                gl_nakit: float | None = nakit_gl_ozetten(fetch_bakiye_ozet(client, bit))
            except MikroAPIError:
                gl_nakit = None
            baslangic_nakit = gl_nakit if gl_nakit is not None else nakit_bakiye(kapanis_rows)
            # Kart ekstre/asgari ödeme verisi her Mikro kurulumunda bulunmuyor. Bu yüzden
            # yalnızca canlı açık borcu okuyor, ödeme planını kullanıcı senaryosuna bırakıyoruz.
            try:
                bildir("Açık kredi kartı borçları çekiliyor…")
                kart_borclari = kredi_karti_borclarini_derle(
                    fetch_kredi_karti_borclari(client, bit))
            except MikroAPIError:
                kart_borclari = []
            kart_borcu_acik = sum(k.borc for k in kart_borclari)
            hareket_rows = donem_satirlari(cfg, bas, bit, fetch_nakit_akis_hareket)
            donem_delta = donem_toplami(cfg, bas, bit, fetch_nakit_delta)
            na = build_nakit_akis(hareket_rows, bakiye_kapanis_rows=kapanis_rows,
                                  donem_delta=donem_delta, bas=bas, bit=bit)
            # Aylık gider DOĞRULANMIŞ GL gelir tablosundan (63 faaliyet, 66 finansman) —
            # cari nakit-kategorisi çek/EFT/GL-direkt ödemeleri kaçırıp eksik kaldığından
            # (Nakit Akış'ta düzeltilen kök) sabit gider önerisi VE runway ikisi de buradan
            # beslenir. GL okunamazsa ancak o zaman cari toplam çıkışa düşülür.
            ay_sayisi = max(1, len(na.aylik))
            gt = None
            try:
                bildir("Faaliyet gideri (gelir tablosu) çekiliyor…")
                gt = build_gelir_tablosu(
                    donem_satirlari(cfg, bas, bit, fetch_gelir_tablosu), bas=bas, bit=bit)
            except (MikroAPIError, YilVeritabaniHatasi):
                gt = None
            if gt is not None:
                sabit_gider = -gt.faaliyet_gideri / ay_sayisi          # 63, işaretli negatif → pozitif
                gider_proxy = -(gt.faaliyet_gideri + gt.finansman_gideri) / ay_sayisi
            else:
                sabit_gider = (na.toplam_cikis
                               - na.cikis_kategori.get("Satıcı ödemesi", 0.0)
                               - na.kredi_odeme) / ay_sayisi
                gider_proxy = -sabit_gider

            # Vade-takvimli runway (gerçek açık kalemlerden) — başarısız olsa da tahmin üretilir.
            runway: RunwayTakvim | None = None
            runway_bilesenleri: dict[str, Any] | None = None
            try:
                bildir("Açık alacak/borç vadeleri çekiliyor (runway)…")
                vade_gun_map = fetch_cari_vade_gun(client)
                acik_rows = fetch_acik_kalemler(client, bit, bas, bit)
                ta = build_tahsilat_alacak(acik_rows, vade_gun_map=vade_gun_map, bas=bas, bit=bit)
                # Kredi ayağı: gerçek taksit takvimi (ödenmemiş taksitler) — düz ortalamadan
                # çok daha doğru. Okunamazsa GL 300/303 ortalamasına düşülür.
                try:
                    bildir("Kredi taksit takvimi çekiliyor…")
                    taksitler = taksitleri_derle(fetch_kredi_taksitleri(client, ay_ileri=18))
                except MikroAPIError:
                    taksitler = []
                if taksitler:
                    ilk_ay = _ay_ekle(bit[:7], 1)  # runway 1. projeksiyon ayı
                    kredi_takvimi = kredi_takvimi_ay(taksitler, ilk_ay=ilk_ay)
                    kredi_proxy = None
                else:
                    kredi_takvimi = None
                    kredi_proxy = donem_toplami(cfg, bas, bit, fetch_kredi_anapara) / ay_sayisi
                runway_bilesenleri = {
                    "na": na, "ta": ta, "baslangic_ay": bit[:7], "ufuk_ay": 6,
                    "baslangic_nakit": baslangic_nakit,
                    "aylik_gider": gider_proxy, "aylik_kredi": kredi_proxy or 0.0,
                    "kredi_takvimi": kredi_takvimi,
                }
                runway = runway_takvim_kur(
                    **runway_bilesenleri,
                    kart_borcu_takvimi=kredi_karti_odeme_takvimi(
                        kart_borclari, baslangic_ay=bit[:7],
                        odeme_yuzde=KART_BORCU_VARSAYILAN_ODEME_YUZDE, ufuk_ay=6,
                    ))
            except (MikroAPIError, YilVeritabaniHatasi):
                runway = None
            bildir("Varsayımlar öneriliyor…")
            satis_serisi = [a.satis for a in gd.trend]
            v = oner_varsayim(
                satis_serisi=satis_serisi, brut_marj_yuzde=gd.gercek_brut_marj,
                baslangic_nakit=baslangic_nakit, aylik_sabit_gider=sabit_gider,
                baslangic_ay=bit[:7], kart_borcu_acik=kart_borcu_acik,
                kart_borcu_odeme_yuzde=KART_BORCU_VARSAYILAN_ODEME_YUZDE, ufuk_ay=ufuk,
            )
            return {
                "varsayim": v, "firma": firma_getir(cfg, client), "runway": runway,
                "kart_borclari": kart_borclari, "runway_bilesenleri": runway_bilesenleri,
            }

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        v: TahminVarsayim = sonuc["varsayim"]
        self._firma = sonuc["firma"]
        self._runway = sonuc.get("runway")
        self._kart_borclari = sonuc.get("kart_borclari", [])
        self._runway_bilesenleri = sonuc.get("runway_bilesenleri")
        self._sp_nakit.setValue(v.baslangic_nakit)
        self._sp_ciro.setValue(v.baz_ciro)
        self._sp_buyume.setValue(v.buyume_yuzde)
        self._sp_marj.setValue(v.marj_yuzde)
        self._sp_gider.setValue(v.sabit_gider)
        self._sp_kart_borc.setValue(v.kart_borcu_acik)
        self._sp_kart_oran.setValue(v.kart_borcu_odeme_yuzde)
        self._senaryo.ac()
        self._durum(
            "Geçmişten dolduruldu (son 12 ayın ortalaması) — rakamları düzenleyip "
            "«Hesapla»ya basabilirsin.", "iyi")
        self._on_projekte()

    def _runway_yenile(self, baslangic_ay: str) -> RunwayTakvim | None:
        bilesenler = getattr(self, "_runway_bilesenleri", None)
        if not bilesenler:
            return None
        return runway_takvim_kur(
            **bilesenler,
            kart_borcu_takvimi=kredi_karti_odeme_takvimi(
                getattr(self, "_kart_borclari", []), baslangic_ay=baslangic_ay,
                odeme_yuzde=self._sp_kart_oran.value(), ufuk_ay=6,
            ),
        )

    def _on_varsayim_degisti(self) -> None:
        """Varsayım değişti → sağdaki rapor artık bu rakamları yansıtmıyor."""
        if self._t is not None:
            self._senaryo.set_guncel(False)

    def _on_projekte(self) -> None:
        bit = self._donem.bit_tarih()
        v = TahminVarsayim(
            baslangic_ay=f"{bit.year():04d}-{bit.month():02d}",
            baslangic_nakit=self._sp_nakit.value(),
            baz_ciro=self._sp_ciro.value(),
            buyume_yuzde=self._sp_buyume.value(),
            marj_yuzde=self._sp_marj.value(),
            sabit_gider=self._sp_gider.value(),
            kart_borcu_acik=self._sp_kart_borc.value(),
            kart_borcu_odeme_yuzde=self._sp_kart_oran.value(),
            ufuk_ay=self._sp_ufuk.value(),
        )
        self._t = build_tahmin(v)
        self._runway = self._runway_yenile(v.baslangic_ay)
        self._icerik_koy(build_tahmin_widget(
            self._t, firma=self._firma, runway=getattr(self, "_runway", None)))
        self._senaryo.set_guncel(True)
        if self._chrome is not None:
            self._chrome.set_csv_aktif(True)
            self._chrome.set_pdf_aktif(True)
        self._durum(
            f"Tahmin: {self._sp_ufuk.value()} ay · toplam ciro {tl(self._t.toplam_ciro)} · "
            f"dönem sonu nakit {tl(self._t.son_nakit)}",
            "hata" if self._t.en_dusuk_nakit < 0 else "iyi",
        )

    def _on_pdf(self) -> None:
        if not self._t:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet",
            varsayilan_kayit_yolu(f"{self._slug}_{self._t.varsayim.baslangic_ay}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            export_tahmin_pdf(self._t, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"{self._slug}_{self._t.varsayim.baslangic_ay}.csv" if self._t else f"{self._slug}.csv"

    def _csv_icerik(self) -> str | None:
        return tahmin_csv(self._t) if self._t else None


class _SenaryoSolPanel(QFrame):
    """Sol rail + senaryo gövdesi. Varsayılan açık; dar navy–teal panel."""

    def __init__(self, alanlar: tuple[tuple[str, QWidget], ...]) -> None:
        super().__init__()
        self.setObjectName("tahminSolHost")
        self._acik = True

        host = QHBoxLayout(self)
        host.setContentsMargins(0, 0, 0, 0)
        host.setSpacing(0)

        self._rail = QPushButton("\n".join("SENARYO"))
        self._rail.setObjectName("tahminSolRail")
        self._rail.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rail.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._rail.setFixedWidth(_RAIL_GENISLIK)
        self._rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._rail.setVisible(False)
        self._rail.clicked.connect(self.ac)
        host.addWidget(self._rail)

        self._govde = QFrame()
        self._govde.setObjectName("tahminSolPanel")
        self._govde.setFixedWidth(_PANEL_GENISLIK)
        self._govde.setVisible(True)
        gl = QVBoxLayout(self._govde)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(0)

        # Üst şerit — navy ton
        baslik_wrap = QFrame()
        baslik_wrap.setObjectName("tahminSolBaslikSerit")
        bw = QVBoxLayout(baslik_wrap)
        bw.setContentsMargins(14, 14, 12, 12)
        bw.setSpacing(4)

        baslik_satir = QHBoxLayout()
        baslik_satir.setSpacing(6)
        col = QVBoxLayout()
        col.setSpacing(2)
        eyebrow = QLabel("TAHMİN")
        eyebrow.setObjectName("tahminSolEyebrow")
        col.addWidget(eyebrow)
        baslik = QLabel("Senaryo varsayımları")
        baslik.setObjectName("tahminFormBaslik")
        baslik.setWordWrap(True)
        col.addWidget(baslik)
        baslik_satir.addLayout(col, 1)
        kapat = QPushButton("‹")
        kapat.setObjectName("tahminSolKapat")
        kapat.setCursor(Qt.CursorShape.PointingHandCursor)
        kapat.setFixedSize(26, 26)
        kapat.clicked.connect(self.kapat)
        baslik_satir.addWidget(kapat, 0, Qt.AlignmentFlag.AlignTop)
        bw.addLayout(baslik_satir)
        ipucu = QLabel("Rakamları değiştirip «Hesapla»ya bas.")
        ipucu.setObjectName("tahminSolIpucu")
        ipucu.setWordWrap(True)
        bw.addWidget(ipucu)
        gl.addWidget(baslik_wrap)

        govde_ic = QWidget()
        gi = QVBoxLayout(govde_ic)
        gi.setContentsMargins(14, 12, 14, 14)
        gi.setSpacing(8)

        for etiket, w in alanlar:
            lbl = QLabel(etiket)
            lbl.setObjectName("tahminAlanEtiket")
            gi.addWidget(lbl)
            w.setObjectName("tahminAlanGirdi")
            gi.addWidget(w)

        gi.addStretch(1)

        self.btn_projekte = QPushButton("Hesapla")
        self.btn_projekte.setObjectName("primaryBtn")
        self.btn_projekte.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_projekte.setMinimumHeight(36)
        gi.addWidget(self.btn_projekte)

        # Sağdaki raporun bu rakamlarla mı üretildiğini söyler. Hesaplama anlık
        # olduğundan "yükleniyor" göstergesi yanıp söner ve hiçbir şey anlatmaz;
        # kalıcı tazelik durumu sorunun kendisini ("güncel mi?") cevaplar.
        self.lbl_tazelik = QLabel()
        self.lbl_tazelik.setObjectName("tahminTazelik")
        self.lbl_tazelik.setWordWrap(True)
        self.lbl_tazelik.setVisible(False)
        gi.addWidget(self.lbl_tazelik)
        gl.addWidget(govde_ic, 1)

        host.addWidget(self._govde)

    def set_guncel(self, guncel: bool) -> None:
        """Sağdaki rapor bu varsayımları yansıtıyor mu — panelde kalıcı olarak yazar."""
        if guncel:
            metin, renk = "✓ Sağdaki rapor güncel", "#15803d"
        else:
            metin, renk = "● Rakamlar değişti — «Hesapla»ya bas", "#b45309"
        self.lbl_tazelik.setText(metin)
        self.lbl_tazelik.setStyleSheet(
            f"color: {renk}; font-size: 11px; font-weight: 600; background: transparent;")
        self.lbl_tazelik.setVisible(True)

    def ac(self) -> None:
        if self._acik:
            return
        self._acik = True
        self._govde.setVisible(True)
        self._rail.setVisible(False)

    def kapat(self) -> None:
        if not self._acik:
            return
        self._acik = False
        self._govde.setVisible(False)
        self._rail.setVisible(True)
