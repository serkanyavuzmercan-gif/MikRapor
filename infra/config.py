"""
Mikro ERP bağlantı ayarları — kullanıcı bazlı yerel config dosyası + ortam değişkeni fallback.

Masaüstü uygulaması her kullanıcının KENDİ Mikro sunucusuna bağlanır. Bağlantı bilgileri
ne repoda ne de koda gömülüdür; kullanıcı "Mikro Ayarları" ekranından girer ve yerel diske
kaydedilir (Windows: %APPDATA%/MikRapor/config.json). Bilgiler kullanıcının makinesinden çıkmaz.

ss/lib/mikro-api.ts ile aynı alanlar kullanılır (ApiKey, FirmaKodu, CalismaYili, KullaniciKodu,
SifreGun) ki tek-kiracılı web entegrasyonu ile uyumlu kalsın.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from domain.gercek_durum_ayarlar import GercekDurumAyarlar
from infra import gizli

APP_DIR_NAME = "MikRapor"
CONFIG_FILE_NAME = "config.json"

_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
_KOD_AYIRAC = re.compile(r"[,;\s]+")
_SAYISAL_KOD_ARALIGI = re.compile(r"^(\d+)-\d+$")


def _varsayilan_firma_kodu(tekil: str, liste: str) -> str:
    """API'nin zorunlu FirmaKodu alanını, kullanıcıdan ikinci kez istemeden üretir."""
    if (tekil or "").strip():
        return (tekil or "").strip()
    ilk = next((p for p in _KOD_AYIRAC.split((liste or "").strip()) if p), "")
    aralik = _SAYISAL_KOD_ARALIGI.fullmatch(ilk)
    return aralik.group(1) if aralik else ilk


def config_dir() -> Path:
    """Platforma göre kullanıcı ayar klasörü (Windows: %APPDATA%, diğer: ~/.config)."""
    appdata = os.environ.get("APPDATA")  # Windows
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_DIR_NAME


def config_path() -> Path:
    return config_dir() / CONFIG_FILE_NAME


def _read_config_data() -> dict:
    """config.json ham içeriği (Mikro + gercek_durum vb.)."""
    path = config_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return {}


