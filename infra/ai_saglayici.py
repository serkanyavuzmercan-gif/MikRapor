"""
Yapay zekâ sağlayıcıları — kayıt defteri ve canlı model listesi.

TASARIM: model adları HARDCODE EDİLMEZ. Yeni bir dil modeli çıktığında programı
güncellemek gerekmesin diye liste, sağlayıcının kendi `GET /models` ucundan canlı
çekilir ve ayarlara önbelleklenir. Kullanıcı listede olmayan bir modeli elle de
yazabilir (düzenlenebilir kutu) — uç nokta yeni modeli henüz döndürmese bile çalışır.

İki istek şeması vardır:
  • "openai"    — OpenAI uyumlu /chat/completions (OpenAI, Google, DeepSeek, Groq, xAI…)
  • "anthropic" — Anthropic Messages API (resmi SDK ile)
Çoğu sağlayıcı OpenAI uyumlu olduğu için yeni bir sağlayıcı eklemek genelde tek satır;
listede olmayanlar için «Özel» seçilip base URL elle girilebilir.

Ağ katmanı stdlib urllib'dir (mikro_api ile aynı ilke: yeni bağımlılık yok).
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

# Anthropic Messages API sürüm başlığı (zorunlu).
_ANTHROPIC_SURUM = "2023-06-01"

_ZAMAN_ASIMI = 20


@dataclass(frozen=True)
class Saglayici:
    """Bir yapay zekâ sağlayıcısının bağlantı tarifi."""

    kod: str
    ad: str
    base_url: str
    sema: str            # "openai" | "anthropic"
    anahtar_ipucu: str
    anahtar_url: str

    @property
    def ozel_mi(self) -> bool:
        return self.kod == "ozel"


SAGLAYICILAR: tuple[Saglayici, ...] = (
    Saglayici("anthropic", "Anthropic — Claude", "https://api.anthropic.com/v1",
              "anthropic", "sk-ant-…", "https://console.anthropic.com/settings/keys"),
    Saglayici("openai", "OpenAI — GPT", "https://api.openai.com/v1",
              "openai", "sk-…", "https://platform.openai.com/api-keys"),
    Saglayici("google", "Google — Gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
              "openai", "AIza…", "https://aistudio.google.com/apikey"),
    Saglayici("deepseek", "DeepSeek", "https://api.deepseek.com",
              "openai", "sk-…", "https://platform.deepseek.com/api_keys"),
    Saglayici("groq", "Groq — ücretsiz kotalı", "https://api.groq.com/openai/v1",
              "openai", "gsk_…", "https://console.groq.com/keys"),
    Saglayici("xai", "xAI — Grok", "https://api.x.ai/v1",
              "openai", "xai-…", "https://console.x.ai"),
    Saglayici("ozel", "Özel (OpenAI uyumlu adres)", "",
              "openai", "", ""),
)

_HARITA = {s.kod: s for s in SAGLAYICILAR}
VARSAYILAN_SAGLAYICI = "anthropic"


def saglayici_bul(kod: str) -> Saglayici:
    """Koda göre sağlayıcı; bilinmiyorsa varsayılana düşer."""
    return _HARITA.get((kod or "").strip(), _HARITA[VARSAYILAN_SAGLAYICI])


class ModelListesiHatasi(Exception):
    """Model listesi çekilemedi — kullanıcıya gösterilebilir mesaj."""


def _istek(url: str, basliklar: dict[str, str]) -> dict:
    istek = urllib.request.Request(url, headers=basliklar, method="GET")  # noqa: S310 - https şart
    if not url.lower().startswith("https://"):
        raise ModelListesiHatasi("Adres https:// ile başlamalı.")
    try:
        with urllib.request.urlopen(istek, timeout=_ZAMAN_ASIMI,  # noqa: S310
                                    context=ssl.create_default_context()) as yanit:
            return json.loads(yanit.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ModelListesiHatasi("API anahtarı geçersiz veya yetkisiz.") from exc
        if exc.code == 404:
            raise ModelListesiHatasi(
                "Bu adreste model listesi ucu yok. Base URL'i kontrol edin.") from exc
        raise ModelListesiHatasi(f"Sağlayıcı hata verdi (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise ModelListesiHatasi(f"Bağlantı kurulamadı: {exc.reason}") from exc
    except (TimeoutError, ValueError) as exc:
        raise ModelListesiHatasi(f"Yanıt okunamadı: {exc}") from exc


def modelleri_getir(saglayici: Saglayici, api_key: str, base_url: str = "") -> list[str]:
    """
    Sağlayıcının canlı model listesini döndürür (alfabetik, tekrarsız).

    Hardcode edilmiş liste yoktur: yarın çıkan model, program güncellenmeden burada
    görünür. Uç nokta desteklenmiyorsa ModelListesiHatasi yükselir; kullanıcı model
    adını elle yazmaya devam edebilir.
    """
    anahtar = (api_key or "").strip()
    if not anahtar:
        raise ModelListesiHatasi("Önce API anahtarını girin.")
    kok = (base_url or saglayici.base_url or "").strip().rstrip("/")
    if not kok:
        raise ModelListesiHatasi("Base URL boş — «Özel» sağlayıcıda adresi girmelisiniz.")

    if saglayici.sema == "anthropic":
        basliklar = {"x-api-key": anahtar, "anthropic-version": _ANTHROPIC_SURUM}
    else:
        basliklar = {"Authorization": f"Bearer {anahtar}"}

    veri = _istek(f"{kok}/models", basliklar)
    ham = veri.get("data") if isinstance(veri, dict) else None
    if not isinstance(ham, list):
        ham = veri.get("models") if isinstance(veri, dict) else None
    if not isinstance(ham, list):
        raise ModelListesiHatasi("Sağlayıcı beklenmeyen bir yanıt verdi.")

    modeller: set[str] = set()
    for m in ham:
        if isinstance(m, str):
            modeller.add(m.strip())
        elif isinstance(m, dict):
            kimlik = m.get("id") or m.get("name") or ""
            if isinstance(kimlik, str) and kimlik.strip():
                # Google "models/gemini-…" biçiminde döndürür; ön eki temizle.
                modeller.add(kimlik.strip().removeprefix("models/"))
    if not modeller:
        raise ModelListesiHatasi("Sağlayıcı hiç model döndürmedi.")
    return sorted(modeller)
