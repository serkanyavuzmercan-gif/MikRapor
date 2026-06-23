"""
Mikro şema teşhis aracı — "0 satır" sorununu kökten çözmek için.

Bu script, kaydedilmiş Mikro Ayarları'nı (config.json) kullanarak bu Mikro'nun GERÇEK
tablo/kolon adlarını ve fatura tip kodlarını bulur. Böylece mikro_fetch.py'deki SQL'ler
tahmin değil, yer gerçeğine göre yazılır.

Çalıştırma (repo klasöründe):
    .\\.venv\\Scripts\\python.exe diag_mikro.py

Çıktının TAMAMINI kopyalayıp gönderin. GİZLİ DEĞER YAZMAZ (API anahtarı/şifre çıktıya
gelmez); yalnızca şema/sayı bilgisi döner.
"""

from __future__ import annotations

from config import load_config
from mikro_api import MikroAPIError, MikroClient, parse_sql_rows


def q(client: MikroClient, label: str, sql: str, limit: int = 60) -> None:
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
    host = cfg.base_url.split("//")[-1].split("/")[0] if cfg.base_url else "(boş)"
    print(f"Bağlantı: host={host}  firma={cfg.firma_kodu}  yıl={cfg.calisma_yili}")
    if not cfg.is_complete():
        print("UYARI: ayarlar eksik:", cfg.eksik_alanlar())
        return
    c = MikroClient(cfg)

    q(c, "1) Erişim testi", "SELECT 1 AS ok")

    q(c, "2) Muhasebe / muavin / yevmiye / fiş tablo adları",
      "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
      "WHERE TABLE_NAME LIKE '%MUHASEBE%' OR TABLE_NAME LIKE '%MUAVIN%' "
      "OR TABLE_NAME LIKE '%YEVMIYE%' OR TABLE_NAME LIKE '%_FIS%' "
      "OR TABLE_NAME LIKE '%HESAP_HAREKET%' ORDER BY TABLE_NAME")

    q(c, "3) Bu muhasebe/GL tablolarının kolonları (borç/alacak/tarih/hesap için)",
      "SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
      "WHERE (TABLE_NAME LIKE '%MUHASEBE%' OR TABLE_NAME LIKE '%MUAVIN%' OR TABLE_NAME LIKE '%YEVMIYE%') "
      "ORDER BY TABLE_NAME, ORDINAL_POSITION", limit=120)

    q(c, "4) STOK_HAREKETLERI: son 120 günde sth_tip/sth_evraktip dağılımı (FATURA kodları)",
      "SELECT sth_tip, sth_evraktip, COUNT(*) adet, MIN(sth_tarih) ilk_tarih, MAX(sth_tarih) son_tarih "
      "FROM STOK_HAREKETLERI WHERE sth_tarih >= DATEADD(day,-120,GETDATE()) "
      "GROUP BY sth_tip, sth_evraktip ORDER BY adet DESC")

    q(c, "5) STOK_HAREKETLERI ilgili kolon adları (belge_no / vade / tutar / miktar)",
      "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='STOK_HAREKETLERI' "
      "AND (COLUMN_NAME LIKE '%tarih%' OR COLUMN_NAME LIKE '%belge%' OR COLUMN_NAME LIKE '%vade%' "
      "OR COLUMN_NAME LIKE '%tutar%' OR COLUMN_NAME LIKE '%miktar%' OR COLUMN_NAME LIKE '%evrak%' "
      "OR COLUMN_NAME LIKE '%cari%') ORDER BY COLUMN_NAME")

    q(c, "6) CARI_HESAP_HAREKETLERI kolon adları (banka/tahsilat hareketleri için)",
      "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='CARI_HESAP_HAREKETLERI' "
      "ORDER BY COLUMN_NAME", limit=120)

    q(c, "7) Cari ay (içinde bulunulan ay) STOK_HAREKETLERI satır sayısı — veri var mı?",
      "SELECT COUNT(*) adet, MIN(sth_tarih) ilk, MAX(sth_tarih) son FROM STOK_HAREKETLERI "
      "WHERE sth_tarih >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)")

    print("\n" + "=" * 72)
    print("Bitti. Yukarıdaki çıktının TAMAMINI kopyalayıp gönderin.")


if __name__ == "__main__":
    main()