def save_config_data(data: dict) -> Path:
    """Tüm config.json içeriğini yazar (mevcut gercek_durum vb. korunur)."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)  # yalnızca sahibi okusun/yazsın (Linux/macOS; Windows’ta no-op benzeri)
    except OSError:
        pass
    return path


@dataclass
class MikroConfig:
    """Mikro REST API bağlantı bilgileri (ss ortam değişkenleriyle birebir karşılık)."""

    base_url: str = ""          # MIKRO_BASE_URL  — örn. https://192.168.1.50:443 veya Tailscale adresi
    api_key: str = ""           # MIKRO_API_KEY
    # API'nin zorunlu alanı; kullanıcı arayüzünde firma_kodlari'nın ilk kodundan türetilir.
    # Eski config/env kayıtları için ayrı alan korunur.
    firma_kodu: str = ""        # MIKRO_FIRMA_KODU — eski kurulumlarla uyumluluk
    # Mikro'da veritabanını FİRMA KODU seçer. Kullanıcının tek girdiği alan budur:
    # «20, 26» veya «001-100». Program yıl → kod eşlemesini katalogdan keşfeder.
    firma_kodlari: str = ""     # MIKRO_FIRMA_KODLARI
    # Teknik API alanı. Masaüstü arayüzünde sorulmaz; rapor yılı seçili tarihten türetilir.
    # 0 ise bağlantı/test için içinde bulunulan yıl kullanılır.
    calisma_yili: int = 0       # MIKRO_CALISMA_YILI — başsız kullanım uyumluluğu
    kullanici_kodu: str = ""    # MIKRO_KULLANICI_KODU
    sifre_gun: str = ""         # MIKRO_SIFRE_GUN — Mikro kullanıcı şifresi (zorunlu)
    firma_adi: str = ""         # Raporlarda (bilanço başlığı) görünen firma unvanı (opsiyonel)
    tls_dogrula: bool = False   # MIKRO_TLS_DOGRULA — True: sertifika doğrulanır;
                                # False: self-signed kabul (Mikro kurulumlarında yaygın)

    def normalized(self) -> MikroConfig:
        yil = self.calisma_yili or date.today().year
        kod_listesi = (self.firma_kodlari or "").strip()
        return MikroConfig(
            base_url=(self.base_url or "").strip().rstrip("/"),
            api_key=(self.api_key or "").strip(),
            firma_kodu=_varsayilan_firma_kodu(self.firma_kodu, kod_listesi),
            firma_kodlari=kod_listesi,
            calisma_yili=int(yil),
            kullanici_kodu=(self.kullanici_kodu or "").strip(),
            sifre_gun=(self.sifre_gun or "").strip(),
            firma_adi=(self.firma_adi or "").strip(),
            tls_dogrula=bool(self.tls_dogrula),
        )

    def eksik_alanlar(self) -> list[str]:
        """Bağlantı için zorunlu ama boş olan alanların okunabilir adları."""
        c = self.normalized()
        eksik: list[str] = []
        if not c.base_url:
            eksik.append("Mikro API adresi")
        if not c.api_key:
            eksik.append("API anahtarı")
        if not c.firma_kodu:
            eksik.append("Firma kodu")
        if not c.kullanici_kodu:
            eksik.append("Kullanıcı kodu")
        if not c.sifre_gun:
            eksik.append("Şifre")
        return eksik

    def is_complete(self) -> bool:
        return not self.eksik_alanlar()

    def base_url_hatalari(self) -> list[str]:
        """base_url biçim / şema hataları (kayıt öncesi doğrulama)."""
        return base_url_dogrula(self.normalized().base_url)


def base_url_dogrula(url: str) -> list[str]:
    """
    Mikro API adresini doğrular.

    - http:// veya https:// zorunlu
    - http yalnızca loopback (localhost / 127.0.0.1 / ::1) için kabul;
      LAN/uzak host'ta https gerekir (kimlik bilgisi düz metin gitmesin)
    """
    s = (url or "").strip()
    if not s:
        return ["Mikro API adresi boş"]
    parsed = urlparse(s)
    if parsed.scheme not in ("http", "https"):
        return ["Mikro API adresi http:// veya https:// ile başlamalı"]
    host = (parsed.hostname or "").lower()
    if not host:
        return ["Mikro API adresinde host adı yok"]
    if parsed.scheme == "http" and host not in _LOOPBACK:
        return [
            "Uzak/LAN adreslerde https:// kullanın "
            f"(http yalnızca localhost için; şu an: {host})"
        ]
    return []


def _int_or_zero(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _bool_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "evet", "yes")


def _from_env() -> MikroConfig:
    """Ortam değişkenlerinden config üretir (ss ile aynı isimler). Geliştiriciler için fallback."""
    return MikroConfig(
        base_url=os.environ.get("MIKRO_BASE_URL", ""),
        api_key=os.environ.get("MIKRO_API_KEY", ""),
        firma_kodu=os.environ.get("MIKRO_FIRMA_KODU", ""),
        firma_kodlari=os.environ.get("MIKRO_FIRMA_KODLARI", ""),
        calisma_yili=_int_or_zero(os.environ.get("MIKRO_CALISMA_YILI")),
        kullanici_kodu=os.environ.get("MIKRO_KULLANICI_KODU", ""),
        sifre_gun=os.environ.get("MIKRO_SIFRE_GUN", ""),
        firma_adi=os.environ.get("MIKRO_FIRMA_ADI", ""),
        tls_dogrula=_bool_env(os.environ.get("MIKRO_TLS_DOGRULA")),
    ).normalized()


def load_config() -> MikroConfig:
    """Yerel config dosyasını okur; yoksa veya bozuksa ortam değişkenlerine düşer.

    api_key / sifre_gun şifreli ("dpapi:...") ise çözülür; düz metin (eski kayıt) da okunur.
    """
    data = _read_config_data()
    if data:
        try:
            return MikroConfig(
                base_url=data.get("base_url", ""),
                api_key=gizli.coz(str(data.get("api_key", "") or "")),
                firma_kodu=str(data.get("firma_kodu", "")),
                firma_kodlari=str(data.get("firma_kodlari", "")),
                calisma_yili=_int_or_zero(data.get("calisma_yili")),
                kullanici_kodu=data.get("kullanici_kodu", ""),
                sifre_gun=gizli.coz(str(data.get("sifre_gun", "") or "")),
                firma_adi=data.get("firma_adi", ""),
                tls_dogrula=bool(data.get("tls_dogrula", False)),
            ).normalized()
        except (TypeError, ValueError):
            pass
    return _from_env()


def save_config(cfg: MikroConfig) -> Path:
    """Mikro alanlarını kaydeder; gercek_durum vb. diğer anahtarları silmez.

    Sırlar (api_key, sifre_gun) DPAPI (Windows) veya yerel şifre (Linux/macOS) ile yazılır.
    """
    data = _read_config_data()
    kayit = asdict(cfg.normalized())
    kayit["api_key"] = gizli.sifrele(kayit["api_key"])
    kayit["sifre_gun"] = gizli.sifrele(kayit["sifre_gun"])
    data.update(kayit)
    return save_config_data(data)


# --- Nakit & Kârlılık ayarları (config.json «gercek_durum» anahtarı) ---

def load_gercek_durum_ayarlar() -> GercekDurumAyarlar:
    return GercekDurumAyarlar.from_dict(_read_config_data().get("gercek_durum"))


def save_gercek_durum_ayarlar(ayarlar: GercekDurumAyarlar) -> None:
    data = _read_config_data()
    data["gercek_durum"] = asdict(ayarlar)
    save_config_data(data)


def premium_onbellek() -> bool:
    """
    Premium daha önce DOĞRULANDI mı?

    Store lisansı her açılışta okunamayabilir (çevrimdışı, hesap oturumu, servis
    hatası). Bu bayrak yalnız POZİTİF bir doğrulamayla yazılır ve kendiliğinden
    silinmez — bkz. `domain/lisans.py`: ödemiş müşteriyi bir API hıçkırığı yüzünden
    kilitlemek, birkaç kişinin fazladan erişmesinden pahalıdır.
    """
    return bool(_read_config_data().get("lisans", {}).get("premium", False))


def premium_onbellek_yaz() -> None:
    """Store premium'u doğruladı — bir daha sorulamasa bile açık kalsın."""
    data = _read_config_data()
    data["lisans"] = {"premium": True}
    save_config_data(data)
