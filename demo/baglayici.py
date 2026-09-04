"""
Demo yamalarını kuran tek yer.

NEDEN `sys.modules` SÜPÜRÜLÜYOR: sekmeler veriyi `from infra.mikro_fetch import
fetch_mizan` diye MODÜL SEVİYESİNDE bağlıyor (ör. `ui/tabs/bilanco_tab.py:12`).
Bu bağ import anında kurulduğu için `infra.mikro_fetch.fetch_mizan`'ı sonradan
değiştirmek o sekmeyi ETKİLEMEZ. Yama, adı bağlayan HER modülün kendi ad alanına
gitmek zorunda — ve bu yalnız `ui.tabs.*` değil:

    ui/rapor_tab.py:31          fetch_firma_adi   (her sekmenin tabanı)
    ui/nakit_detay_dialog.py:32 fetch_nakit_akis_detay
    ui/veri_sagligi_dialog.py   teşhis fetch'leri
    ui/gercek_durum_settings_dialog.py, ui/mikro_settings_dialog.py
    infra/mukayese_fetch.py     donem_* yardımcılarının kendi çağırdıkları

Elle liste tutmak yerine `ui.*` ve `infra.*` altındaki yüklü her modülde, demo
kaydındaki adla aynı ada sahip niteliği değiştiririz. Yeni bir sekme yeni bir
fetch bağlarsa kayda eklemek yeter; liste bakımı bir yerde birikir.

YARDIMCILAR YENİDEN YAZILMAZ: `donem_satirlari(cfg, bas, bit, cek, …)` yüksek
mertebeden — çağıran zaten demo fetch'i veriyor. Kural 1'in yıl parçalama mantığını
demoda ikinci kez yazmak, CLAUDE.md'nin «aynı eleme iki yere» dediği hatanın ta
kendisi olurdu. Yalnız `yil_client` nötrlenir.

KULLANICININ GERÇEK KURULUMU KİRLENMEZ: `config_dir` geçici klasöre çevrilir, yani
ayar penceresinin «Kaydet»i de, premium önbelleği de oraya yazar. Premium
`ui.premium` üzerinden açılır; `infra.store_lisans.lisans_durumu` SAHİP döndürmek
YASAK — o yol `premium_onbellek_yaz()` çağırır ve kural 8 gereği kullanıcının
gerçek config'ini KALICI premium yapardı.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

from demo import fetch as demo_fetch
from demo.defter import FIRMA_ADI, ILK_AY, SON_AY

# Demo karşılığı olan adlar — ad → fonksiyon.
KAYIT: dict[str, Any] = {
    ad: getattr(demo_fetch, ad)
    for ad in dir(demo_fetch)
    if ad.startswith("fetch_") and callable(getattr(demo_fetch, ad))
}


class SahteClient:
    """`yil_client`in döndürdüğü nesne. Demo fetch'leri client'a DOKUNMAZ."""

    def __init__(self, yil: int = 0) -> None:
        self.yil = yil

    def ping(self) -> None:
        return None

    def sql_veri_oku(self, *_a: Any, **_k: Any) -> list[dict[str, Any]]:
        # Buraya düşmek, demoda karşılığı olmayan bir fetch'in çağrıldığı anlamına
        # gelir. Sessiz boş liste dönmek ekranı «veri yok» gösterip sebebi gizlerdi.
        raise RuntimeError(
            "Demo modunda ham SQL çalıştırılamaz — bu fetch'in demo karşılığı yok. "
            "demo/fetch.py'ye ekleyin.")


def demo_cfg() -> Any:
    from infra.config import MikroConfig
    return MikroConfig(
        base_url="https://demo.gecersiz.local",
        api_key="demo",
        firma_kodu="20",
        firma_kodlari="20",
        kullanici_kodu="DEMO",
        sifre_gun="demo",
        firma_adi=FIRMA_ADI,
    )


def _yamala_modulleri(kayit: dict[str, Any]) -> int:
    """Yüklü `ui.*` / `infra.*` modüllerinde kayıttaki adları değiştirir."""
    sayi = 0
    for ad, modul in list(sys.modules.items()):
        if modul is None or not (ad.startswith(("ui.", "infra.")) or ad in ("ui", "infra")):
            continue
        if ad.startswith("demo"):
            continue
        for isim, yeni in kayit.items():
            if hasattr(modul, isim):
                setattr(modul, isim, yeni)
                sayi += 1
    return sayi


def _premium_ac() -> None:
    """
    Premium kilidini bu OTURUM için açar — önbelleğe YAZMADAN.

    Kilit hangi şeye takılıyorsa (sekme, PDF/CSV çıktısı) karar `premium_durumu`
    kapısından geçtiği sürece demo çalışır; bölünme değişse de burası değişmez.
    """
    from dataclasses import dataclass

    from domain.lisans import LisansDurumu
    from ui import premium as premium_mod

    @dataclass(frozen=True)
    class _Acik:
        acik: bool = True
        kaynak: LisansDurumu = LisansDurumu.SAHIP

    durum = _Acik()
    premium_mod._durum = durum                       # noqa: SLF001
    premium_mod.premium_durumu = lambda yenile=False: durum  # type: ignore[assignment]
    _yamala_modulleri({"premium_durumu": premium_mod.premium_durumu})


def _ai_yamala() -> None:
    """Yapay Zekâ sekmesi ağ çağrısı YAPMAZ; kurgu bir yönetim yorumu döner."""
    from demo.metin import DEMO_AI_METNI
    from domain.ai_yorum import AiYorum

    def sahte_yorumla(cfg: Any, paket: Any, *, bildir: Any = None) -> AiYorum:
        if bildir:
            bildir("Demo yorumu hazırlanıyor…")
        return AiYorum(
            metin=DEMO_AI_METNI,
            model="demo-model",
            saglayici="Demo",
            yil=getattr(paket, "yil", 0),
            bas=getattr(paket, "bas", ""),
            bit=getattr(paket, "bit", ""),
            firma=FIRMA_ADI,
            girdi_token=18_450,
            cikti_token=1_120,
            veri_ozeti=getattr(paket, "ozet", "") or "",
            kapanislar=list(getattr(paket, "kapanislar", []) or []),
        )

    import infra.ai_client as ai_client
    ai_client.yorumla = sahte_yorumla  # type: ignore[assignment]
    _yamala_modulleri({"yorumla": sahte_yorumla})


def _config_izole_et() -> Path:
    """Gerçek %APPDATA%\\MikRapor'a hiçbir şey yazılmasın."""
    import infra.config as config_mod

    klasor = Path(tempfile.gettempdir()) / "mikrapor-demo"
    klasor.mkdir(parents=True, exist_ok=True)
    config_mod.config_dir = lambda: klasor  # type: ignore[assignment]
    cfg = demo_cfg()
    config_mod.load_config = lambda: cfg    # type: ignore[assignment]
    _yamala_modulleri({"load_config": config_mod.load_config})
    return klasor


