"""
Mikro ERP REST API istemcisi (Python).

ss/lib/mikro-api.ts auth ve istek desenini birebir taşır:
  - Günlük rotasyonlu parola: MD5( "YYYY-MM-DD"  veya  "YYYY-MM-DD <SIFRE_GUN>" )
  - POST {baseUrl}/{endpoint}  gövde: {"Mikro": {...auth}, ...}
  - Yanıt zarfı: result[0].Data ; result[0].IsError true ise hata fırlatılır
  - SqlVeriOkuV2 ile salt-okunur ham SQL — satırlar SQLResult1 / SQLResult / Data / Rows altında
  - Geçici ağ hataları için exponential backoff (2s, 4s, 8s) retry
  - TLS doğrulaması yapılandırılabilir (MikroConfig.tls_dogrula). Varsayılan KAPALI —
    Mikro kurulumlarında self-signed sertifika yaygındır (ss'de rejectUnauthorized:false);
    geçerli sertifikası olan kurulumlar ayarlardan doğrulamayı açabilir.

Ağ katmanı stdlib `urllib` ile yazıldı (yeni bağımlılık yok, PyInstaller derlemesi sade kalsın).
Test edilebilmesi için `transport` enjekte edilebilir (network'süz birim testleri).
"""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from infra.cancel import aktif_iptal
from infra.config import MikroConfig

_log = logging.getLogger(__name__)
_tls_uyari_verildi = False

DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_ATTEMPTS = 4

# transport(url, body_json, timeout_seconds) -> (http_status, response_text)
Transport = Callable[[str, str, float], "tuple[int, str]"]


class MikroAPIError(Exception):
    """Mikro API hata (HTTP, çözümleme veya API seviyesi IsError)."""


class MikroIptalError(MikroAPIError):
    """Kullanıcı / worker iptali — retry edilmez, UI'ya hata olarak gösterilmez."""


def password_hash(sifre_gun: str, today: str | None = None) -> str:
    """
    Günlük rotasyonlu Mikro parolasını üretir (ss getPasswordHash ile birebir).

    ss `new Date().toISOString().split('T')[0]` kullanır → UTC tarih. Mikro tarafı bunu
    beklediği için biz de UTC kullanıyoruz (yerel/UTC farkı gece yarısı sorununu önler).
    """
    gun = today if today is not None else datetime.now(UTC).strftime("%Y-%m-%d")
    to_hash = f"{gun} {sifre_gun}" if sifre_gun else gun
    return hashlib.md5(to_hash.encode("utf-8")).hexdigest()


def build_auth(cfg: MikroConfig) -> dict[str, Any]:
    """Mikro istek gövdesindeki `Mikro` auth objesini üretir."""
    c = cfg.normalized()
    return {
        "ApiKey": c.api_key,
        "FirmaKodu": c.firma_kodu,
        "CalismaYili": c.calisma_yili,
        "KullaniciKodu": c.kullanici_kodu,
        "Sifre": password_hash(c.sifre_gun),
    }


def _ssl_context(dogrula: bool) -> ssl.SSLContext:
    """TLS bağlamı: dogrula=False ise self-signed sertifika kabul edilir (Mikro'da yaygın)."""
    ctx = ssl.create_default_context()
    if not dogrula:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _iptal_kontrol() -> None:
    token = aktif_iptal()
    if token is not None and token.iptal_mi():
        raise MikroIptalError("İptal edildi")


def _urllib_transport_factory(dogrula: bool) -> Transport:
    """http.client tabanlı transport — CancelToken ile bağlantı kesilebilir."""
    ctx = _ssl_context(dogrula)

    def _transport(url: str, body: str, timeout: float) -> tuple[int, str]:
        _iptal_kontrol()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise MikroAPIError(f"Geçersiz Mikro URL: {url!r}")
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        if parsed.scheme == "https":
            conn: http.client.HTTPConnection = http.client.HTTPSConnection(
                host, port=port, context=ctx, timeout=timeout,
            )
        else:
            conn = http.client.HTTPConnection(host, port=port, timeout=timeout)

        token = aktif_iptal()
        if token is not None:
            token.bagla(conn)
        try:
            _iptal_kontrol()
            conn.request(
                "POST",
                path,
                body=body.encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            _iptal_kontrol()
            resp = conn.getresponse()
            text = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), text
        except MikroIptalError:
            raise
        except Exception:
            _iptal_kontrol()  # iptal kaynaklı socket hatası → MikroIptalError
            raise
        finally:
            if token is not None:
                token.birak()
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    return _transport


def _is_retryable(err: Exception) -> bool:
    """Geçici ağ hataları retry edilir; HTTP/IsError/iptal/çözümleme hataları edilmez."""
    if isinstance(err, MikroIptalError):
        return False
    if isinstance(err, MikroAPIError):
        return False
    if isinstance(err, (TimeoutError, ssl.SSLError, urllib.error.URLError, ConnectionError, OSError)):
        return True
    msg = str(err).lower()
    return any(tok in msg for tok in ("timed out", "timeout", "reset", "socket", "tls", "refused", "eof"))


