"""
Nakit akış kategorisinin ARKASINDAKİ fişler — «bu rakam gerçek mi» sorusunun cevabı.

Canlı bir demoda mali müşavir «müşteri tahsilatı 3M — bu yapıldı mı?» diye sordu ve
gösterilecek hiçbir şey yoktu. Bir uzman rakamına itiraz ettiğinde elinde kanıt yoksa
tartışmayı kaybediyorsun; üstelik o rakam doğruydu, yüzlerce fişin toplamıydı.

Pencere ÖZETLE AYNI SORGUDAN beslenir (infra.mikro_fetch._gl_nakit_kirilim) ve altta
detay toplamı ile panel toplamını yan yana yazar: tutmuyorsa bunu SÖYLER. Kendi
rakamını doğrulayamayan bir kanıt penceresi, hiç olmamasından kötüdür.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QVBoxLayout,
)

from domain.mizan_bilanco import tl
from domain.nakit_akis import hesap_kirilim_etiketi, kategori_etiketi
from domain.ortak import csv_metin, csv_sayi, tr_sayi
from domain.ortak import to_float as _f
from infra.config import MikroConfig
from infra.mikro_api import MikroAPIError
from infra.mikro_fetch import fetch_nakit_akis_detay
from infra.mukayese_fetch import YilVeritabaniHatasi, donem_satirlari
from ui.bilesenler import csv_kaydet
from ui.gercek_durum_view import _agac, _c, _ic, _tsatir
from ui.styles import MUTED, NAVY, SURFACE
from ui.worker import RaporWorker

# Ekranda en fazla bu kadar fiş; tamamı CSV'de. Binlerce satırlık liste hem pencereyi
# hem de «bak işte, 47 tahsilat» anlatısını boğuyor.
_AZAMI_SATIR = 300

# Detay ile panel toplamı arasındaki kabul edilebilir sapma (yuvarlama payı).
_TOLERANS = 0.5

# Kapanışta çalışan sorgunun sonlanması için beklenen süre.
_KAPANIS_BEKLEME_MS = 5000


class NakitDetayDialog(QDialog):
    """Tek bir nakit kategorisinin fiş fiş dökümü."""

    def __init__(self, cfg: MikroConfig, *, bas: str, bit: str, tip: int,
                 etiket: str, beklenen: float, parent=None) -> None:
        super().__init__(parent)
        self._cfg, self._bas, self._bit = cfg, bas, bit
        self._tip, self._etiket, self._beklenen = tip, etiket, beklenen
        self._satirlar: list[dict] = []
        self._worker: RaporWorker | None = None
        self.setWindowTitle(f"{etiket} — hareket dökümü")
        self.setObjectName("ndDialog")
        self.setMinimumSize(780, 520)
        self._build()
        self._basla()

    def _build(self) -> None:
        kok = QVBoxLayout(self)
        kok.setContentsMargins(0, 0, 0, 0)
        kok.setSpacing(0)

        baslik = QFrame()
        baslik.setObjectName("ndBaslik")
        bl = QVBoxLayout(baslik)
        bl.setContentsMargins(18, 14, 18, 12)
        bl.setSpacing(3)
        ey = QLabel("GERÇEKLEŞEN HAREKETLER")
        ey.setStyleSheet("color:#8fb8d8; font-size:11px; font-weight:800; "
                         "letter-spacing:1px; background:transparent;")
        bl.addWidget(ey)
        self._ust = QLabel(self._etiket)
        self._ust.setWordWrap(True)
        self._ust.setStyleSheet("color:#ffffff; font-size:16px; font-weight:800; "
                                "background:transparent;")
        bl.addWidget(self._ust)
        self._alt = QLabel("Fişler okunuyor…")
        self._alt.setWordWrap(True)
        self._alt.setStyleSheet("color:#c5d8e8; font-size:11px; background:transparent;")
        bl.addWidget(self._alt)
        kok.addWidget(baslik)

        self._govde = QVBoxLayout()
        self._govde.setContentsMargins(16, 14, 16, 10)
        kok.addLayout(self._govde, 1)

        butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._btn_csv = butonlar.addButton("CSV", QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        butonlar.rejected.connect(self.reject)
        butonlar.setContentsMargins(16, 0, 16, 13)
        kok.addWidget(butonlar)

        self.setStyleSheet(
            f"QDialog#ndDialog {{ background: {SURFACE}; }}"
            f"QFrame#ndBaslik {{ background: {NAVY}; border: none; }}")

    # ------------------------------------------------------------------ çekim
    def _basla(self) -> None:
        cfg, bas, bit, tip, etiket = (
            self._cfg, self._bas, self._bit, self._tip, self._etiket)

        def is_fn(bildir) -> list[dict]:
            bildir("Nakit fişleri okunuyor…")
            try:
                ham = donem_satirlari(
                    cfg, bas, bit,
                    lambda c, b, e: fetch_nakit_akis_detay(c, b, e, tip),
                    bildir=bildir, ad="nakit fişleri")
            except (MikroAPIError, YilVeritabaniHatasi):
                return []
            # Sınıflama ÖZETLE AYNI fonksiyonla yapılır; ayrı eşleme yazılsaydı detay
            # ile toplam sessizce ayrışırdı.
            return [r for r in ham
                    if kategori_etiketi(str(r.get("prefix", r.get("PREFIX")) or ""),
                                        tip) == etiket]

        worker = RaporWorker(is_fn, parent=self)
        self._worker = worker
        worker.bitti.connect(self._goster)
        worker.hata.connect(lambda m: self._alt.setText(f"Okunamadı: {m}"))
        worker.finished.connect(self._birak)
        worker.start()

    def _birak(self) -> None:
        self._worker = None

    # ------------------------------------------------------------------ kapanış
    def reject(self) -> None:  # noqa: D102 — Qt API
        self._durdur()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        self._durdur()
        super().closeEvent(event)

    def _durdur(self) -> None:
        """
        Kapanırken çalışan sorguyu iptal et ve BEKLE.

        KRİTİK: hâlâ koşan bir QThread'in sahibi yok edilirse Qt «Destroyed while
        thread is still running» ile SÜRECİ ÖLDÜRÜR. Uzun bir sorgu sırasında pencereyi
        kapatmak programı kapatıyordu (bkz. CLAUDE.md — Qt ölümcül tuzağı).
        """
        w, self._worker = self._worker, None
        if w is None:
            return
        w.iptal_et()
        w.wait(_KAPANIS_BEKLEME_MS)

    # ---------------------------------------------------------------- gösterim
    def _goster(self, sonuc: object) -> None:
        if not isinstance(sonuc, list):
            return
        self._satirlar = sonuc
        toplam = sum(_f(r.get("tutar", r.get("TUTAR"))) for r in sonuc)
        self._btn_csv.setEnabled(bool(sonuc))
        # Sayı ayrı biçimlenir: cümlenin tamamında virgül→nokta değişimi tl() çıktısını
        # bozuyordu («2.950.000,00» → «2.950.000.00»). Bkz. domain.ortak.tr_sayi.
        self._alt.setText(f"{self._bas} → {self._bit}  ·  "
                          f"{tr_sayi(len(sonuc), 0)} hareket  ·  toplam {tl(toplam)}")

        t = _agac(4, [(0, 96), (1, 92), (3, 140)], esnek=2)
        _tsatir(t, [_c("Tarih", renk=MUTED, kalin=True),
                    _c("Yevmiye", renk=MUTED, kalin=True),
                    _c("Karşı hesap", renk=MUTED, kalin=True),
                    _c("Tutar", renk=MUTED, kalin=True, sag=True)])
        for r in sonuc[:_AZAMI_SATIR]:
            hesap = str(r.get("hesap", r.get("HESAP")) or "")
            _tsatir(t, [
                _c(str(r.get("tarih", r.get("TARIH")) or "")[:10]),
                _c(str(int(_f(r.get("yevmiye", r.get("YEVMIYE")))) or "")),
                _c(hesap or hesap_kirilim_etiketi(
                    str(r.get("prefix", r.get("PREFIX")) or ""))),
                _c(tl(_f(r.get("tutar", r.get("TUTAR")))), sag=True)])
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        notlar: list[tuple[str, str]] = []
        # MUTABAKAT: panelde yazan rakamla buradaki toplam tutmalı. Tutmuyorsa
        # gizlemek yerine söylenir — kanıt penceresinin işi tam olarak budur.
        fark = toplam - self._beklenen
        if abs(fark) > _TOLERANS:
            notlar.append((
                f"Panelde yazan {tl(self._beklenen)} ile bu dökümün toplamı arasında "
                f"{tl(fark)} fark var — döküm eksik olabilir.", "#8a5a00"))
        else:
            notlar.append((
                f"Bu dökümün toplamı, paneldeki {tl(self._beklenen)} ile birebir aynı.",
                MUTED))
        if len(sonuc) > _AZAMI_SATIR:
            notlar.append((f"Ekranda ilk {_AZAMI_SATIR} hareket gösteriliyor; "
                           "tamamı CSV'de.", MUTED))
        notlar.append(("Kaynak: muhasebe yevmiyesi. Bir fişin nakit tutarı, karşısındaki "
                       "hesaplara tutarları oranında dağıtılır.", MUTED))
        self._govde.addWidget(_ic(t, notlar))

    def _on_csv(self) -> None:
        if not self._satirlar:
            return
        out = ["Tarih;Yevmiye;Karşı hesap;Tutar (TL)"]
        for r in self._satirlar:
            out.append(";".join((
                str(r.get("tarih", r.get("TARIH")) or "")[:10],
                str(int(_f(r.get("yevmiye", r.get("YEVMIYE"))))),
                csv_metin(str(r.get("hesap", r.get("HESAP")) or "")),
                csv_sayi(_f(r.get("tutar", r.get("TUTAR")))))))
        ad = f"nakit_detay_{self._bas}_{self._bit}.csv"
        yol = csv_kaydet(self, None, ad, "\r\n".join(out))
        if yol:
            self._alt.setText(f"CSV kaydedildi: {Path(yol).name}")
