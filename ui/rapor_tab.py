"""
Ortak rapor sekmesi iskeleti (RaporTab) + arka plan çalıştırma.

Eski main.py'de her sekme aynı bloğu kopyalıyordu: ayar kontrolü, tarih doğrulama,
"getir" butonu, durum etiketi, boş/karşılama ekranı, kaydırmalı görünüm, CSV kaydetme
ve hata yönetimi. RaporTab bunların hepsini tek yerde toplar; ağ çağrılarını
RaporWorker (QThread) ile ANA THREAD DIŞINDA çalıştırır — arayüz donmaz,
"İptal" ile beklemekten vazgeçilebilir, aşama mesajları durum etiketine akar.

Alt sınıf sözleşmesi:
  - Sınıf sabitleri: EMOJI, BASLIK, ACIKLAMA (karşılama), GETIR_ETIKET,
    TEK_TARIH (bilanço), PDF_DESTEK, DONEM_ETIKET, BASLARKEN (ilk durum mesajı).
  - _is_hazirla(cfg, bas, bit) -> is_fn(bildir):  worker thread'inde çalışacak
    SAF iş (fetch + build; Qt widget'ına DOKUNMAZ), sonucu döndürür.
  - _goster(sonuc): ana thread'de görünümü kurar (self._icerik_koy + self._durum).
  - _csv_dosya_adi() / _csv_icerik(): CSV dışa aktarım.
  - İsteğe bağlı kancalar: _ekstra_kontroller(controls), _ust_alan(layout), _on_pdf().
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from infra.config import MikroConfig, load_config
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import fetch_firma_adi
from ui.bilesenler import csv_kaydet, durum_yaz, hos_geldin
from ui.donem import DonemDurumu, donem_aralik_bagla, donem_tek_bagla
from ui.mikro_settings_dialog import MikroAyarlarDialog
from ui.tarih_secici import TarihSecici
from ui.worker import IsFonksiyonu, RaporWorker


def firma_getir(cfg: MikroConfig, client: MikroClient) -> str:
    """Firma ünvanı: elle girilmişse o; boşsa Mikro'dan. (Worker thread'inde çağrılır.)"""
    firma = (cfg.firma_adi or "").strip()
    if firma:
        return firma
    try:
        return fetch_firma_adi(client)
    except MikroAPIError:
        return ""


class RaporTab(QWidget):
    """Tüm rapor sekmelerinin ortak iskeleti — bkz. modül docstring'i."""

    EMOJI = "📊"
    BASLIK = ""
    ACIKLAMA = ""
    IPUCU = ""                    # karşılama alt notu (boş: varsayılan)
    GETIR_ETIKET = "Getir"
    BASLARKEN = "Veriler çekiliyor…"
    DONEM_ETIKET = "Dönem:"
    TEK_TARIH = False
    TARIH_GENISLIK = 130
    PDF_DESTEK = False

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._worker: RaporWorker | None = None
        self._firma: str = ""
        self._build()

    # ------------------------------------------------------------------ kurulum
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        controls_host = QFrame()
        controls_host.setObjectName("tabToolbar")
        controls = QHBoxLayout(controls_host)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(8)
        controls.addWidget(QLabel(self.DONEM_ETIKET))
        if self.TEK_TARIH:
            self._tarih = TarihSecici(self._donem.bit_tarih(), genislik=140)
            controls.addWidget(self._tarih)
            donem_tek_bagla(self, self._donem, self._tarih)
        else:
            self._bas = TarihSecici(self._donem.bas_tarih(), genislik=self.TARIH_GENISLIK)
            controls.addWidget(self._bas)
            controls.addWidget(QLabel("→"))
            self._bit = TarihSecici(self._donem.bit_tarih(), genislik=self.TARIH_GENISLIK)
            controls.addWidget(self._bit)
            donem_aralik_bagla(self, self._donem, self._bas, self._bit)

        self._ekstra_kontroller(controls)

        self._btn_getir = QPushButton(self.GETIR_ETIKET)
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_iptal = QPushButton("İptal")
        self._btn_iptal.setObjectName("ghostBtn")
        self._btn_iptal.setVisible(False)
        self._btn_iptal.clicked.connect(self._on_iptal)
        controls.addWidget(self._btn_iptal)

        if self.PDF_DESTEK:
            self._btn_pdf = QPushButton("PDF Kaydet")
            self._btn_pdf.setObjectName("ghostBtn")
            self._btn_pdf.setEnabled(False)
            self._btn_pdf.clicked.connect(self._on_pdf)
            controls.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel(self._ilk_mesaj())
        self._status.setObjectName("toolbarHint")
        self._status.setStyleSheet("color: #64748b;")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addWidget(controls_host)

        self._ust_alan(layout)

        self._empty = hos_geldin(self.EMOJI, self.BASLIK, self.ACIKLAMA, self.IPUCU)
        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _ilk_mesaj(self) -> str:
        return f"Dönem seçip «{self.GETIR_ETIKET}»e basın."

    # ------------------------------------------------------- alt sınıf kancaları
    def _ekstra_kontroller(self, controls: QHBoxLayout) -> None:
        """Kontrol çubuğuna ek buton (ör. ⚙ Ayarlar) eklemek için."""

    def _ust_alan(self, layout: QVBoxLayout) -> None:
        """Kontrol çubuğu ile içerik arasına widget (ör. Tahmin formu) eklemek için."""

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        raise NotImplementedError

    def _goster(self, sonuc: Any) -> None:
        raise NotImplementedError

    def _csv_dosya_adi(self) -> str:
        raise NotImplementedError

    def _csv_icerik(self) -> str | None:
        return None

    def _on_pdf(self) -> None:  # PDF_DESTEK=True olan sekme override eder
        raise NotImplementedError

    # --------------------------------------------------------------- yardımcılar
    def _durum(self, mesaj: str, tur: str = "notr") -> None:
        durum_yaz(self._status, mesaj, tur)

    def _icerik_koy(self, widget: QWidget) -> None:
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(widget)

    def _ayarlar_tamam(self) -> MikroConfig | None:
        """Mikro ayarları eksikse kullanıcıya sorar; tamamsa config döner."""
        cfg = load_config()
        if cfg.is_complete():
            return cfg
        cevap = QMessageBox.question(
            self, "Mikro Ayarları Eksik",
            "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
            "Şimdi açmak ister misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap == QMessageBox.StandardButton.Yes:
            MikroAyarlarDialog(self).exec()
        return None

    # ------------------------------------------------------------- çalıştırma
    def _on_getir(self) -> None:
        cfg = self._ayarlar_tamam()
        if cfg is None:
            return
        if self.TEK_TARIH:
            bit = self._tarih.date().toString("yyyy-MM-dd")
            bas = bit
        else:
            if self._bas.date() > self._bit.date():
                QMessageBox.warning(self, "Tarih Hatası", "Başlangıç tarihi bitişten sonra olamaz.")
                return
            bas = self._bas.date().toString("yyyy-MM-dd")
            bit = self._bit.date().toString("yyyy-MM-dd")
        self._calistir(self._is_hazirla(cfg, bas, bit))

    def _calistir(self, is_fn: IsFonksiyonu) -> None:
        """İşi arka plan thread'inde başlatır; UI açık ve iptal edilebilir kalır."""
        if self._worker is not None:  # süren işi bırak (sinyalleri sustur)
            self._worker.iptal_et()
            self._worker = None
        self._btn_getir.setEnabled(False)
        self._btn_iptal.setVisible(True)
        self._durum(self.BASLARKEN)

        worker = RaporWorker(is_fn, self)
        worker.ilerleme.connect(self._on_ilerleme)
        worker.bitti.connect(self._on_bitti)
        worker.hata.connect(self._on_hata)
        worker.finished.connect(lambda w=worker: self._on_worker_bitti(w))
        self._worker = worker
        worker.start()

    def _on_ilerleme(self, mesaj: str) -> None:
        self._durum(mesaj)

    def _on_bitti(self, sonuc: object) -> None:
        self._btn_csv.setEnabled(True)
        if self.PDF_DESTEK:
            self._btn_pdf.setEnabled(True)
        self._goster(sonuc)

    def _on_hata(self, mesaj: str) -> None:
        self._durum("Rapor getirilemedi.", "hata")
        QMessageBox.warning(self, "Mikro Hatası", mesaj)

    def _on_worker_bitti(self, worker: RaporWorker) -> None:
        if worker is self._worker:
            self._worker = None
            self._btn_getir.setEnabled(True)
            self._btn_iptal.setVisible(False)
        worker.deleteLater()

    def _on_iptal(self) -> None:
        """İşbirlikçi iptal: sonuç yok sayılır; süren istek timeout'una kadar arkada söner."""
        if self._worker is not None:
            self._worker.iptal_et()
            self._worker = None
        self._btn_getir.setEnabled(True)
        self._btn_iptal.setVisible(False)
        self._durum("İptal edildi.", "uyari")

    # ------------------------------------------------------------------- CSV
    def _on_csv(self) -> None:
        icerik = self._csv_icerik()
        if icerik is None:
            return
        csv_kaydet(self, self._status, self._csv_dosya_adi(), icerik)
