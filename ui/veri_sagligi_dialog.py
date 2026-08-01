"""
Veri Sağlığı penceresi — Mikro Ayarları'ndan açılır.

SEKME DEĞİL. Bütün rapor sekmeleri seçili tarih aralığına bağlıyken bu değil: verinin
durumu bir dönem raporu değil, kurulumun hâli. Sekme çubuğunda durunca hem oraya ait
olmayan bir şey gibi görünüyordu hem de kullanıcı ondan dönem raporu bekliyordu.

Pencere BÜTÜN GEÇMİŞİ okur — sabit ve tarih seçicisi yok. Önce son 12 ay taranıyordu;
canlıda 2023'teki 13 bozuk stok kaydı bu yüzden hiç görünmedi, oysa o kayıtlar 2023'ü
kapsayan HER raporu zehirliyor. Bozuk kayıt mevsimsel değil, kalıcıdır: bir kez girilir
ve düzeltilene kadar durur. «Kurulumun hâli» demek, kurulumun tamamına bakmak demek.

Kapsam katalogtan gelir (infra/veritabani.py); yıllar ayrı veritabanlarındaysa hepsi
sırayla okunur.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import build_bilanco
from domain.ortak import to_float as _f
from domain.veri_sagligi import (
    KRITIK,
    Bulgu,
    VeriSagligi,
    build_veri_sagligi,
    veri_sagligi_csv,
)
from infra.config import load_config
from infra.mikro_api import MikroAPIError
from infra.mikro_fetch import (
    fetch_firma_adi,
    fetch_mizan,
    fetch_stok_aykiri_satirlar,
    fetch_stok_ozet,
)
from infra.mukayese_fetch import YilVeritabaniHatasi, donem_satirlari, yil_client
from infra.veritabani import katalog
from ui.bilesenler import csv_kaydet, varsayilan_kayit_yolu
from ui.mikro_settings_dialog import AYARLAR_ADI
from ui.styles import MUTED, NAVY, SURFACE
from ui.veri_sagligi_pdf import export_veri_sagligi_pdf
from ui.worker import RaporWorker

_RENK = {KRITIK: ("#b91c1c", "#fef2f2", "#fecaca")}
_UYARI_RENK = ("#7a5b00", "#fff8e1", "#f0d48a")
_IYI = ("#166534", "#f0fdf4", "#bbf7d0")

# Ekranda en fazla bu kadar kayıt listelenir; kalanı CSV'de. Yüz satırlık bir liste
# pencereyi okunmaz yapar, ilk birkaçı zaten hangi evrak olduğunu gösterir.
_AZAMI_KAYIT = 12


class VeriSagligiDialog(QDialog):
    """Rapor rakamlarını bozan kayıt sorunlarını sade dille gösterir."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Veri Sağlığı")
        self.setObjectName("vsDialog")
        self.setMinimumSize(620, 420)
        self._worker: RaporWorker | None = None
        self._vs: VeriSagligi | None = None
        self._firma = ""
        self._build()
        self._basla()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        baslik = QFrame()
        baslik.setObjectName("vsBaslik")
        bl = QVBoxLayout(baslik)
        bl.setContentsMargins(18, 15, 18, 13)
        bl.setSpacing(4)
        ey = QLabel("VERİ SAĞLIĞI")
        ey.setStyleSheet("color:#8fb8d8; font-size:11px; font-weight:800; "
                         "letter-spacing:1px; background:transparent;")
        bl.addWidget(ey)
        self._ozet = QLabel("Kayıtlar kontrol ediliyor…")
        self._ozet.setWordWrap(True)
        self._ozet.setStyleSheet("color:#ffffff; font-size:16px; font-weight:800; "
                                 "background:transparent;")
        bl.addWidget(self._ozet)
        self._alt = QLabel("Kayıtlar taranıyor…")
        self._alt.setWordWrap(True)
        self._alt.setStyleSheet("color:#c5d8e8; font-size:11px; background:transparent;")
        bl.addWidget(self._alt)
        root.addWidget(baslik)

        kaydir = QScrollArea()
        kaydir.setWidgetResizable(True)
        kaydir.setFrameShape(QFrame.Shape.NoFrame)
        self._govde = QWidget()
        self._gl = QVBoxLayout(self._govde)
        self._gl.setContentsMargins(18, 16, 18, 16)
        self._gl.setSpacing(10)
        self._gl.addStretch(1)
        kaydir.setWidget(self._govde)
        root.addWidget(kaydir, 1)

        # PDF/CSV: bu raporun asıl gideceği yer MALİ MÜŞAVİR. «Şu kayıtları düzeltir
        # misin» diye gönderilecekse ekrandan okuyup elle yazdırmak anlamsız.
        butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._btn_pdf = butonlar.addButton("PDF", QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_csv = butonlar.addButton("CSV", QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_pdf.clicked.connect(self._on_pdf)
        self._btn_csv.clicked.connect(self._on_csv)
        # Sonuç gelmeden dışa aktarılacak bir şey yok.
        self._btn_pdf.setEnabled(False)
        self._btn_csv.setEnabled(False)
        butonlar.rejected.connect(self.reject)
        butonlar.setContentsMargins(18, 0, 18, 14)
        root.addWidget(butonlar)

        self.setStyleSheet(
            f"QDialog#vsDialog {{ background: {SURFACE}; }}"
            f"QFrame#vsBaslik {{ background: {NAVY}; border: none; }}")

    # ------------------------------------------------------------------ çekim
    def _basla(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            self._ozet.setText(f"«{AYARLAR_ADI}» eksik")
            self._not(f"Önce «{AYARLAR_ADI}»'nı doldurun: " + ", ".join(cfg.eksik_alanlar()))
            return
        bit = date.today().isoformat()

        def is_fn(bildir) -> tuple[VeriSagligi, str]:
            client = yil_client(cfg, int(bit[:4]))
            # Kapsam katalogtan: bozuk kayıt hangi yılda olursa olsun bulunmalı.
            # KATALOG OKUNAMAZSA SESSİZCE DARALMAZ, ama bu bir DÜŞEN KAYNAK DEĞİL:
            # `yil_client` katalog boşken bilerek seçili firmayla devam ediyor, yani
            # mizan ve stok yine okunuyor — yalnız tek yıl taranıyor. `okunamayan`a
            # yazılınca sonuç «kontrol tamamlanamadı» görünüyordu; oysa okunan neyse
            # temizdi. Kapsam notu olarak kapsam satırında yazar.
            yillar = [k.ilk_yil for k in katalog(cfg)]
            kapsam_notu = "" if yillar else (
                "Yıl kataloğu kurulamadığı için geçmiş yıllar taranamadı — "
                f"«{AYARLAR_ADI}»'nda firma kodlarını kontrol edin.")
            ilk_yil = min(yillar, default=int(bit[:4]))
            bas = f"{ilk_yil}-01-01"
            # Her kaynak AYRI denenir; düşen kaynak sessizce atlanmaz. Listeye ELLE
            # eklenmiyor: veri `None` kaldığında build_veri_sagligi bunu kendisi görür,
            # böylece eleme tek yerde durur.
            bildir("Muhasebe mizanı okunuyor…")
            bilanco = None
            try:
                bilanco = build_bilanco(fetch_mizan(client, bit), asof=bit)
            except (MikroAPIError, YilVeritabaniHatasi):
                pass
            bildir(f"Stok hareketleri okunuyor ({ilk_yil}–{bit[:4]})…")
            stok_rows = None
            aykiri_rows: list[dict] = []
            try:
                stok_rows = donem_satirlari(cfg, bas, bit, fetch_stok_ozet,
                                            bildir=bildir, ad="stok hareketleri")
                # Aykırı satırların KENDİSİ ayrı çekilir — «düzeltin» demek yetmez,
                # hangi evrak olduğu yazmazsa kullanıcı onu bulamaz. Bu sorgu
                # başarısız olsa da bulgu (sayı + tutar) yine gösterilir.
                if any(_f(r.get("aykiri_adet", r.get("AYKIRI_ADET")))
                       for r in stok_rows):
                    bildir("Hatalı stok kayıtları listeleniyor…")
                    aykiri_rows = donem_satirlari(
                        cfg, bas, bit, fetch_stok_aykiri_satirlar,
                        bildir=bildir, ad="hatalı kayıtlar")
            except (MikroAPIError, YilVeritabaniHatasi):
                pass
            # Firma ünvanı PDF başlığına girer; müşavire giden belge kime ait olduğunu
            # yazmalı. Okunamazsa boş kalır, rapor yine üretilir.
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except (MikroAPIError, YilVeritabaniHatasi):
                    firma = ""
            return build_veri_sagligi(bas=bas, bit=bit, bilanco=bilanco,
                                      stok_rows=stok_rows, aykiri_rows=aykiri_rows,
                                      kapsam_notu=kapsam_notu), firma

        worker = RaporWorker(is_fn, parent=self)
        self._worker = worker
        worker.bitti.connect(self._goster)
        worker.hata.connect(lambda m: self._ozet.setText(f"Kontrol başarısız: {m}"))

        def _bitti() -> None:
            if self._worker is worker:
                self._worker = None

        # Çalışan QThread üzerinde deleteLater() süreci çökertir; finished'a bırakılır.
        worker.finished.connect(_bitti)
        worker.start()

    # ---------------------------------------------------------------- gösterim
    def _dosya_adi(self, uzanti: str) -> str:
        return f"veri_sagligi_{self._vs.bas}_{self._vs.bit}.{uzanti}" if self._vs \
            else f"veri_sagligi.{uzanti}"

    def _on_pdf(self) -> None:
        if self._vs is None:
            return
        yol, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", varsayilan_kayit_yolu(self._dosya_adi("pdf")),
            "PDF (*.pdf)")
        if not yol:
            return
        try:
            export_veri_sagligi_pdf(self._vs, yol, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._not(f"PDF kaydedildi: {Path(yol).name}")

    def _on_csv(self) -> None:
        if self._vs is None:
            return
        yol = csv_kaydet(self, None, self._dosya_adi("csv"), veri_sagligi_csv(self._vs))
        if yol:
            self._not(f"CSV kaydedildi: {Path(yol).name}")

    def _goster(self, sonuc: object) -> None:
        if not (isinstance(sonuc, tuple) and len(sonuc) == 2
                and isinstance(sonuc[0], VeriSagligi)):
            return
        sonuc, self._firma = sonuc
        self._vs = sonuc
        self._btn_pdf.setEnabled(True)
        self._btn_csv.setEnabled(True)
        self._ozet.setText(sonuc.ozet())
        # Hangi kapsamın tarandığı YAZAR: «temiz» sonucu, neye bakıldığı bilinmeden
        # sahte bir güven verir. Cümle domain'den gelir — PDF'le aynısı olsun diye.
        self._alt.setText(
            f"{sonuc.kapsam_satiri()} Rapor rakamlarını bozabilecek sorunlar ve ne "
            "yapılması gerektiği listelenir.")
        for b in sonuc.bulgular:
            self._ekle(_kart(b))
        if sonuc.temiz:
            self._ekle(_iyi_kart())

    def _ekle(self, w: QWidget) -> None:
        self._gl.insertWidget(self._gl.count() - 1, w)

    def _not(self, metin: str) -> None:
        lbl = QLabel(metin)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        self._ekle(lbl)


def _cerceve(yazi: str, arka: str, kenar: str) -> QFrame:
    kart = QFrame()
    kart.setObjectName("vsKart")
    kart.setStyleSheet(
        f"QFrame#vsKart {{ background: {arka}; border: 1px solid {kenar}; "
        f"border-left: 4px solid {yazi}; border-radius: 10px; }}")
    return kart


def _kart(bulgu: Bulgu) -> QFrame:
    yazi, arka, kenar = _RENK.get(bulgu.onem, _UYARI_RENK)
    kart = _cerceve(yazi, arka, kenar)
    lay = QVBoxLayout(kart)
    lay.setContentsMargins(15, 12, 15, 13)
    lay.setSpacing(5)

    ust = QLabel(bulgu.baslik)
    ust.setWordWrap(True)
    ust.setStyleSheet(f"color:{yazi}; font-size:14px; font-weight:800; "
                      "background:transparent; border:none;")
    lay.addWidget(ust)
    if bulgu.olcum:
        ol = QLabel(bulgu.olcum)
        ol.setWordWrap(True)
        ol.setStyleSheet(f"color:{yazi}; font-size:12px; font-weight:700; "
                         "background:transparent; border:none;")
        lay.addWidget(ol)
    for etiket, metin in (("Etkisi", bulgu.etkisi), ("Ne yapmalı", bulgu.ne_yapmali)):
        e = QLabel(f"<b>{etiket}:</b> {metin}")
        e.setTextFormat(Qt.TextFormat.RichText)
        e.setWordWrap(True)
        e.setStyleSheet("color:#334155; font-size:12px; background:transparent; "
                        "border:none;")
        lay.addWidget(e)
    # HANGİ KAYIT olduğu yazmazsa «düzeltin» tavsiyesi işe yaramaz: kullanıcı yüz
    # binlerce satır içinde onu bulamaz. Tarih + evrak no + stok kodu, Mikro'da evrakı
    # açmaya yeter. Liste kırpılıyorsa kaç tanesinin gösterildiği de yazılır.
    if bulgu.kayitlar:
        lay.addWidget(_kayit_listesi(bulgu.kayitlar, yazi))
    return kart


def _kayit_listesi(kayitlar: list[str], yazi: str) -> QWidget:
    kutu = QFrame()
    kutu.setObjectName("vsKayit")
    kutu.setStyleSheet(
        "QFrame#vsKayit { background: rgba(255,255,255,0.72); "
        "border: 1px solid rgba(0,0,0,0.08); border-radius: 7px; }")
    lay = QVBoxLayout(kutu)
    lay.setContentsMargins(11, 8, 11, 9)
    lay.setSpacing(3)
    for satir in kayitlar[:_AZAMI_KAYIT]:
        lbl = QLabel(satir)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet(f"color:{yazi}; font-size:11px; font-family:'Consolas',"
                          "'Courier New',monospace; background:transparent; border:none;")
        lay.addWidget(lbl)
    if len(kayitlar) > _AZAMI_KAYIT:
        kalan = QLabel(f"… ve {len(kayitlar) - _AZAMI_KAYIT} kayıt daha "
                       "(tamamı CSV'de)")
        kalan.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent; "
                            "border:none;")
        lay.addWidget(kalan)
    return kutu


def _iyi_kart() -> QFrame:
    yazi, arka, kenar = _IYI
    kart = _cerceve(yazi, arka, kenar)
    lay = QVBoxLayout(kart)
    lay.setContentsMargins(15, 13, 15, 14)
    lbl = QLabel("Rapor rakamlarını bozabilecek bir kayıt sorunu bulunamadı.")
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color:{yazi}; font-size:13px; font-weight:700; "
                      "background:transparent; border:none;")
    lay.addWidget(lbl)
    return kart
