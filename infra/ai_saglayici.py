"""
Yapay zekâ sağlayıcıları — kayıt defteri, canlı model listesi ve OTOMATİK model seçimi.

TASARIM: kullanıcı model adı yazmaz, seçmez. «Yorumla»ya bastığında sağlayıcının kendi
model listesi çekilir, aday olmayanlar (gömme/görsel/ses/moderasyon…) elenir ve kalanlar
arasından EN GÜNCELİ otomatik seçilir. Böylece yarın yeni bir model çıktığında program
güncellenmeden o model kullanılır.

Model ADI hiçbir yerde hardcode değildir. Hardcode edilen tek şey *tercih sırasıdır*
(hangi aile daha yetenekli sayılır) ve o da eşleşme bulunamazsa sürüm numarasına düşer.

İki istek şeması vardır:
  • "openai"    — OpenAI uyumlu /chat/completions (OpenAI, Google, DeepSeek, xAI…)
  • "anthropic" — Anthropic Messages API (resmi SDK)

Ağ katmanı stdlib urllib'dir (mikro_api ile aynı ilke: yeni bağımlılık yok).
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from domain.ortak import tr_kucuk

_ANTHROPIC_SURUM = "2023-06-01"
_ZAMAN_ASIMI = 25

# Sohbet/yorum için aday OLMAYAN modeller — ada göre elenir.
_ELE = (
    "embed", "embedding", "whisper", "tts", "audio", "speech", "transcribe",
    "image", "imagen", "vision-only", "dall-e", "moderation", "guard", "rerank",
    "aqa", "veo", "search", "code-search", "similarity", "distil",
)

# Yayına hazır olmayanlar — başka aday varsa tercih edilmez.
_DENEYSEL = ("preview", "exp", "experimental", "beta", "alpha", "nightly", "test")


@dataclass(frozen=True)
class Saglayici:
    """Bir yapay zekâ sağlayıcısının bağlantı tarifi."""

    kod: str
    ad: str
    base_url: str
    sema: str                 # "openai" | "anthropic"
    anahtar_ipucu: str
    anahtar_url: str
    # Model listesi ucu farklıysa (Google) ve kimlik doğrulama biçimi:
    model_url: str = ""
    model_auth: str = "bearer"   # "bearer" | "x-api-key" | "query_key"
    # Aile tercihi — en yetenekliden aza. Eşleşme yoksa sürüm numarası karar verir.
    tercih: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ozel_mi(self) -> bool:
        return self.kod == "ozel"

    def model_listesi_url(self, base_url: str = "") -> str:
        if self.model_url:
            return self.model_url
        kok = (base_url or self.base_url).rstrip("/")
        return f"{kok}/models" if kok else ""


SAGLAYICILAR: tuple[Saglayici, ...] = (
    Saglayici(
        "anthropic", "Anthropic — Claude", "https://api.anthropic.com/v1", "anthropic",
        "sk-ant-…", "https://console.anthropic.com/settings/keys",
        model_auth="x-api-key", tercih=("opus", "sonnet", "haiku"),
    ),
    Saglayici(
        "openai", "OpenAI — GPT", "https://api.openai.com/v1", "openai",
        "sk-…", "https://platform.openai.com/api-keys",
        tercih=("gpt", "o4", "o3"),
    ),
    Saglayici(
        # Google'ın OpenAI uyumlu katmanı /models ucunu vermiyor (canlıda HTTP 400);
        # liste yerel API'den, sohbet OpenAI uyumlu uçtan gider.
        "google", "Google — Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai", "openai",
        "AIza…", "https://aistudio.google.com/apikey",
        model_url="https://generativelanguage.googleapis.com/v1beta/models",
        model_auth="query_key", tercih=("pro", "flash"),
    ),
    Saglayici(
        "deepseek", "DeepSeek", "https://api.deepseek.com", "openai",
        "sk-…", "https://platform.deepseek.com/api_keys",
        tercih=("reasoner", "chat"),
    ),
    # Groq listeden ÇIKARILDI: ücretsiz kota altında sürekli hata veriyordu. Gerekirse
    # «Özel» sağlayıcıyla https://api.groq.com/openai/v1 adresi elle girilebilir.
    Saglayici(
        "xai", "xAI — Grok", "https://api.x.ai/v1", "openai",
        "xai-…", "https://console.x.ai",
        tercih=("grok",),
    ),
    Saglayici("ozel", "Özel (OpenAI uyumlu adres)", "", "openai", "", ""),
)

_HARITA = {s.kod: s for s in SAGLAYICILAR}
VARSAYILAN_SAGLAYICI = "anthropic"


def saglayici_bul(kod: str) -> Saglayici:
    """Koda göre sağlayıcı; bilinmiyorsa varsayılana düşer."""
    return _HARITA.get((kod or "").strip(), _HARITA[VARSAYILAN_SAGLAYICI])


class ModelListesiHatasi(Exception):
    """Model listesi çekilemedi — kullanıcıya gösterilebilir mesaj."""


# --------------------------------------------------------------- hata çevirisi
def _govde_mesaji(exc: urllib.error.HTTPError) -> str:
    """Sağlayıcının kendi hata açıklamasını çıkarır (her servis farklı sarar)."""
    try:
        ham = exc.read().decode("utf-8", "replace")
    except (AttributeError, OSError, ValueError):
        return ""
    try:
        veri = json.loads(ham)
    except ValueError:
        return ham.strip()[:300]
    if isinstance(veri, list) and veri:          # Google bazen liste sarar
        veri = veri[0]
    if isinstance(veri, dict):
        hata = veri.get("error")
        if isinstance(hata, dict):
            return str(hata.get("message") or hata.get("status") or "").strip()[:300]
        if isinstance(hata, str):
            return hata.strip()[:300]
        for alan in ("message", "detail", "msg"):
            if veri.get(alan):
                return str(veri[alan]).strip()[:300]
    return ""


def http_hata_mesaji(exc: urllib.error.HTTPError, *, model: str = "") -> str:
    """
    HTTP hatasını kullanıcının anlayacağı Türkçe cümleye çevirir.

    «HTTP 400» tek başına hiçbir şey anlatmaz; ne yapması gerektiğini söyleriz ve
    sağlayıcının kendi açıklamasını da ekleriz (asıl teşhis çoğu zaman orada).
    """
    ayrinti = _govde_mesaji(exc)
    kuyruk = f"\n\nSağlayıcının açıklaması: {ayrinti}" if ayrinti else ""
    if exc.code == 400:
        return ("İstek reddedildi. Genellikle model adı bu sağlayıcıda geçersiz "
                f"olduğunda olur{f' (denenen: {model})' if model else ''}." + kuyruk)
    if exc.code == 401:
        return "API anahtarı geçersiz. Anahtarı kontrol edip yeniden girin." + kuyruk
    if exc.code == 403:
        return ("API anahtarı bu işlem için yetkisiz. Anahtarın ilgili modele/servise "
                "erişimi olduğundan ve faturalandırmanın açık olduğundan emin olun." + kuyruk)
    if exc.code == 404:
        return (f"Bulunamadı{f' (model: {model})' if model else ''}. Sağlayıcı ya da "
                "adres yanlış olabilir." + kuyruk)
    if exc.code == 413:
        return "Gönderilen veri sağlayıcı için fazla büyük. Daha dar bir dönem seçin." + kuyruk
    if exc.code == 429:
        return ("Kota doldu ya da çok sık istek gönderildi. Birkaç dakika sonra tekrar "
                "deneyin; ücretsiz kotalarda bu sık olur." + kuyruk)
    if 500 <= exc.code < 600:
        return f"Sağlayıcının sunucusunda geçici hata (HTTP {exc.code}). Tekrar deneyin." + kuyruk
    return f"Sağlayıcı isteği reddetti (HTTP {exc.code})." + kuyruk


def ag_hata_mesaji(exc: Exception) -> str:
    """Bağlantı/zaman aşımı hatalarını Türkçeleştirir."""
    if isinstance(exc, TimeoutError):
        return ("Zaman aşımı — sağlayıcı yanıt vermedi. İnternet bağlantınız yavaş olabilir "
                "ya da servis yoğun. Tekrar deneyin.")
    if isinstance(exc, urllib.error.URLError):
        sebep = exc.reason
        if isinstance(sebep, TimeoutError):
            return "Zaman aşımı — sağlayıcı yanıt vermedi. Tekrar deneyin."
        metin = str(sebep)
        if "certificate" in metin.lower() or "ssl" in metin.lower():
            return f"Güvenli bağlantı (SSL) kurulamadı: {metin}"
        if "name or service not known" in metin.lower() or "getaddrinfo" in metin.lower():
            return "Adres çözümlenemedi. İnternet bağlantınızı kontrol edin."
        return f"Sağlayıcıya bağlanılamadı: {metin}"
    return f"Beklenmeyen ağ hatası: {exc}"


# ------------------------------------------------------------------ ağ
def _istek(url: str, basliklar: dict[str, str]) -> dict:
    if not url.lower().startswith("https://"):
        raise ModelListesiHatasi("Adres https:// ile başlamalı.")
    istek = urllib.request.Request(url, headers=basliklar, method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(istek, timeout=_ZAMAN_ASIMI,  # noqa: S310
                                    context=ssl.create_default_context()) as yanit:
            return json.loads(yanit.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise ModelListesiHatasi(http_hata_mesaji(exc)) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise ModelListesiHatasi(ag_hata_mesaji(exc)) from exc
    except ValueError as exc:
        raise ModelListesiHatasi(f"Sağlayıcının yanıtı okunamadı: {exc}") from exc


def modelleri_getir(saglayici: Saglayici, api_key: str, base_url: str = "") -> list[str]:
    """Sağlayıcının canlı model listesi (aday olmayanlar elenmiş, alfabetik)."""
    anahtar = (api_key or "").strip()
    if not anahtar:
        raise ModelListesiHatasi("Önce API anahtarını girin.")
    url = saglayici.model_listesi_url(base_url)
    if not url:
        raise ModelListesiHatasi("Base URL boş — «Özel» sağlayıcıda adresi girmelisiniz.")

    basliklar: dict[str, str] = {}
    if saglayici.model_auth == "x-api-key":
        basliklar = {"x-api-key": anahtar, "anthropic-version": _ANTHROPIC_SURUM}
    elif saglayici.model_auth == "query_key":
        url = f"{url}?{urllib.parse.urlencode({'key': anahtar, 'pageSize': 200})}"
    else:
        basliklar = {"Authorization": f"Bearer {anahtar}"}

    veri = _istek(url, basliklar)
    ham = None
    if isinstance(veri, dict):
        ham = veri.get("data") if isinstance(veri.get("data"), list) else veri.get("models")
    if not isinstance(ham, list):
        raise ModelListesiHatasi("Sağlayıcı beklenmeyen bir yanıt verdi.")

    modeller: set[str] = set()
    for m in ham:
        if isinstance(m, str):
            kimlik = m
        elif isinstance(m, dict):
            # Google yalnız generateContent destekleyenleri aday sayar.
            yontemler = m.get("supportedGenerationMethods")
            if isinstance(yontemler, list) and "generateContent" not in yontemler:
                continue
            kimlik = m.get("id") or m.get("name") or ""
        else:
            continue
        kimlik = str(kimlik).strip().removeprefix("models/")
        if kimlik and not _elenmis(kimlik):
            modeller.add(kimlik)
    if not modeller:
        raise ModelListesiHatasi("Sağlayıcı sohbet için uygun model döndürmedi.")
    return sorted(modeller)


# ------------------------------------------------- otomatik en güncel model seçimi
def _elenmis(model: str) -> bool:
    d = tr_kucuk(model)
    return any(k in d for k in _ELE)


def _surum_puani(model: str) -> tuple[float, ...]:
    """Addaki sürüm numaralarını sayıya çevirir (claude-opus-4-8 → (4, 8))."""
    sayilar = [float(p) for p in re.findall(r"\d+(?:\.\d+)?", model.replace("-", " "))]
    # 8 haneli tarih damgası (20251001) sürüm değildir; sürüm sayılırsa hep kazanır.
    return tuple(s for s in sayilar if s < 10_000) or (0.0,)


def en_iyi_model(modeller: list[str], saglayici: Saglayici) -> str:
    """
    Aday listesinden EN GÜNCEL/EN YETENEKLİ modeli seçer.

    Sıra: (1) sağlayıcının tercih ettiği aile, (2) yayına hazır olma (preview/exp değil),
    (3) sürüm numarası, (4) alfabetik son. Model adı hardcode değil; yalnız tercih
    sırası bilinir, o da eşleşmezse sürüm numarası karar verir.
    """
    adaylar = [m for m in modeller if m and not _elenmis(m)]
    if not adaylar:
        raise ModelListesiHatasi("Uygun model bulunamadı.")

    def puan(model: str) -> tuple:
        d = tr_kucuk(model)
        aile = next((len(saglayici.tercih) - i for i, k in enumerate(saglayici.tercih)
                     if k in d), 0)
        kararli = 0 if any(k in d for k in _DENEYSEL) else 1
        return (aile, kararli, _surum_puani(model), model)

    return max(adaylar, key=puan)


def guncel_model_sec(saglayici: Saglayici, api_key: str, base_url: str = "") -> str:
    """Listeyi çekip en güncel modeli döndürür (kullanıcı hiçbir şey seçmez)."""
    return en_iyi_model(modelleri_getir(saglayici, api_key, base_url), saglayici)
