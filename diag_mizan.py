"""
Mizan denge teşhisi — 'AKTİF≠PASİF (1,96M fark)' kaynağını bulur.

Σ(borç) ≠ Σ(alacak) çıkıyor. Bu script hangi kolon çiftinin dengeli olduğunu ve hangi
FİŞ TİPİNİN (fis_tur) dengesizliği yarattığını gösterir. Gizli değer yazmaz.

    .\\.venv\\Scripts\\python.exe diag_mizan.py            # bugüne kadar
    .\\.venv\\Scripts\\python.exe diag_mizan.py 2026-06-23
"""

from __future__ import annotations

import sys
from datetime import date

from config import load_config
from mikro_api import MikroAPIError, MikroClient, parse_sql_rows


def q(c: MikroClient, label: str, sql: str, lim: int = 60) -> None:
    print("\n" + "=" * 72)
    print(label)
    print("-" * 72)
    try:
        rows = parse_sql_rows(c.sql_veri_oku(sql, timeout=120, max_attempts=2))
        if not rows:
            print("  (0 satır)")
        for r in rows[:lim]:
            print("  ", r)
    except MikroAPIError as e:
        print("  HATA:", e)
    except Exception as e:  # noqa: BLE001
        print("  BEKLENMEYEN HATA:", e)


def main() -> None:
    asof = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    c = MikroClient(cfg)
    flt = f"fis_iptal = 0 AND fis_tarih <= '{asof}'"

    q(c, "1) Kolon toplamları — hangi çift dengeli? (m0=borç?, m1=alacak?)",
      f"SELECT SUM(fis_meblag0) m0, SUM(fis_meblag1) m1, SUM(fis_meblag2) m2, "
      f"SUM(fis_meblag3) m3, SUM(fis_meblag4) m4, SUM(fis_meblag5) m5, SUM(fis_meblag6) m6, "
      f"COUNT(*) n FROM MUHASEBE_FISLERI WITH (NOLOCK) WHERE {flt}")

    q(c, "2) fis_tur bazında borç/alacak/FARK — hangi fiş tipi dengesiz?",
      f"SELECT fis_tur, COUNT(*) n, SUM(fis_meblag0) borc, SUM(fis_meblag1) alacak, "
      f"SUM(fis_meblag0) - SUM(fis_meblag1) fark FROM MUHASEBE_FISLERI WITH (NOLOCK) "
      f"WHERE {flt} GROUP BY fis_tur ORDER BY ABS(SUM(fis_meblag0) - SUM(fis_meblag1)) DESC")

    q(c, "3) Tarih aralığı + NULL tarih + iptal=0 satır sayısı",
      "SELECT MIN(fis_tarih) ilk, MAX(fis_tarih) son, "
      "SUM(CASE WHEN fis_tarih IS NULL THEN 1 ELSE 0 END) null_tarih, COUNT(*) n "
      "FROM MUHASEBE_FISLERI WITH (NOLOCK) WHERE fis_iptal = 0")

    q(c, "4) 102 Bankalar örnek satırlar (kolon yapısı görünsün)",
      "SELECT TOP 8 fis_tarih, fis_tur, fis_hesap_kod, fis_satir_no, fis_meblag0, fis_meblag1, "
      "fis_meblag2, fis_meblag3, fis_aciklama1 FROM MUHASEBE_FISLERI WITH (NOLOCK) "
      "WHERE fis_hesap_kod LIKE '102%' AND fis_iptal = 0 ORDER BY fis_tarih DESC")

    q(c, "5) 698 Enflasyon Düzeltmesi + 690/691/692 dönem kâr hesapları var mı/bakiyesi?",
      f"SELECT LEFT(fis_hesap_kod,3) ana, SUM(fis_meblag0) borc, SUM(fis_meblag1) alacak "
      f"FROM MUHASEBE_FISLERI WITH (NOLOCK) WHERE {flt} AND "
      f"(fis_hesap_kod LIKE '698%' OR fis_hesap_kod LIKE '69%' OR fis_hesap_kod LIKE '8%') "
      f"GROUP BY LEFT(fis_hesap_kod,3) ORDER BY ana")

    print("\n" + "=" * 72)
    print("Bitti. Özellikle (1) kolon toplamları ve (2) fis_tur FARK tablosunu gönderin.")


if __name__ == "__main__":
    main()
