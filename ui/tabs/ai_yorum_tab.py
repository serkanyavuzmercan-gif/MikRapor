"""
Yapay Zekâ Yorumu sekmesi — seçili dönemin tüm raporlarını modele yorumlatır.

MikRapor'un dışarıya veri gönderen TEK yeri burasıdır. Üst şeritte API anahtarı ve
açık onay kutusu vardır; ikisi birlikte sağlanmadan «Yorumla» çalışmaz ve hiçbir ağ
çağrısı yapılmaz. Gönderilen veri, diğer sekmelerin CSV üreticilerinden kurulur —
ekranda görülen rakamla modele giden rakam aynı kaynaktan gelsin diye.

Seçilen aralığın EN YENİ yılı «odak» olur ve ham detayı o taşır. Yıllar arası mukayese
ise seçimden BAĞIMSIZ kurulur: tek yıl seçilse bile geriye doğru AZAMI_YIL'e tamamlanır,
çünkü kıyas her koşuda istenen bir şey. Veritabanında olmayan yıllar sessizce düşer.
Aralık AZAMI_YIL'i aşarsa kullanıcıya sorulup en yeni yıllara kırpılır.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from domain.ai_yorum import (
    AZAMI_YIL,
    AiYorum,
    YilKapanis,
    ai_yorum_csv,
    ay_farki,
    build_ai_veri_paketi,
    yil_araligi,
    yillar_arasi_csv,
)
from domain.gelir_tablosu import GelirTablosu, build_gelir_tablosu, gelir_tablosu_csv
from domain.gercek_durum import build_gercek_durum, gercek_durum_csv
from domain.mizan_bilanco import Bilanco, bilanco_csv, build_bilanco
from domain.nakit_akis import build_nakit_akis, nakit_akis_csv
from domain.tahsilat_alacak import build_tahsilat_alacak, tahsilat_alacak_csv
from domain.trend import build_finansal_oranlar, build_trend, trend_csv
from infra.ai_client import yorumla
from infra.ai_config import (
    ONAY_METNI,
    PAYLASIM_UYARISI,
    AiConfig,
    load_ai_config,
    save_ai_config,
)
from infra.ai_saglayici import SAGLAYICILAR
from infra.config import MikroConfig, load_gercek_durum_ayarlar
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import (
    fetch_acik_kalemler,
    fetch_cari_vade_gun,
    fetch_doviz_ozet,
    fetch_gelir_tablosu,
    fetch_mizan,
    fetch_nakit_akis_gl,
    fetch_nakit_bakiye_gl,
    fetch_nakit_delta_gl,
    fetch_nakit_ozet_ve_aylik,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from ui.ai_yorum_pdf import export_ai_yorum_pdf
from ui.ai_yorum_view import build_ai_yorum_widget
from ui.bilesenler import soru_evet_hayir, varsayilan_kayit_yolu
from ui.rapor_tab import RaporTab, firma_getir
from ui.worker import IsFonksiyonu

# Cari listeleri kırpılmasın: kullanıcı ham paylaşımı onayladı, ünvanlar dâhil hepsi gider.
_TUM_CARILER = 100_000


def _kapanis_kur(yil: int, *, tam: bool, b: Bilanco, gt: GelirTablosu,
                 doviz: dict[str, float] | None = None) -> YilKapanis:
    """Bir yılın bilanço + gelir tablosundan karşılaştırma satırını çıkarır."""
    _, ozet = build_finansal_oranlar(b)
    d = doviz or {}
    return YilKapanis(
        yil=yil, tam=tam,
        net_satis=gt.net_satislar, brut_kar=gt.brut_kar,
        faaliyet_kari=gt.faaliyet_kari, net_kar=gt.net_kar,
        nakit=ozet["nakit"], alacak=ozet["alacak"], stok=ozet["stok"],
        kvyk=ozet["kvyk"], uvyk=ozet["uvyk"], donen=ozet["donen"],
        ozkaynak=ozet["ozkaynak"], aktif_toplam=ozet["aktif_toplam"],
        banka_kredisi=_banka_kredisi(b), smm=gt.smm, maliyet_eksik=gt.maliyet_eksik,
        faaliyet_gideri=gt.faaliyet_gideri, finansman_gideri=gt.finansman_gideri,
        satis_usd=d.get("satis_usd", 0.0), kur_son=d.get("kur_son", 0.0))


# 300 Banka Kredileri (KV), 303 UV kredilerin anapara taksitleri, 400 Banka Kredileri (UV).
_KREDI_ANA = {"300", "303", "400"}


def _banka_kredisi(b: Bilanco) -> float:
    """Kredi borçluluğunun yıllar arası trendi — pasifte kredi hesaplarının toplamı."""
    return sum(s.tutar for s in b.pasif if s.ana in _KREDI_ANA)


def _doviz_dene(client: MikroClient, bas: str, bit: str) -> dict[str, float]:
    """Döviz özeti okunamazsa yıl komple düşmesin — döviz bloğu sessizce yazılmaz."""
    try:
        return fetch_doviz_ozet(client, bas, bit)
    except (MikroAPIError, ValueError, KeyError, TypeError):
        return {}


class AiYorumTab(RaporTab):
    """Tüm raporları yıllık bazda yapay zekâya yorumlatan sekme."""

    EMOJI = "🤖"
    BASLIK = "Yapay Zekâ Yorumu"
    ACIKLAMA = (
        "Seçili dönemin <b>tüm rapor verisini</b> girdiğiniz API anahtarına ait yapay zekâ<br>"
        "modeline gönderir ve sade Türkçe bir yönetim yorumu üretir. Son "
        f"{AZAMI_YIL} yılın mukayese tablosu, tek yıl seçseniz de eklenir.<br>"
        "<span style='color:#9aa0a8;'>MikRapor'un dışarıya veri gönderdiği tek yer burasıdır; "
        "onay kutusu işaretlenmeden hiçbir veri çıkmaz.</span>")
    GETIR_ETIKET = "Yorumla ve Gönder"
    GETIR_ETIKET_ZORLA = True   # «Raporu Getir» yanıltıcı olur: bu düğme veriyi DIŞARI gönderir
    BASLARKEN = "Yılın raporları hazırlanıyor…"
    # Yapay zekâ yorumu dakikalar sürer: raporlar çekilir, sonra model tüm dönemi okuyup
    # yazar. "Birkaç saniye" demek kullanıcıya takıldığını düşündürüyordu.
    SURE_IPUCU = "Yapay zekâ tüm dönemi okuyup yazıyor — birkaç dakika sürebilir · «İptal» ile durdurabilirsin"
    PDF_DESTEK = True
    HERO_ASSET = "empty-trendler.png"

    _y: AiYorum | None = None

    def _ilk_mesaj(self) -> str:
        cfg = load_ai_config()
        return "Hazır" if cfg.hazir else (cfg.eksik() or "Hazır")

    # ------------------------------------------------------------ üst şerit (ayarlar)
    def _ust_alan(self, layout: QVBoxLayout) -> None:
        cfg = load_ai_config()

        bar = QFrame()
        bar.setObjectName("aiAyarBar")
        bar.setStyleSheet(
            "QFrame#aiAyarBar { background:#fffaf3; border:1px solid #f0d9b5; "
            "border-radius:10px; margin: 0 0 8px 0; }"
        )
        dis = QVBoxLayout(bar)
        dis.setContentsMargins(14, 10, 14, 11)
        dis.setSpacing(7)

        # 1. satır: sağlayıcı + anahtar
        satir = QHBoxLayout()
        satir.setSpacing(10)
        baslik = QLabel("YAPAY ZEKÂ")
        baslik.setStyleSheet("color:#8a5a00; font-size:11px; font-weight:800; background:transparent;")
        satir.addWidget(baslik)

        satir.addWidget(self._etiket("Sağlayıcı"))
        self._cb_saglayici = QComboBox()
        for s in SAGLAYICILAR:
            self._cb_saglayici.addItem(s.ad, s.kod)
        self._cb_saglayici.setCurrentIndex(max(0, self._cb_saglayici.findData(cfg.saglayici)))
        self._cb_saglayici.currentIndexChanged.connect(self._on_saglayici_degisti)
        satir.addWidget(self._cb_saglayici)

        satir.addWidget(self._etiket("API anahtarı"))
        self._ed_key = QLineEdit(cfg.api_key)
        self._ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._ed_key.setMinimumWidth(180)
        self._ed_key.editingFinished.connect(self._ayar_kaydet)
        satir.addWidget(self._ed_key, 1)

        # «Özel» sağlayıcıda adres elle girilir — listede olmayan/yarın çıkacak servisler için.
        self._ed_url = QLineEdit(cfg.ozel_base_url)
        self._ed_url.setPlaceholderText("https://… (OpenAI uyumlu adres)")
        self._ed_url.setMinimumWidth(200)
        self._ed_url.editingFinished.connect(self._ayar_kaydet)
        satir.addWidget(self._ed_url, 1)

        # Model KULLANICIDAN İSTENMEZ: «Yorumla»ya basınca sağlayıcının listesinden
        # en güncel olan otomatik seçilir (bkz. ai_saglayici.guncel_model_sec).
        self._lbl_anahtar_link = QLabel()
        self._lbl_anahtar_link.setOpenExternalLinks(True)
        self._lbl_anahtar_link.setTextFormat(Qt.TextFormat.RichText)
        self._lbl_anahtar_link.setStyleSheet("font-size:11px; background:transparent;")
        satir.addWidget(self._lbl_anahtar_link)
        dis.addLayout(satir)

        self._chk_onay = QCheckBox(ONAY_METNI)
        self._chk_onay.setObjectName("aiOnay")
        self._chk_onay.setChecked(cfg.onay)
        self._chk_onay.setCursor(Qt.CursorShape.PointingHandCursor)
        # İşaret kutusu AÇIKÇA biçimlendirilir: QCheckBox'a herhangi bir QSS verilince Qt
        # tüm çizimi stil sayfasına devreder ve ::indicator kuralı yoksa kutucuk kaybolur
        # (canlıda görüldü). Onay kapısının görünmez olması kabul edilemez.
        self._chk_onay.setStyleSheet(
            "QCheckBox#aiOnay { color:#7a4a00; font-size:12px; font-weight:700; spacing:8px; "
            "background:transparent; }"
            "QCheckBox#aiOnay::indicator { width:15px; height:15px; border:2px solid #b45309; "
            "border-radius:4px; background:#ffffff; }"
            "QCheckBox#aiOnay::indicator:hover { border-color:#8a5a00; background:#fff7ed; }"
            "QCheckBox#aiOnay::indicator:checked { background:#15803d; border-color:#15803d; }"
        )
        self._chk_onay.toggled.connect(self._ayar_kaydet)
        dis.addWidget(self._chk_onay)

        uyari = QLabel(PAYLASIM_UYARISI)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setWordWrap(True)
        uyari.setStyleSheet("color:#8a5a00; font-size:11px; background:transparent;")
        dis.addWidget(uyari)

        layout.addWidget(bar)
        self._saglayici_ui_tazele(cfg)

    @staticmethod
    def _etiket(metin: str) -> QLabel:
        lbl = QLabel(metin)
        lbl.setStyleSheet("color:#5c4326; font-size:11px; font-weight:600; background:transparent;")
        return lbl

    def _saglayici_ui_tazele(self, cfg: AiConfig) -> None:
        """Seçili sağlayıcıya göre ipucu, adres kutusu ve anahtar bağlantısını günceller."""
        s = cfg.saglayici_bilgi
        self._ed_key.setPlaceholderText(s.anahtar_ipucu or "API anahtarı")
        self._ed_url.setVisible(s.ozel_mi)
        if s.anahtar_url:
            self._lbl_anahtar_link.setText(
                f"<a style='color:#8a5a00;' href='{s.anahtar_url}'>anahtar al ↗</a>")
            self._lbl_anahtar_link.setVisible(True)
        else:
            self._lbl_anahtar_link.setVisible(False)

    def _on_saglayici_degisti(self) -> None:
        """Sağlayıcı değişti: o sağlayıcının kayıtlı anahtarını geri yükle."""
        kayitli = load_ai_config()
        kod = self._cb_saglayici.currentData() or ""
        self._ed_key.blockSignals(True)
        self._ed_key.setText(kayitli.anahtar_al(kod))
        self._ed_key.blockSignals(False)
        cfg = self._ayarlar()
        # Model sağlayıcıya özgüdür; değişince önbellek düşer, yenisi otomatik seçilir.
        if kod != kayitli.saglayici:
            cfg.model = ""
        self._saglayici_ui_tazele(cfg)
        save_ai_config(cfg)
        self._durum(cfg.eksik() or f"{cfg.saglayici_bilgi.ad} seçildi — model otomatik seçilecek.",
                    "uyari" if not cfg.hazir else "iyi")
    def _ayarlar(self) -> AiConfig:
        return AiConfig(
            saglayici=self._cb_saglayici.currentData() or "",
            api_key=self._ed_key.text(),
            onay=self._chk_onay.isChecked(),
            model=load_ai_config().model,   # yalnız önbellek; kullanıcı seçmez
            ozel_base_url=self._ed_url.text(),
            anahtarlar=dict(load_ai_config().anahtarlar),
        ).normalized()

    def _ayar_kaydet(self) -> None:
        cfg = self._ayarlar()
        save_ai_config(cfg)
        self._durum(cfg.eksik() or "Yapay zekâ ayarları kaydedildi.",
                    "uyari" if not cfg.hazir else "iyi")

    # ------------------------------------------------------------------------ iş
    def _on_getir(self) -> None:
        """Anahtar/onay yoksa hiç başlama — tek dış çıkış noktasının kapısı burası."""
        ai_cfg = self._ayarlar()
        if not ai_cfg.hazir:
            QMessageBox.warning(
                self, "Yapay Zekâ Ayarları Eksik",
                (ai_cfg.eksik() or "Yapay zekâ ayarları eksik.")
                + "\n\nÜstteki alandan API anahtarınızı girin ve veri paylaşım "
                  "onayını işaretleyin. Onay verilmeden hiçbir veri dışarı gönderilmez.")
            self._durum(ai_cfg.eksik(), "uyari")
            return
        if not self._aralik_onayi():
            return
        super()._on_getir()

    def _aralik_onayi(self) -> bool:
        """Aralık AZAMI_YIL'i aşıyorsa kullanıcıya sorar; kırpma _is_hazirla'da aynen olur."""
        yillar, dusen = yil_araligi(
            self._donem.bas_tarih().toString("yyyy-MM-dd"),
            self._donem.bit_tarih().toString("yyyy-MM-dd"))
        if not dusen or not yillar:
            return True
        return soru_evet_hayir(
            self, "Aralık Çok Geniş",
            f"Seçtiğiniz aralık {len(yillar) + dusen} yılı kapsıyor. Bu kadar veri yapay "
            f"zekânın yorumlama kapasitesini aşar ve yorumu yüzeyselleştirir.\n\n"
            f"En fazla {AZAMI_YIL} yıl yorumlanabilir. Son {AZAMI_YIL} yıl "
            f"({yillar[0]}–{yillar[-1]}) ile devam edilsin mi?\n\n"
            "Daha kısa bir aralık seçmek için «Hayır» deyin.")

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        ai_cfg = self._ayarlar()
        # Aralığın kapsadığı yıllar; en yeni yıl «odak» olur ve ham detayı o taşır.
        yillar, _ = yil_araligi(bas, bit)
        yil = yillar[-1] if yillar else int((bit or bas or "")[:4] or 0)
        yillar = yillar or [yil]
        # Odak yılın bitişi BUGÜNÜ AŞMAZ: yıl sürerken 31 Aralık'a kadar veri istemek,
        # modele yılın bittiğini düşündürüyordu («2026'yı 19,5M ile kapattı» — canlıda görüldü).
        bugun = date.today()
        yil_sonu = date(yil, 12, 31)
        y_son = min(yil_sonu, bugun)
        y_bas, y_bit = f"{yil}-01-01", y_son.isoformat()
        tamamlandi = yil_sonu <= bugun
        ay_sayisi = 12 if tamamlandi else y_son.month
        # Geçmiş bir yıl seçilmişse veri bugüne göre eskidir — model bugüne çekilmeli.
        gecikme_ay = ay_farki(y_bit, bugun.isoformat())
        # MUKAYESE SEÇİMDEN BAĞIMSIZ KURULUR: kullanıcı tek yıl seçtiğinde tablo hiç
        # oluşmuyordu ve model "geçmiş yıl verisi yok, trend analiz edilemiyor" diyordu
        # (canlıda görüldü). Yıllar arası kıyas her koşuda istenen bir şey; aralık dar
        # kalırsa geriye doğru AZAMI_YIL'e tamamlarız. Veritabanında olmayan yıllar
        # sessizce düşer (bkz. YilKapanis.dolu), sıfır satırı tabloya girmez.
        if len(yillar) < AZAMI_YIL:
            yillar = list(range(yil - AZAMI_YIL + 1, yil + 1))
        gecmis = [y for y in yillar if y != yil]
        gd_ayarlar = load_gercek_durum_ayarlar()

        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            firma = firma_getir(cfg, client)
            bolumler: list[tuple[str, str]] = []

            def ekle(baslik: str, uret) -> None:
                """Bir bölümü hesapla; okunamazsa raporu komple düşürmek yerine atla."""
                try:
                    icerik = uret()
                except (MikroAPIError, ValueError, KeyError, TypeError):
                    return
                if icerik and icerik.strip():
                    bolumler.append((baslik, icerik))

            bildir("Bilanço çekiliyor…")
            mizan = fetch_mizan(client, y_bit)
            bilanco = build_bilanco(mizan, asof=y_bit)
            ekle("BİLANÇO", lambda: bilanco_csv(bilanco))

            bildir("Gelir tablosu çekiliyor…")
            gt = build_gelir_tablosu(fetch_gelir_tablosu(client, y_bas, y_bit),
                                     bas=y_bas, bit=y_bit)
            ekle("GELİR TABLOSU", lambda: gelir_tablosu_csv(gt))

            # Geçmiş yıllar: ham kırılım DEĞİL, yalnız kapanış satırları. Üç sorgu/yıl.
            kapanislar: list[YilKapanis] = [_kapanis_kur(
                yil, tam=tamamlandi, b=bilanco, gt=gt,
                doviz=_doviz_dene(client, y_bas, y_bit))]
            for sira, g in enumerate(gecmis, 1):
                bildir(f"{g} yılı mukayese için çekiliyor… ({sira}/{len(gecmis)})")
                g_bas, g_bit = f"{g}-01-01", f"{g}-12-31"
                try:
                    gecmis_yil = _kapanis_kur(
                        g, tam=True,
                        b=build_bilanco(fetch_mizan(client, g_bit), asof=g_bit),
                        gt=build_gelir_tablosu(
                            fetch_gelir_tablosu(client, g_bas, g_bit),
                            bas=g_bas, bit=g_bit),
                        doviz=_doviz_dene(client, g_bas, g_bit))
                except (MikroAPIError, ValueError, KeyError, TypeError):
                    continue   # o yıl veritabanında yoksa sessizce atla
                if gecmis_yil.dolu:   # boş yıl sıfır satırı olarak tabloya girmesin
                    kapanislar.append(gecmis_yil)
            if len(kapanislar) > 1:
                ekle("YILLAR ARASI KARŞILAŞTIRMA", lambda: yillar_arasi_csv(kapanislar))

            bildir("Satış, alış ve nakit hareketleri çekiliyor…")
            stok = fetch_stok_ozet(client, y_bas, y_bit)
            stok_aylik = fetch_stok_aylik(client, y_bas, y_bit)
            nakit_rows, nakit_aylik = fetch_nakit_ozet_ve_aylik(client, y_bas, y_bit)
            gd = build_gercek_durum(
                stok_rows=stok, stok_aylik=stok_aylik,
                nakit_rows=nakit_rows, nakit_aylik=nakit_aylik,
                bas=y_bas, bit=y_bit, ayarlar=gd_ayarlar)
            ekle("NAKİT VE KÂRLILIK", lambda: gercek_durum_csv(gd))

            bildir("Alacak ve borç kalemleri çekiliyor…")
            ta = None
            try:
                ta = build_tahsilat_alacak(
                    fetch_acik_kalemler(client, y_bit, y_bas, y_bit),
                    vade_gun_map=fetch_cari_vade_gun(client),
                    bas=y_bas, bit=y_bit, top_n=_TUM_CARILER)
            except MikroAPIError:
                ta = None
            if ta is not None:
                ekle("ALACAK VE BORÇ (cari ünvanları dâhil)", lambda: tahsilat_alacak_csv(ta))

            bildir("Nakit akışı çekiliyor…")
            ekle("NAKİT AKIŞI", lambda: nakit_akis_csv(build_nakit_akis(
                fetch_nakit_akis_gl(client, y_bas, y_bit),
                kapanis_nakit=fetch_nakit_bakiye_gl(client, y_bit),
                donem_delta=fetch_nakit_delta_gl(client, y_bas, y_bit),
                bas=y_bas, bit=y_bit)))

            bildir("Trend ve oranlar hazırlanıyor…")
            ekle("TREND VE FİNANSAL ORANLAR", lambda: trend_csv(build_trend(
                aylik=gd.trend, bilanco=bilanco, bas=y_bas, bit=y_bit)))

            paket = build_ai_veri_paketi(
                yil=yil, bas=y_bas, bit=y_bit, firma=firma, bolumler=bolumler,
                bugun=bugun.isoformat(), tamamlandi=tamamlandi, ay_sayisi=ay_sayisi,
                gecikme_ay=gecikme_ay, calisma_yili=cfg.calisma_yili,
                yillar=[k.yil for k in kapanislar], kapanislar=kapanislar)
            yorum = yorumla(ai_cfg, paket, bildir=bildir)
            return {"yorum": yorum, "firma": firma}

        return is_fn

    def _on_hata(self, mesaj: str) -> None:
        """Yapay zekâ hataları «Mikro Hatası» başlığıyla çıkmasın; mesajı sadeleştir."""
        if self.sender() is not None and self.sender() is not self._worker:
            return
        temiz = mesaj.removeprefix("Beklenmeyen hata: ")
        if getattr(self, "_yukleniyor", None) is not None:
            self._yukleniyor.durdur()
            self._stack.setCurrentIndex(1 if self._rapor_var else 0)
        self._durum("Yorum alınamadı.", "hata")
        QMessageBox.warning(self, "Yapay Zekâ Hatası", temiz)

    def _goster(self, sonuc: dict[str, Any]) -> None:
        y: AiYorum = sonuc["yorum"]
        self._y = y
        self._firma = sonuc["firma"]
        self._icerik_koy(build_ai_yorum_widget(y, firma=self._firma))
        kayit = self._ayarlar()
        kayit.model = y.model          # bir dahaki sefere yedek olarak dursun
        save_ai_config(kayit)
        ilk_yil = (y.aralik_bas or "")[:4]
        kapsam = f"{ilk_yil}–{y.yil}" if ilk_yil and ilk_yil != str(y.yil) else str(y.yil)
        self._durum(
            f"{kapsam} yorumlandı · {y.saglayici} · {y.model} · "
            f"{y.toplam_token:,} token".replace(",", "."), "iyi")

    # ------------------------------------------------------------------ dışa aktar
    def _on_pdf(self) -> None:
        if not self._y:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet",
            varsayilan_kayit_yolu(f"{self._slug}_{self._y.yil}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            export_ai_yorum_pdf(self._y, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"{self._slug}_{self._y.yil}.csv" if self._y else f"{self._slug}.csv"

    def _csv_icerik(self) -> str | None:
        return ai_yorum_csv(self._y) if self._y else None