def _veritabani_yamala() -> None:
    import infra.veritabani as vt
    from infra.veritabani import FirmaKapsami

    kapsam = [FirmaKapsami(firma_kodu="20", ilk_yil=ILK_AY.year, son_yil=SON_AY.year)]
    vt.katalog = lambda cfg, *, yenile=False: kapsam        # type: ignore[assignment]
    vt.firma_kodlari = lambda cfg: ["20"]                   # type: ignore[assignment]
    vt.firma_client = lambda cfg, firma_kodu: SahteClient()  # type: ignore[assignment]

    import infra.mukayese_fetch as mf
    mf.yil_client = lambda cfg, yil: SahteClient(yil)       # type: ignore[assignment]

    from infra.mikro_api import MikroClient
    MikroClient.ping = lambda self: None                    # type: ignore[assignment]

    _yamala_modulleri({
        "katalog": vt.katalog,
        "firma_kodlari": vt.firma_kodlari,
        "yil_client": mf.yil_client,
    })


def demo_moduna_gec() -> None:
    """Bütün yamaları kurar. `ui.app` import EDİLDİKTEN sonra çağrılmalıdır."""
    _config_izole_et()
    _veritabani_yamala()
    _yamala_modulleri(KAYIT)
    _premium_ac()
    _ai_yamala()
