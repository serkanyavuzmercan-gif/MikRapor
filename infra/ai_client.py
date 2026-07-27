"""
Yapay zekâ (Anthropic) istemcisi — MikRapor'un TEK dış çıkış noktası.

Mikro sunucusu dışında ağa çıkan başka modül yoktur. Buradaki çağrı da yalnız
kullanıcı hem API anahtarını girmiş HEM de veri paylaşımını onaylamışsa yapılır;
`yorumla()` bunu her seferinde yeniden doğrular (savunmacı — çağıran taraf unutsa bile).

Uzun girdi ve uzun çıktı olduğu için akış (streaming) kullanılır: akışsız istek
büyük max_tokens ile HTTP zaman aşımına düşebilir.
"""

from __future__ import annotations

from collections.abc import Callable

from domain.ai_yorum import SISTEM_PROMPT, AiVeriPaketi, AiYorum
from infra.ai_config import AiConfig

# Yorum uzun olabilir (5 bölüm, madde madde); akışla birlikte rahat bir tavan.
_MAX_TOKEN = 8000

# Girdi tavanı: ham paket çok büyükse SESSİZCE KIRPMA — kullanıcıya söyle.
# 1M bağlam penceresinin çok altında güvenli bir sınır (yaklaşık karakter bazlı).
MAX_GIRDI_KARAKTER = 1_500_000


class AiHata(Exception):
    """Yapay zekâ çağrısında kullanıcıya gösterilebilir hata."""


def _istemci(cfg: AiConfig):
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - paket kuruluysa gerçekleşmez
        raise AiHata(
            "Yapay zekâ kütüphanesi bulunamadı. Kurulum: pip install anthropic"
        ) from exc
    return anthropic, anthropic.Anthropic(api_key=cfg.api_key)


def yorumla(
    cfg: AiConfig,
    paket: AiVeriPaketi,
    *,
    bildir: Callable[[str], None] | None = None,
) -> AiYorum:
    """
    Veri paketini modele gönderip yorumu döndürür.

    Onay/anahtar eksikse hiçbir ağ çağrısı yapılmadan AiHata yükseltir.
    """
    cfg = cfg.normalized()
    if not cfg.hazir:
        raise AiHata(cfg.eksik() or "Yapay zekâ ayarları eksik.")
    if not paket.bolumler:
        raise AiHata("Gönderilecek rapor verisi yok — önce raporları getirin.")
    if paket.karakter_sayisi > MAX_GIRDI_KARAKTER:
        raise AiHata(
            f"Veri paketi çok büyük ({paket.karakter_sayisi:,} karakter). ".replace(",", ".")
            + "Daha dar bir dönem seçin."
        )

    anthropic, client = _istemci(cfg)
    if bildir:
        bildir("Yapay zekâya gönderiliyor…")

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
        raise AiHata("Yapay zekâ servisi yoğun (kota/limit). Birazdan tekrar deneyin.") from exc
    except anthropic.APIConnectionError as exc:
        raise AiHata("Yapay zekâ servisine bağlanılamadı. İnternet bağlantısını kontrol edin.") from exc
    except anthropic.APIStatusError as exc:
        raise AiHata(f"Yapay zekâ servisi hata verdi ({exc.status_code}).") from exc

    # Güvenlik sınıflandırıcısı reddettiyse content boş/kısmi olabilir — içerik okumadan önce bak.
    if getattr(mesaj, "stop_reason", "") == "refusal":
        raise AiHata("Yapay zekâ bu içeriği yorumlamayı reddetti. Veriyi daralt veya tekrar dene.")

    metin = "\n".join(b.text for b in mesaj.content if getattr(b, "type", "") == "text").strip()
    if not metin:
        raise AiHata("Yapay zekâdan boş yanıt geldi. Tekrar deneyin.")

    kullanim = getattr(mesaj, "usage", None)
    return AiYorum(
        metin=metin,
        model=cfg.model,
        yil=paket.yil,
        bas=paket.bas,
        bit=paket.bit,
        firma=paket.firma,
        girdi_token=int(getattr(kullanim, "input_tokens", 0) or 0),
        cikti_token=int(getattr(kullanim, "output_tokens", 0) or 0),
        veri_ozeti=paket.ozet_satiri(),
    )
