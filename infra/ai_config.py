"""
Yapay zekâ yorumu ayarları — API anahtarı (şifreli) + veri paylaşım onayı.

MikRapor kapalı devre çalışır: Mikro sunucusu dışında hiçbir yere veri gitmez.
TEK istisna bu modüldür. Dışarıya çıkış yalnız iki koşul birlikte sağlanırsa olur:
  1) kullanıcı kendi API anahtarını girmiştir,
  2) `onay = True` — veri paylaşımını açıkça onaylamıştır.
Onay geri alınabilir; alındığında anahtar dursa bile çağrı yapılmaz.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from infra import gizli
from infra.config import _read_config_data, save_config_data

# Anahtar adı config.json içinde; Mikro ayarlarıyla karışmasın diye ayrı bölüm.
_BOLUM = "yapay_zeka"

# Varsayılan model — Anthropic'in en yetenekli modeli (bkz. MIKRAPOR-AI-NOTLARI).
VARSAYILAN_MODEL = "claude-opus-5"

MODEL_SECENEKLERI: tuple[tuple[str, str], ...] = (
    ("claude-opus-5", "Claude Opus 5 — en yetenekli (önerilen)"),
    ("claude-sonnet-5", "Claude Sonnet 5 — hızlı ve ekonomik"),
)

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
    """Yapay zekâ yorumu ayarları."""

    api_key: str = ""
    onay: bool = False
    model: str = VARSAYILAN_MODEL

    def normalized(self) -> AiConfig:
        model = (self.model or "").strip() or VARSAYILAN_MODEL
        gecerli = {kod for kod, _ in MODEL_SECENEKLERI}
        return AiConfig(
            api_key=(self.api_key or "").strip(),
            onay=bool(self.onay),
            model=model if model in gecerli else VARSAYILAN_MODEL,
        )

    @property
    def hazir(self) -> bool:
        """Dışarıya çağrı yapılabilir mi — anahtar VE onay birlikte şart."""
        return bool((self.api_key or "").strip()) and bool(self.onay)

    def eksik(self) -> str:
        """Hazır değilse kullanıcıya gösterilecek tek cümlelik sebep."""
        if not (self.api_key or "").strip():
            return "API anahtarı girilmemiş."
        if not self.onay:
            return "Veri paylaşım onayı verilmemiş."
        return ""


def load_ai_config() -> AiConfig:
    """config.json «yapay_zeka» bölümünü okur; anahtar şifreliyse çözer."""
    ham = _read_config_data().get(_BOLUM)
    if not isinstance(ham, dict):
        return AiConfig()
    try:
        return AiConfig(
            api_key=gizli.coz(str(ham.get("api_key", "") or "")),
            onay=bool(ham.get("onay", False)),
            model=str(ham.get("model", "") or ""),
        ).normalized()
    except (TypeError, ValueError):
        return AiConfig()


def save_ai_config(cfg: AiConfig) -> None:
    """Ayarları kaydeder; anahtar Mikro şifresiyle aynı yolla (DPAPI/yerel) şifrelenir."""
    data = _read_config_data()
    kayit = asdict(cfg.normalized())
    kayit["api_key"] = gizli.sifrele(kayit["api_key"])
    data[_BOLUM] = kayit
    save_config_data(data)
