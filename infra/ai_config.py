"""
Yapay zekâ yorumu ayarları — API anahtarı (şifreli) + veri paylaşım onayı.

MikRapor kapalı devre çalışır: Mikro sunucusu dışında hiçbir yere veri gitmez.
TEK istisna bu modüldür. Dışarıya çıkış yalnız iki koşul birlikte sağlanırsa olur:
  1) kullanıcı kendi API anahtarını girmiştir,
  2) `onay = True` — veri paylaşımını açıkça onaylamıştır.
Onay geri alınabilir; alındığında anahtar dursa bile çağrı yapılmaz.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from infra import gizli
from infra.ai_saglayici import VARSAYILAN_SAGLAYICI, Saglayici, saglayici_bul
from infra.config import _read_config_data, save_config_data

# Anahtar adı config.json içinde; Mikro ayarlarıyla karışmasın diye ayrı bölüm.
_BOLUM = "yapay_zeka"

# Model adı HARDCODE EDİLMEZ — «Modelleri Getir» ile sağlayıcıdan canlı çekilir ve
# burada önbelleklenir (bkz. infra/ai_saglayici.py). Böylece yarın çıkan bir model,
# program güncellenmeden seçilebilir. Kullanıcı adı elle de yazabilir.

# Onay metni tek kaynak: ekranda gösterilen ile kaydedilen aynı olsun.
ONAY_METNI = (
    "Bilgilerimin, ayarlarda girdiğim API anahtarına ait yapay zekâ dil modeli ile "
    "paylaşılmasını onaylıyorum."
)

# Kullanıcıya ne gittiğini gizlemeyen açık uyarı (onay kutusunun altında gösterilir).
PAYLASIM_UYARISI = (
    "Seçili yılın <b>tüm rapor verisi ham olarak</b> gönderilir: müşteri ve tedarikçi "
    "ünvanları, muhasebe hesap kodları, alacak/borç yaşlandırma kırılımları, banka ve "
    "kredi hareketleri dâhil. Gönderim yalnız «Yorumla ve Gönder» düğmesine bastığınızda yapılır; "
    "onay kaldırılırsa hiçbir veri dışarı çıkmaz."
)


@dataclass
class AiConfig:
    """
    Yapay zekâ yorumu ayarları.

    Anahtar SAĞLAYICI BAŞINA saklanır: kullanıcı Claude ile Gemini arasında geçiş
    yaparken anahtarını yeniden girmek zorunda kalmasın. Onay tektir ve tüm
    sağlayıcılar için geçerlidir (veri paylaşımı kararı sağlayıcıdan bağımsızdır).
    """

    saglayici: str = VARSAYILAN_SAGLAYICI
    api_key: str = ""
    onay: bool = False
    model: str = ""
    ozel_base_url: str = ""
    # Sağlayıcıdan çekilmiş son model listesi (çevrimdışı açılışta kutuyu doldurur).
    model_listesi: list[str] = field(default_factory=list)
    # Sağlayıcı kodu → şifreli olmayan anahtar (bellekte); diske şifreli yazılır.
    anahtarlar: dict[str, str] = field(default_factory=dict)

    def normalized(self) -> AiConfig:
        sag = saglayici_bul(self.saglayici).kod
        anahtarlar = {
            str(k): str(v or "").strip()
            for k, v in (self.anahtarlar or {}).items() if str(v or "").strip()
        }
        anahtar = (self.api_key or "").strip() or anahtarlar.get(sag, "")
        if anahtar:
            anahtarlar[sag] = anahtar
        return AiConfig(
            saglayici=sag,
            api_key=anahtar,
            onay=bool(self.onay),
            model=(self.model or "").strip(),
            ozel_base_url=(self.ozel_base_url or "").strip().rstrip("/"),
            model_listesi=[str(m).strip() for m in (self.model_listesi or []) if str(m).strip()],
            anahtarlar=anahtarlar,
        )

    @property
    def saglayici_bilgi(self) -> Saglayici:
        return saglayici_bul(self.saglayici)

    @property
    def etkin_base_url(self) -> str:
        """Kullanılacak adres — «Özel» sağlayıcıda kullanıcının girdiği."""
        s = self.saglayici_bilgi
        return (self.ozel_base_url or s.base_url).rstrip("/") if s.ozel_mi else s.base_url

    def anahtar_al(self, saglayici_kod: str) -> str:
        """Belirli bir sağlayıcı için kayıtlı anahtar (sekme değişince geri yüklenir)."""
        return (self.anahtarlar or {}).get(saglayici_kod, "")

    @property
    def hazir(self) -> bool:
        """Dışarıya çağrı yapılabilir mi — anahtar, model, onay (ve özelde adres) şart."""
        return not self.eksik()

    def eksik(self) -> str:
        """Hazır değilse kullanıcıya gösterilecek tek cümlelik sebep."""
        if not (self.api_key or "").strip():
            return "API anahtarı girilmemiş."
        if self.saglayici_bilgi.ozel_mi and not self.ozel_base_url:
            return "Özel sağlayıcı için adres (base URL) girilmemiş."
        if not (self.model or "").strip():
            return "Model seçilmemiş — «Modelleri Getir»e basın ya da adı elle yazın."
        if not self.onay:
            return "Veri paylaşım onayı verilmemiş."
        return ""


def load_ai_config() -> AiConfig:
    """config.json «yapay_zeka» bölümünü okur; anahtarlar şifreliyse çözer."""
    ham = _read_config_data().get(_BOLUM)
    if not isinstance(ham, dict):
        return AiConfig()
    try:
        anahtarlar = {
            str(k): gizli.coz(str(v or ""))
            for k, v in (ham.get("anahtarlar") or {}).items()
        }
        cfg = AiConfig(
            saglayici=str(ham.get("saglayici", "") or VARSAYILAN_SAGLAYICI),
            api_key=gizli.coz(str(ham.get("api_key", "") or "")),
            onay=bool(ham.get("onay", False)),
            model=str(ham.get("model", "") or ""),
            ozel_base_url=str(ham.get("ozel_base_url", "") or ""),
            model_listesi=list(ham.get("model_listesi") or []),
            anahtarlar=anahtarlar,
        )
        return cfg.normalized()
    except (TypeError, ValueError):
        return AiConfig()


def save_ai_config(cfg: AiConfig) -> None:
    """Ayarları kaydeder; anahtarlar Mikro şifresiyle aynı yolla (DPAPI/yerel) şifrelenir."""
    data = _read_config_data()
    kayit = asdict(cfg.normalized())
    kayit["api_key"] = gizli.sifrele(kayit["api_key"])
    kayit["anahtarlar"] = {k: gizli.sifrele(v) for k, v in kayit["anahtarlar"].items()}
    data[_BOLUM] = kayit
    save_config_data(data)
