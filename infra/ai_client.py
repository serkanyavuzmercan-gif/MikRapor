"""
Yapay zekâ istemcisi — MikRapor'un TEK dış çıkış noktası.

Mikro sunucusu dışında ağa çıkan başka modül yoktur. Buradaki çağrı da yalnız
kullanıcı anahtarını girmiş, modelini seçmiş VE veri paylaşımını onaylamışsa yapılır;
`yorumla()` bunu her seferinde yeniden doğrular (savunmacı — çağıran taraf unutsa bile).

İki istek şeması desteklenir (bkz. infra/ai_saglayici.py):
  • "anthropic" — resmi Anthropic SDK (akışlı, uyarlanır düşünme)
  • "openai"    — OpenAI uyumlu /chat/completions; OpenAI, Google Gemini, DeepSeek,
                  Groq, xAI ve aynı sözleşmeyi konuşan her sağlayıcı buradan geçer.
OpenAI uyumlu tarafta stdlib urllib kullanılır (mikro_api ile aynı ilke: sağlayıcı
başına yeni bağımlılık eklemeyiz, PyInstaller derlemesi sade kalır).
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable

from domain.ai_yorum import SISTEM_PROMPT, AiVeriPaketi, AiYorum
from infra.ai_config import AiConfig

# Yorum uzun olabilir (5 bölüm, madde madde); rahat bir tavan.
_MAX_TOKEN = 8000

# Girdi tavanı: ham paket çok büyükse SESSİZCE KIRPMA — kullanıcıya söyle.
MAX_GIRDI_KARAKTER = 1_500_000

_ANTHROPIC_SURUM = "2023-06-01"
_ZAMAN_ASIMI = 600  # uzun girdi + uzun çıktı; sağlayıcılar yavaş olabilir


class AiHata(Exception):
    """Yapay zekâ çağrısında kullanıcıya gösterilebilir hata."""


# --------------------------------------------------------------------- ortak kapı
def _kapi(cfg: AiConfig, paket: AiVeriPaketi) -> AiConfig:
    """Onay/anahtar/model/boyut kontrolleri — geçmezse HİÇBİR ağ çağrısı yapılmaz."""
    cfg = cfg.normalized()
    if not cfg.hazir:
        raise AiHata(cfg.eksik() or "Yapay zekâ ayarları eksik.")
    if not paket.bolumler:
        raise AiHata("Gönderilecek rapor verisi yok — önce raporları getirin.")
    if paket.karakter_sayisi > MAX_GIRDI_KARAKTER:
        raise AiHata(
            f"Veri paketi çok büyük ({paket.karakter_sayisi:,} karakter). ".replace(",", ".")
            + "Daha dar bir dönem seçin.")
    return cfg


def yorumla(
    cfg: AiConfig,
    paket: AiVeriPaketi,
    *,
    bildir: Callable[[str], None] | None = None,
) -> AiYorum:
    """Veri paketini seçili sağlayıcının modeline gönderip yorumu döndürür."""
    cfg = _kapi(cfg, paket)
    if bildir:
        bildir(f"{cfg.saglayici_bilgi.ad} modeline gönderiliyor…")

    if cfg.saglayici_bilgi.sema == "anthropic":
        metin, girdi, cikti = _anthropic_cagir(cfg, paket, bildir)
    else:
        metin, girdi, cikti = _openai_cagir(cfg, paket, bildir)

    if not metin.strip():
        raise AiHata("Yapay zekâdan boş yanıt geldi. Tekrar deneyin.")
    return AiYorum(
        metin=metin.strip(), model=cfg.model, yil=paket.yil, bas=paket.bas, bit=paket.bit,
        firma=paket.firma, girdi_token=girdi, cikti_token=cikti,
        veri_ozeti=paket.ozet_satiri(), saglayici=cfg.saglayici_bilgi.ad,
    )


# ------------------------------------------------------------------- Anthropic
def _anthropic_cagir(cfg: AiConfig, paket: AiVeriPaketi,
                     bildir: Callable[[str], None] | None) -> tuple[str, int, int]:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - paket kuruluysa gerçekleşmez
        raise AiHata("Anthropic kütüphanesi bulunamadı. Kurulum: pip install anthropic") from exc

    client = anthropic.Anthropic(api_key=cfg.api_key)
    try:
        with client.messages.stream(
            model=cfg.model,
            max_tokens=_MAX_TOKEN,
            system=SISTEM_PROMPT,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": paket.metin}],
        ) as akis:
            for _ in akis.text_stream:
                if bildir:
                    bildir("Yorum yazılıyor…")
            mesaj = akis.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise AiHata("API anahtarı geçersiz. Ayarlardan kontrol edin.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AiHata("API anahtarının bu modele erişim yetkisi yok.") from exc
    except anthropic.NotFoundError as exc:
        raise AiHata(f"Model bulunamadı: {cfg.model}") from exc
    except anthropic.RateLimitError as exc:
        raise AiHata("Servis yoğun (kota/limit). Birazdan tekrar deneyin.") from exc
    except anthropic.APIConnectionError as exc:
        raise AiHata("Servise bağlanılamadı. İnternet bağlantısını kontrol edin.") from exc
    except anthropic.APIStatusError as exc:
        raise AiHata(f"Servis hata verdi (HTTP {exc.status_code}).") from exc

    # Güvenlik sınıflandırıcısı reddettiyse içerik okumadan önce bak.
    if getattr(mesaj, "stop_reason", "") == "refusal":
        raise AiHata("Model bu içeriği yorumlamayı reddetti. Veriyi daraltıp tekrar deneyin.")

    metin = "\n".join(b.text for b in mesaj.content if getattr(b, "type", "") == "text")
    k = getattr(mesaj, "usage", None)
    return metin, int(getattr(k, "input_tokens", 0) or 0), int(getattr(k, "output_tokens", 0) or 0)


# --------------------------------------------------------------- OpenAI uyumlu
def _openai_cagir(cfg: AiConfig, paket: AiVeriPaketi,
                  bildir: Callable[[str], None] | None) -> tuple[str, int, int]:
    kok = cfg.etkin_base_url.rstrip("/")
    if not kok.lower().startswith("https://"):
        raise AiHata("Sağlayıcı adresi https:// ile başlamalı.")
    if bildir:
        bildir("Yorum yazılıyor…")

    govde = json.dumps({
        "model": cfg.model,
        "max_tokens": _MAX_TOKEN,
        "messages": [
            {"role": "system", "content": SISTEM_PROMPT},
            {"role": "user", "content": paket.metin},
        ],
    }).encode("utf-8")
    istek = urllib.request.Request(  # noqa: S310 - https yukarıda doğrulandı
        f"{kok}/chat/completions", data=govde, method="POST",
        headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(istek, timeout=_ZAMAN_ASIMI,  # noqa: S310
                                    context=ssl.create_default_context()) as yanit:
            veri = json.loads(yanit.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise AiHata(_http_mesaj(exc, cfg.model)) from exc
    except urllib.error.URLError as exc:
        raise AiHata(f"Servise bağlanılamadı: {exc.reason}") from exc
    except (TimeoutError, ValueError) as exc:
        raise AiHata(f"Yanıt okunamadı: {exc}") from exc

    secenekler = veri.get("choices") or []
    if not secenekler:
        hata = (veri.get("error") or {}).get("message") if isinstance(veri, dict) else ""
        raise AiHata(f"Servis yanıt döndürmedi. {hata or ''}".strip())
    metin = ((secenekler[0].get("message") or {}).get("content")) or ""
    if isinstance(metin, list):  # bazı sağlayıcılar parça listesi döndürür
        metin = "".join(p.get("text", "") for p in metin if isinstance(p, dict))
    k = veri.get("usage") or {}
    return str(metin), int(k.get("prompt_tokens") or 0), int(k.get("completion_tokens") or 0)


def _http_mesaj(exc: urllib.error.HTTPError, model: str) -> str:
    """HTTP hatasını Türkçeleştirir; gövdedeki açıklamayı da ekler (sağlayıcılar farklı yazar)."""
    try:
        ayrinti = (json.loads(exc.read().decode("utf-8", "replace")).get("error") or {}).get("message", "")
    except (ValueError, AttributeError, OSError):
        ayrinti = ""
    if exc.code in (401, 403):
        return "API anahtarı geçersiz veya yetkisiz."
    if exc.code == 404:
        return f"Model bulunamadı: {model}. «Modelleri Getir» ile listeyi tazeleyin."
    if exc.code == 429:
        return "Servis yoğun veya kota doldu. Birazdan tekrar deneyin."
    return f"Servis hata verdi (HTTP {exc.code}). {ayrinti}".strip()
