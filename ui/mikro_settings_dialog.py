"""
Mikro bağlantı ayarları ekranı (PyQt6).

Kullanıcı kendi Mikro sunucusunun bilgilerini girer; "Bağlantıyı Test Et" ile auth+ağ
doğrulanır, "Kaydet" ile yerel diske yazılır (config.save_config). Bilgiler makineden çıkmaz.

Ağ çağrıları (ping, firma adı) RaporWorker ile arka planda çalışır — UI donmaz.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from infra.config import MikroConfig, config_path, load_config, save_config
from infra.mikro_api import MikroClient
from infra.mikro_fetch import fetch_firma_adi
from infra.veritabani import FirmaKapsami, firma_kodlari, katalog, onbellegi_temizle
from ui.worker import RaporWorker


class MikroAyarlarDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mikro Bağlantı Ayarları")
        self.setMinimumWidth(520)
        self._cfg = load_config()
        self._worker: RaporWorker | None = None
        self._build_ui()
        self._on_tls_toggled(self._tls_dogrula.isChecked())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Bu bilgiler yalnızca bu bilgisayarda saklanır ve doğrudan kendi Mikro "
            "sunucunuza bağlanmak için kullanılır. Hiçbir bilgi dışarı gönderilmez. "
            "API anahtarı ve şifre Windows'ta DPAPI, Linux/macOS'ta yerel anahtarla "
            "şifrelenerek kaydedilir. Uzak adreslerde https:// zorunludur."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #9aa0a8;")
        layout.addWidget(info)

        form = QFormLayout()
        self._base_url = QLineEdit(self._cfg.base_url)
        self._base_url.setPlaceholderText("https://192.168.1.50:443  (http yalnız localhost)")
        self._api_key = QLineEdit(self._cfg.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        # Mikro'da veritabanını firma kodu seçer ve bir veritabanı birden çok yıl
        # taşıyabilir. Liste veya sayısal aralık girilir; program yıl eşlemesini tarar.
        self._firma_kodlari = QLineEdit(self._cfg.firma_kodlari or self._cfg.firma_kodu)
        self._firma_kodlari.setPlaceholderText("zorunlu — örn. 20, 26 veya 001-100")
        self._kullanici = QLineEdit(self._cfg.kullanici_kodu)
        self._sifre_gun = QLineEdit(self._cfg.sifre_gun)
        self._sifre_gun.setEchoMode(QLineEdit.EchoMode.Password)
        self._sifre_gun.setPlaceholderText("Mikro kullanıcı şifresi")

        form.addRow("Mikro API adresi:", self._base_url)
        form.addRow("API anahtarı:", self._api_key)
        firma_kodlari_row = QHBoxLayout()
        firma_kodlari_row.addWidget(self._firma_kodlari, stretch=1)
        self._btn_katalog = QPushButton("Yılları Tara")
        self._btn_katalog.setToolTip("Kodların taşıdığı yıl aralıklarını Mikro'dan tarar")
        self._btn_katalog.clicked.connect(self._on_katalog_tara)
        firma_kodlari_row.addWidget(self._btn_katalog)
        form.addRow("Yıl veritabanları:", firma_kodlari_row)
        self._katalog_sonuc = QLabel(
            "Birden çok veritabanı varsa kodları liste veya aralık olarak girin; "
            "örnek: 20, 26 ya da 001-100."
        )
        self._katalog_sonuc.setWordWrap(True)
        self._katalog_sonuc.setStyleSheet("color: #9aa0a8; font-size: 11px;")
        form.addRow("", self._katalog_sonuc)
        form.addRow("Kullanıcı kodu:", self._kullanici)
        form.addRow("Şifre:", self._sifre_gun)

        self._firma_adi = QLineEdit(self._cfg.firma_adi)
        self._firma_adi.setPlaceholderText("Boş bırakırsanız Mikro'dan (FIRMALAR.fir_unvan) otomatik çekilir")
        firma_row = QHBoxLayout()
        firma_row.addWidget(self._firma_adi, stretch=1)
        self._btn_firma = QPushButton("Mikro'dan Getir")
        self._btn_firma.clicked.connect(self._on_firma_getir)
        firma_row.addWidget(self._btn_firma)
        form.addRow("Firma adı (raporlarda):", firma_row)

        self._show_secrets = QCheckBox("Anahtar ve şifreyi göster")
        self._show_secrets.toggled.connect(self._on_toggle_secrets)
        form.addRow("", self._show_secrets)

        self._tls_dogrula = QCheckBox("TLS sertifikasını doğrula")
        self._tls_dogrula.setChecked(self._cfg.tls_dogrula)
        self._tls_dogrula.toggled.connect(self._on_tls_toggled)
        form.addRow("", self._tls_dogrula)

        self._tls_uyari = QLabel("")
        self._tls_uyari.setWordWrap(True)
        self._tls_uyari.setStyleSheet("color: #ffb74d; font-size: 11px;")
        form.addRow("", self._tls_uyari)
        layout.addLayout(form)

        path_lbl = QLabel(f"Kayıt yeri: {config_path()}")
        path_lbl.setStyleSheet("color: #9aa0a8; font-size: 10px;")
        path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_lbl)

        test_row = QHBoxLayout()
        self._btn_test = QPushButton("Bağlantıyı Test Et")
        self._btn_test.clicked.connect(self._on_test)
        test_row.addWidget(self._btn_test)
        # VERİ SAĞLIĞI BURADA, sekme çubuğunda DEĞİL: bütün rapor sekmeleri seçili
        # tarih aralığına bağlıyken bu değil — verinin durumu bir dönem raporu değil,
        # kurulumun hâli. Sekmede durunca kullanıcı ondan dönem raporu bekliyordu.
        self._btn_saglik = QPushButton("Veri Sağlığı")
        self._btn_saglik.clicked.connect(self._on_veri_sagligi)
        test_row.addWidget(self._btn_saglik)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        test_row.addWidget(self._test_result, stretch=1)
        layout.addLayout(test_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        from ui.bilesenler import dialog_kaydet_iptal
        dialog_kaydet_iptal(buttons)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _on_tls_toggled(self, checked: bool) -> None:
        if checked:
            self._tls_uyari.setText("")
        else:
            self._tls_uyari.setText(
                "Uyarı: sertifika doğrulaması kapalı — bağlantı MITM’e açık olabilir. "
                "Self-signed Mikro kurulumlarında normal; aksi halde kutuyu işaretleyin."
            )

    def _set_busy(self, busy: bool) -> None:
        self._btn_test.setEnabled(not busy)
        self._btn_firma.setEnabled(not busy)
        self._btn_katalog.setEnabled(not busy)
        self._buttons.setEnabled(not busy)

    def _on_katalog_tara(self) -> None:
        """Girilen kodların yıl kapsamını arka planda bulur; raporları etkilemez."""
        cfg = self._current_config()
        eksik = cfg.eksik_alanlar()
        if eksik:
            self._katalog_sonuc.setText("Tarama için eksik: " + ", ".join(eksik))
            self._katalog_sonuc.setStyleSheet("color: #ffb74d; font-size: 11px;")
            return
        kodlar = firma_kodlari(cfg)
        self._katalog_sonuc.setText(f"{len(kodlar)} kod taranıyor; bu işlem biraz sürebilir…")
        self._katalog_sonuc.setStyleSheet("color: #9aa0a8; font-size: 11px;")

        def is_fn(bildir) -> list[FirmaKapsami]:
            bildir("Veritabanı yıl kapsamları taranıyor…")
            return katalog(cfg, yenile=True)

        def on_ok(sonuc: object) -> None:
            kapsamlar = list(sonuc or [])
            if not kapsamlar:
                self._katalog_sonuc.setText(
                    "Erişilebilir bir yıl veritabanı bulunamadı. Kodları ve bağlantıyı kontrol edin."
                )
                self._katalog_sonuc.setStyleSheet("color: #ffb74d; font-size: 11px;")
                return
            ozet = " · ".join(
                f"{k.firma_kodu}: {k.ilk_yil}–{k.son_yil}" for k in kapsamlar
            )
            bulunan = {k.firma_kodu for k in kapsamlar}
            okunamayan = [k for k in kodlar if k not in bulunan]
            ek = (f" | Yıl kapsamı okunamadı, raporda kullanılmayacak: {', '.join(okunamayan)}"
                  if okunamayan else "")
            renk = "#ffb74d" if okunamayan else "#81c784"
            self._katalog_sonuc.setText(f"Bulunan yıl eşlemesi: {ozet}{ek}")
            self._katalog_sonuc.setStyleSheet(f"color: {renk}; font-size: 11px;")

        def on_err(mesaj: str) -> None:
            self._katalog_sonuc.setText(f"Tarama başarısız: {mesaj}")
            self._katalog_sonuc.setStyleSheet("color: #e57373; font-size: 11px;")

        self._baslat_is(is_fn, on_ok, on_err)

    def _baslat_is(self, is_fn, on_ok, on_err) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_busy(True)
        worker = RaporWorker(is_fn, parent=self)
        self._worker = worker
        worker.bitti.connect(on_ok)
        worker.hata.connect(on_err)

        def _bitti() -> None:
            self._set_busy(False)
            if self._worker is worker:
                self._worker = None

        worker.finished.connect(_bitti)
        worker.start()

    def _on_firma_getir(self) -> None:
        cfg = self._current_config()
        eksik = cfg.eksik_alanlar()
        if eksik:
            self._test_result.setText("Önce bağlantı bilgileri gerekli: " + ", ".join(eksik))
            self._test_result.setStyleSheet("color: #ffb74d;")
            return
        self._test_result.setText("Firma adı getiriliyor…")
        self._test_result.setStyleSheet("color: #9aa0a8;")

        def is_fn(bildir) -> str:
            bildir("Firma adı getiriliyor…")
            return fetch_firma_adi(MikroClient(cfg))

        def on_ok(ad: object) -> None:
            text = str(ad or "").strip()
            if text:
                self._firma_adi.setText(text)
                self._test_result.setText(f"✓ Firma adı getirildi: {text}")
                self._test_result.setStyleSheet("color: #81c784;")
            else:
                self._test_result.setText("Firma ünvanı bulunamadı (FIRMALAR.fir_unvan boş).")
                self._test_result.setStyleSheet("color: #ffb74d;")

        def on_err(msg: str) -> None:
            self._test_result.setText(f"✗ Firma adı alınamadı: {msg}")
            self._test_result.setStyleSheet("color: #e57373;")

        self._baslat_is(is_fn, on_ok, on_err)

    def _on_veri_sagligi(self) -> None:
        """Rapor rakamlarını bozabilecek kayıt sorunlarını ayrı pencerede gösterir."""
        from ui.veri_sagligi_dialog import VeriSagligiDialog
        VeriSagligiDialog(self).exec()

    def _on_toggle_secrets(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self._api_key.setEchoMode(mode)
        self._sifre_gun.setEchoMode(mode)

    def _current_config(self) -> MikroConfig:
        return MikroConfig(
            base_url=self._base_url.text(),
            api_key=self._api_key.text(),
            firma_kodu="",  # firma_kodlari'nın ilk kodundan otomatik türetilir
            firma_kodlari=self._firma_kodlari.text(),
            # Rapor yılını kullanıcı seçer; Mikro API için çalışma yılı da o seçili
            # tarihten türetilir. Burada kalıcı bir yıl tercihi yoktur.
            calisma_yili=0,
            kullanici_kodu=self._kullanici.text(),
            sifre_gun=self._sifre_gun.text(),
            firma_adi=self._firma_adi.text(),
            tls_dogrula=self._tls_dogrula.isChecked(),
        ).normalized()

    def _on_test(self) -> None:
        cfg = self._current_config()
        eksik = cfg.eksik_alanlar()
        if eksik:
            self._test_result.setText("Eksik: " + ", ".join(eksik))
            self._test_result.setStyleSheet("color: #ffb74d;")
            return
        self._test_result.setText("Bağlanılıyor…")
        self._test_result.setStyleSheet("color: #9aa0a8;")

        def is_fn(bildir) -> bool:
            bildir("Bağlanılıyor…")
            MikroClient(cfg).ping()
            return True

        def on_ok(_ok: object) -> None:
            self._test_result.setText("✓ Bağlantı başarılı.")
            self._test_result.setStyleSheet("color: #81c784;")

        def on_err(msg: str) -> None:
            self._test_result.setText(f"✗ Başarısız: {msg}")
            self._test_result.setStyleSheet("color: #e57373;")

        self._baslat_is(is_fn, on_ok, on_err)

    def _on_save(self) -> None:
        cfg = self._current_config()
        eksik = cfg.eksik_alanlar()
        if eksik:
            QMessageBox.warning(self, "Eksik Bilgi", "Şu alanlar zorunlu:\n• " + "\n• ".join(eksik))
            return
        try:
            from infra.sql_params import firma_kodu_guvenli

            for kod in firma_kodlari(cfg):
                firma_kodu_guvenli(kod)
        except ValueError as exc:
            QMessageBox.warning(self, "Geçersiz Firma Kodu", str(exc))
            return
        url_hatalari = cfg.base_url_hatalari()
        if url_hatalari:
            QMessageBox.warning(self, "Geçersiz API Adresi", "\n".join(url_hatalari))
            return
        if not cfg.tls_dogrula:
            from ui.bilesenler import soru_evet_hayir

            if not soru_evet_hayir(
                self,
                "TLS doğrulaması kapalı",
                "TLS sertifika doğrulaması kapalı. Self-signed Mikro sunucuları için "
                "bu yaygındır; geçerli (imzalı) sertifikanız varsa iptal edip kutuyu işaretleyin.\n\n"
                "Yine de kaydedilsin mi?",
            ):
                return
        try:
            save_config(cfg)
        except OSError as exc:
            QMessageBox.critical(self, "Kaydedilemedi", str(exc))
            return
        # Firma listesi değişmiş olabilir; eski kapsamlar yılları yanlış
        # veritabanına yönlendirmesin.
        onbellegi_temizle()
        self._cfg = cfg
        self.accept()

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.iptal_et()
            self._worker.wait(5000)
        super().reject()

    def accept(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.iptal_et()
            self._worker.wait(5000)
        super().accept()

    def saved_config(self) -> MikroConfig:
        return self._cfg
