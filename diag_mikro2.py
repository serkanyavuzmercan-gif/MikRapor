"""
Mikro şema teşhis — 2. tur (muavin / GL).

MUHASEBE_FISLERI (fiş başlığı) + MUHASEBE_FIS_DETAYLARI (satır detayı) kolon adlarını ve
küçük bir örnek satırı getirir. Böylece muavin (operasyonel gider 7xx) SQL'i doğru yazılır.

Çalıştırma:
    .\\.venv\\Scripts\\python.exe diag_mikro2.py

Çıktının TAMAMINI gönderin. Gizli değer yazmaz.
"""

from __future__ import annotations

from config import load_config
from mikro_api import MikroAPIError, MikroClient, parse_sql_rows


def q(client: MikroClient, label: str, sql: str, limit: int = 200) -> None:
    print("\n" + "=" * 72)
    print(label)
    print("-" * 72)
    try:
        rows = parse_sql_rows(client.sql_veri_oku(sql, timeout=60, max_attempts=2))
        if not rows:
            print("  (0 satır döndü)")
        for r in rows[:limit]:
            print("  ", r)
        if len(rows) > limit:
            print(f"  ... (+{len(rows) - limit} satır daha)")
    except MikroAPIError as exc:
        print("  HATA:", exc)
    except Exception as exc:  # noqa: BLE001
        print("  BEKLENMEYEN HATA:", exc)


def main() -> None:
    cfg = load_config()
    if not cfg.is_complete():
        print("UYARI: ayarlar eksik:", cfg.eksik_alanlar())
        return
    c = MikroClient(cfg)

    q(c, "A) MUHASEBE_FIS_DETAYLARI kolonları (hesap kodu / borç / alacak / meblağ)",
      "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
      "WHERE TABLE_NAME='MUHASEBE_FIS_DETAYLARI' ORDER BY ORDINAL_POSITION")

    q(c, "B) MUHASEBE_FISLERI kolonları (tarih / fiş no)",
      "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
      "WHERE TABLE_NAME='MUHASEBE_FISLERI' ORDER BY ORDINAL_POSITION")

    # Örnek: 7 ile başlayan gider hesaplarından birkaç satır (kolon adlarını görmeden, * ile).
    # NOLOCK + TOP 3, yalnızca yapıyı görmek için.
    q(c, "C) MUHASEBE_FIS_DETAYLARI örnek 3 satır (yapı görünsün)",
      "SELECT TOP 3 * FROM MUHASEBE_FIS_DETAYLARI WITH (NOLOCK)", limit=3)

    print("\n" + "=" * 72)
    print("Bitti. A ve B kolon listelerini + C örneğini TAMAMEN gönderin.")


if __name__ == "__main__":
    main()
