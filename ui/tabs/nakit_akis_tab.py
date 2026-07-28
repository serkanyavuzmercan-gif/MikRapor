"""Nakit Akış sekmesi — banka/kasa hareketinden kategorize nakit akış."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from domain.kredi import (
    KART_BORCU_VARSAYILAN_ODEME_YUZDE,
    kredi_karti_borclarini_derle,
    kredi_karti_odeme_takvimi,
    kredi_odemelerini_derle,
    taksitleri_derle,
)
from domain.mizan_bilanco import tl
from domain.nakit_akis import NakitAkis, build_nakit_akis, nakit_akis_csv
from domain.tahsilat_alacak import TahsilatAlacak, build_tahsilat_alacak
from infra.config import MikroConfig
from infra.mikro_api import MikroAPIError
from infra.mikro_fetch import (
    fetch_acik_kalemler,
    fetch_cari_bakiye,
    fetch_cari_vade_gun,
    fetch_kredi_gl,
    fetch_kredi_karti_borclari,
    fetch_kredi_odemeleri_gl,
    fetch_kredi_taksitleri,
    fetch_nakit_akis_gl,
    fetch_nakit_akis_hareket,
    fetch_nakit_bakiye_gl,
    fetch_nakit_delta,
    fetch_nakit_delta_gl,
)
from infra.mukayese_fetch import (
    YilVeritabaniHatasi,
    donem_parcalari,
    donem_satirlari,
    donem_toplami,
    yil_client,
)
from ui.bilesenler import varsayilan_kayit_yolu
from ui.nakit_akis_pdf import export_nakit_akis_pdf
from ui.nakit_akis_view import build_nakit_akis_widget
from ui.rapor_tab import RaporTab, firma_getir
from ui.worker import IsFonksiyonu

_RUNWAY_REFERANS_GUN = 90


def _runway_referans_bas(bit: str) -> str:
    """Runway için rapor başlangıcından bağımsız, bitişe göre sabit 90 günlük pencere."""
    try:
        return (date.fromisoformat(bit) - timedelta(days=_RUNWAY_REFERANS_GUN - 1)).isoformat()
    except ValueError:
        return bit


class NakitAkisTab(RaporTab):
    """Banka/kasa hareketinden kategorize nakit akış (tahsilat, ödeme, kredi…) sekmesi."""

    EMOJI = "💵"
    BASLIK = "Nakit Akış"
    ACIKLAMA = (
        "Banka ve kasadan fiilen geçen para — karşı tarafına göre kategorize:<br>"
        "müşteri tahsilatı, satıcı ödemesi, kredi kullanım/ödemesi, vergi & SGK.<br>"
        "<span style='color:#9aa0a8;'>Açılış → girişler − çıkışlar → kapanış + aylık trend.</span>")
    GETIR_ETIKET = "Nakit Akışı Getir"
    BASLARKEN = "Banka/kasa hareketleri çekiliyor…"
    PDF_DESTEK = True
    HERO_ASSET = "empty-nakit.png"

    _na: NakitAkis | None = None

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        def is_fn(bildir) -> dict[str, Any]:
            # Veritabanını firma kodu seçer: dönemin bittiği yıl hangi
            # veritabanındaysa oraya bağlanılır (bkz. infra/veritabani.py).
            client = yil_client(cfg, int(bit[:4]))
            # ÖNCE MUHASEBE (GL): cari tablosu yalnız cari modülünden geçen banka/kasa
            # hareketini görür; çek ödemesi / EFT / kredi gibi doğrudan muhasebeye
            # işlenenleri kaçırır (satıcı ödemesi 13K gibi külli eksik rakamlar).
            # GL'de akış + kapanış aynı kaynaktan → mutabakat kapanır.
            na = None
            try:
                bildir("Nakit hareketleri muhasebeden çekiliyor…")
                # AKIŞ bölünür (dönem iki veritabanına yayılabilir), BAKİYE bölünmez:
                # kapanış nakdi tek bir tarihe aittir, bitişin veritabanından okunur.
                gl_rows = donem_satirlari(cfg, bas, bit, fetch_nakit_akis_gl,
                                          bildir=bildir, ad="nakit hareketleri")
                if gl_rows:
                    kapanis = fetch_nakit_bakiye_gl(client, bit)
                    delta = donem_toplami(cfg, bas, bit, fetch_nakit_delta_gl)
                    bildir("Nakit akış kuruluyor…")
                    na = build_nakit_akis(
                        gl_rows, kapanis_nakit=kapanis,
                        donem_delta=delta, bas=bas, bit=bit)
                    na.kaynak = "gl"
            except MikroAPIError:
                na = None
            if na is None:
                bildir("Banka/kasa hareketleri çekiliyor…")
                hareket_rows = donem_satirlari(cfg, bas, bit, fetch_nakit_akis_hareket,
                                               bildir=bildir, ad="banka/kasa hareketleri")
                bildir("Kapanış bakiyeleri çekiliyor…")
                kapanis_rows = fetch_cari_bakiye(client, bit)
                donem_delta = donem_toplami(cfg, bas, bit, fetch_nakit_delta)
                bildir("Nakit akış kuruluyor…")
                na = build_nakit_akis(
                    hareket_rows, bakiye_kapanis_rows=kapanis_rows,
                    donem_delta=donem_delta, bas=bas, bit=bit)

            # Runway, ekrandaki rapor başlangıcına göre değil; bitiş tarihindeki son 90 günlük
            # sabit pencereye göre hesaplanır. Böylece kullanıcı aynı "as of" tarihi için
            # rapor aralığını değiştirince ileriye dönük hız değişmez.
            runway_bas = _runway_referans_bas(bit)
            runway_na: NakitAkis | None = None
            try:
                # 90 günlük pencere yıl sınırını aşabilir (ör. 18.11.2025 – 15.02.2026).
                if na.kaynak == "gl":
                    runway_rows = donem_satirlari(cfg, runway_bas, bit, fetch_nakit_akis_gl)
                    if runway_rows:
                        runway_na = build_nakit_akis(
                            runway_rows, kapanis_nakit=na.kapanis_nakit,
                            donem_delta=donem_toplami(cfg, runway_bas, bit, fetch_nakit_delta_gl),
                            bas=runway_bas, bit=bit,
                        )
                        runway_na.kaynak = "gl"
                else:
                    runway_rows = donem_satirlari(cfg, runway_bas, bit, fetch_nakit_akis_hareket)
                    if runway_rows:
                        runway_na = build_nakit_akis(
                            runway_rows, kapanis_nakit=na.kapanis_nakit,
                            donem_delta=donem_toplami(cfg, runway_bas, bit, fetch_nakit_delta),
                            bas=runway_bas, bit=bit,
                        )
            except (MikroAPIError, YilVeritabaniHatasi):
                runway_na = None

            # Açık cari kalemler, vadesi yaklaşan gerçek tahsilat/ödemeleri runway'e taşır.
            runway_ta: TahsilatAlacak | None = None
            try:
                bildir("Nakit projeksiyonu için açık cari kalemler çekiliyor…")
                vade_gun_map = fetch_cari_vade_gun(client)
                acik_rows = fetch_acik_kalemler(client, bit, runway_bas, bit)
                runway_ta = build_tahsilat_alacak(
                    acik_rows, vade_gun_map=vade_gun_map, bas=runway_bas, bit=bit,
                )
            except MikroAPIError:
                runway_ta = None

            # Kredi özeti nakit sınıflamasından değil, kredi borç hesaplarının iki yönlü
            # muhasebe hareketinden kurulur. Böylece refinansman ve nakde uğramayan kapamalar
            # da gerçek borç değişimine dahil olur; kredi kartı hesapları sorguda dışlanır.
            try:
                bildir("Kredi borç hareketleri muhasebeden okunuyor…")
                odeme = kullanim = 0.0
                for c, p_bas, p_bit in donem_parcalari(cfg, bas, bit):
                    kgl = fetch_kredi_gl(c, p_bas, p_bit)
                    odeme += kgl.get("odeme", 0.0)
                    kullanim += kgl.get("kullanim", 0.0)
                # Yarım kalan bir parça yanlış toplam vermesin: hepsi bitince yazılır.
                na.kredi_odeme_gl, na.kredi_kullanim_gl = odeme, kullanim
                na.kredi_ozet_gl = True
            except (MikroAPIError, YilVeritabaniHatasi):
                pass
            # Seçili dönemde fiilen nakitten çıkan banka kredisi anaparaları ekranda detaylanır.
            # Gelecek sözleşme taksitleri yalnızca ileriye dönük runway hesabına gider.
            kredi_odemeleri = []
            gelecek_taksitler = []
            kart_borcu_takvimi: dict[str, float] = {}
            try:
                if na.kaynak == "gl":
                    bildir("Dönem kredi ödemeleri detaylandırılıyor…")
                    kredi_odemeleri = kredi_odemelerini_derle(
                        donem_satirlari(cfg, bas, bit, fetch_kredi_odemeleri_gl)
                    )
            except (MikroAPIError, YilVeritabaniHatasi):
                kredi_odemeleri = []
            try:
                gelecek_taksitler = taksitleri_derle(
                    fetch_kredi_taksitleri(client, ay_ileri=18, asof=bit)
                )
            except MikroAPIError:
                gelecek_taksitler = []
            try:
                bildir("Açık kredi kartı borçları çekiliyor…")
                kart_borclari = kredi_karti_borclarini_derle(fetch_kredi_karti_borclari(client, bit))
                kart_borcu_takvimi = kredi_karti_odeme_takvimi(
                    kart_borclari,
                    baslangic_ay=bit[:7],
                    odeme_yuzde=KART_BORCU_VARSAYILAN_ODEME_YUZDE,
                    ufuk_ay=6,
                )
            except MikroAPIError:
                kart_borcu_takvimi = {}
            return {
                "na": na, "firma": firma_getir(cfg, client),
                "kredi_odemeleri": kredi_odemeleri,
                "runway_na": runway_na, "runway_ta": runway_ta,
                "runway_referans_bas": runway_bas, "taksitler": gelecek_taksitler,
                "kart_borcu_takvimi": kart_borcu_takvimi,
            }

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        na: NakitAkis = sonuc["na"]
        self._na = na
        self._firma = sonuc["firma"]
        self._icerik_koy(build_nakit_akis_widget(
            na, firma=self._firma, kredi_odemeleri=sonuc.get("kredi_odemeleri"),
            runway_na=sonuc.get("runway_na"), runway_ta=sonuc.get("runway_ta"),
            runway_referans_bas=sonuc.get("runway_referans_bas", ""),
            kredi_taksitler=sonuc.get("taksitler"),
            kart_borcu_takvimi=sonuc.get("kart_borcu_takvimi"),
        ))
        parts = [
            f"Giriş {tl(na.toplam_giris)}",
            f"Çıkış {tl(na.toplam_cikis)}",
            f"Net {tl(na.net_akis)}",
        ]
        if na.kredi_odeme_gosterim > 0.005 or na.kredi_kullanim_gosterim > 0.005:
            kaynak = " (muhasebeden)" if na.kredi_kaynak_gl else ""
            parts.append(f"Kredi net {tl(na.kredi_net_gosterim)}{kaynak}")
        if na.hareket_sayisi == 0:
            parts.insert(0, "⚠ banka/kasa hareketi yok — dönem/yıl kontrol edin")
        self._durum(
            " · ".join(parts),
            "uyari" if na.hareket_sayisi == 0 else ("iyi" if na.net_akis >= 0 else "hata"),
        )

    def _on_pdf(self) -> None:
        if not self._na:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet",
            varsayilan_kayit_yolu(f"{self._slug}_{self._na.bas}_{self._na.bit}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            export_nakit_akis_pdf(self._na, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"{self._slug}_{self._na.bas}_{self._na.bit}.csv" if self._na else f"{self._slug}.csv"

    def _csv_icerik(self) -> str | None:
        return nakit_akis_csv(self._na) if self._na else None