def parse_sql_rows(res: Any) -> list[dict[str, Any]]:
    """SqlVeriOkuV2 yanıtından satır listesini çıkarır (ss parseSqlRows mantığı)."""
    if isinstance(res, list):
        if not res:
            return []
        first = res[0]
        if isinstance(first, dict):
            inner = (
                first.get("SQLResult1")
                or first.get("SQLResult")
                or first.get("Data")
                or first.get("Rows")
            )
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
        return [r for r in res if isinstance(r, dict)]
    if isinstance(res, dict):
        inner = (
            res.get("SQLResult1")
            or res.get("SQLResult")
            or res.get("Rows")
            or res.get("Data")
            or res.get("rows")
        )
        if isinstance(inner, list):
            return [r for r in inner if isinstance(r, dict)]
    return []


def parse_sql_first_row(res: Any) -> dict[str, Any] | None:
    rows = parse_sql_rows(res)
    return rows[0] if rows else None


def get_row_value(row: dict[str, Any], *keys: str) -> Any:
    """Satırdan bir anahtarı farklı yazımlarıyla (aynen/UPPER/lower) dener."""
    for key in keys:
        for variant in (key, key.upper(), key.lower()):
            if variant in row:
                val = row[variant]
                if val is not None and val != "":
                    return val
    return None


class MikroClient:
    """Mikro REST API istemcisi. Tek bir MikroConfig ile kurulur."""

    def __init__(
        self,
        cfg: MikroConfig,
        transport: Transport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self.cfg = cfg.normalized()
        global _tls_uyari_verildi
        if not self.cfg.tls_dogrula and not _tls_uyari_verildi:
            _tls_uyari_verildi = True
            _log.warning(
                "TLS sertifika doğrulaması kapalı (tls_dogrula=False). "
                "Self-signed Mikro kurulumları için yaygın; geçerli sertifika varsa "
                "Mikro Ayarları'ndan doğrulamayı açın."
            )
        self._transport = transport or _urllib_transport_factory(self.cfg.tls_dogrula)
        self.timeout = timeout
        self.max_attempts = max_attempts

    def request(
        self,
        endpoint: str,
        body: dict[str, Any],
        *,
        timeout: float | None = None,
        max_attempts: int | None = None,
    ) -> Any:
        if not self.cfg.base_url:
            raise MikroAPIError("Mikro API adresi tanımlı değil. Önce 'Mikro Ayarları'nı doldurun.")
        url = f"{self.cfg.base_url}/{endpoint}"
        body_str = json.dumps(body, ensure_ascii=False)
        attempts = max_attempts or self.max_attempts
        to = timeout or self.timeout

        last_err: Exception | None = None
        for attempt in range(attempts):
            try:
                _iptal_kontrol()
                status, text = self._transport(url, body_str, to)
                if status < 200 or status >= 300:
                    raise MikroAPIError(f"Mikro HTTP {status}: {text[:400]}")
                return self._extract_data(text)
            except MikroIptalError:
                raise
            except MikroAPIError:
                raise
            except Exception as exc:  # noqa: BLE001 — ağ hatalarını sınıflandırıp retry ediyoruz
                last_err = exc
                if attempt < attempts - 1 and _is_retryable(exc):
                    # İptal edilebilir bekleme (2s / 4s / 8s — 0.2s dilimler)
                    bekle = 2 * (attempt + 1)
                    for _ in range(int(bekle / 0.2)):
                        _iptal_kontrol()
                        time.sleep(0.2)
                    continue
                raise MikroAPIError(f"Mikro bağlantı hatası: {exc}") from exc
        raise MikroAPIError(f"Mikro bağlantı hatası: {last_err}")

    @staticmethod
    def _extract_data(text: str) -> Any:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MikroAPIError(f"Mikro yanıtı çözümlenemedi: {text[:200]}") from exc
        result = data.get("result") if isinstance(data, dict) else None
        first = result[0] if isinstance(result, list) and result else None
        if isinstance(first, dict) and first.get("IsError"):
            msg = (first.get("ErrorMessage") or "").strip() or "Mikro API hata"
            raise MikroAPIError(f"Mikro: {msg}")
        return first.get("Data") if isinstance(first, dict) else None

    def sql_veri_oku(
        self,
        sql: str,
        *,
        firma_kodu: str | None = None,
        timeout: float | None = None,
        max_attempts: int | None = None,
    ) -> Any:
        """SqlVeriOkuV2 ile salt-okunur ham SQL çalıştırır."""
        auth = build_auth(self.cfg)
        if firma_kodu is not None:
            from infra.sql_params import firma_kodu_guvenli

            auth = {**auth, "FirmaKodu": firma_kodu_guvenli(str(firma_kodu))}
        body = {"Mikro": auth, "SQLSorgu": sql}
        return self.request("SqlVeriOkuV2", body, timeout=timeout, max_attempts=max_attempts)

    def ping(self) -> None:
        """Hızlı erişim yoklaması (auth + ağ). Başarısızsa MikroAPIError fırlatır."""
        self.sql_veri_oku("SELECT 1 AS ok", timeout=15, max_attempts=1)
