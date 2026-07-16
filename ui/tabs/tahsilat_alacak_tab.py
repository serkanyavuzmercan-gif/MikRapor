"""Tahsilat & Alacak sekmesi — cari hareketten yaşlandırma, vade takvimi, performans."""

from __future__ import annotations

from typing import Any

from domain.mizan_bilanco import tl
from domain.tahsilat_alacak import TahsilatAlacak, build_tahsilat_alacak, tahsilat_alacak_csv
from infra.config import MikroConfig
from infra.mikro_api import MikroClient
from infra.mikro_fetch import fetch_acik_kalemler, fetch_cari_vade_gun
from ui.rapor_tab import RaporTab, firma_getir
from ui.tahsilat_alacak_view import build_tahsilat_alacak_widget
from ui.worker import IsFonksiyonu


class TahsilatAlacakTab(RaporTab):
    """Cari hareketten alacak/borç yaşlandırma, vade takvimi ve tahsilat performansı sekmesi."""

    EMOJI = "📒"
    BASLIK = "Tahsilat & Alacak"
    ACIKLAMA = (
        "Cari hareketlerden — açık alacak ve borçların vadeye göre yaşlandırması,<br>"
        "dönem tahsilat/ödeme performansı (DSO/DPO) ve ileriye dönük net vade<br>"
        "takvimi (ne girecek − ne çıkacak). Resmi GL'ye dokunmaz.")
    GETIR_ETIKET = "Tahsilat && Alacak Getir"
    BASLARKEN = "Cari açık kalemler çekiliyor…"

    _ta: TahsilatAlacak | None = None

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            bildir("Cari ödeme planları çekiliyor…")
            vade_gun_map = fetch_cari_vade_gun(client)
            bildir("Cari açık kalemler çekiliyor…")
            acik_rows = fetch_acik_kalemler(client, bit, bas, bit)
            bildir("Yaşlandırma kuruluyor…")
            ta = build_tahsilat_alacak(acik_rows, vade_gun_map=vade_gun_map, bas=bas, bit=bit)
            return {"ta": ta, "firma": firma_getir(cfg, client)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        ta: TahsilatAlacak = sonuc["ta"]
        self._ta = ta
        self._firma = sonuc["firma"]
        self._icerik_koy(build_tahsilat_alacak_widget(ta, firma=self._firma))
        parts = [
            f"{ta.cari_sayisi} cari hesap",
            f"Alacak {tl(ta.alacak_toplam)} (gecikmiş {tl(ta.alacak_gecikmis)})",
            f"Borç {tl(ta.borc_toplam)}",
        ]
        if ta.dso is not None:
            parts.append(f"DSO {ta.dso:.0f}g")
        if ta.cari_sayisi == 0:
            parts.insert(0, "⚠ açık bakiye yok — dönem/yıl kontrol edin")
        self._durum(
            " · ".join(parts),
            "uyari" if ta.cari_sayisi == 0 else
            ("hata" if ta.alacak_gecikmis > 0.005 else "iyi"),
        )

    def _csv_dosya_adi(self) -> str:
        return f"tahsilat_alacak_{self._ta.bas}_{self._ta.bit}.csv" if self._ta else "tahsilat_alacak.csv"

    def _csv_icerik(self) -> str | None:
        return tahsilat_alacak_csv(self._ta) if self._ta else None
