"""
Cari bakiye teşhisi — Mikro cari modülüyle kıyas için.

    .\\.venv\\Scripts\\python.exe cari_diag_cli.py
    .\\.venv\\Scripts\\python.exe cari_diag_cli.py 2025-12-31
"""

from __future__ import annotations

import sys
from datetime import date

from config import load_config
from gercek_durum import _bakiye_caridan
from mikro_api import MikroClient
from mikro_fetch import fetch_cari_bakiye
from mizan_bilanco import tl


def _f(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    asof = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    print(f"Cari bakiye teşhisi — {asof} (firma {cfg.firma_kodu}, yıl {cfg.calisma_yili})\n")
    rows = fetch_cari_bakiye(MikroClient(cfg), asof)
    if not rows:
        print("UYARI: 0 satır döndü — Mikro SQL sessiz hata veya bu tarihte hareket yok.")
        print("       Stok/satış çalışıyorsa sorgu şeması uyumsuz olabilir; geliştiriciye bildirin.\n")
    oz = _bakiye_caridan(rows)
    print("ÖZET:")
    print(f"  Banka net      {tl(oz['nakit_banka']):>18}")
    print(f"  Kasa net       {tl(oz['nakit_kasa']):>18}")
    print(f"  Alacak         {tl(oz['alacak']):>18}")
    print(f"  Borç           {tl(oz['borc']):>18}")
    print(f"  Müşteri avans  {tl(oz['musteri_avans']):>18}")
    print(f"  Satıcı avans   {tl(oz['satici_avans']):>18}")
    print(f"  Hesap sayısı   {oz['cari_hesap_sayisi']:>18}")

    bankalar = []
    for r in rows:
        cins = int(_f(r.get("cins", r.get("CINS"))))
        if cins != 2:
            continue
        kod = str(r.get("kod", r.get("KOD")) or "")
        bh = _f(r.get("borc_h", r.get("BORC_H")))
        ah = _f(r.get("alacak_h", r.get("ALACAK_H")))
        net = bh - ah
        tip = int(_f(r.get("ban_hesap_tip", r.get("BAN_HESAP_TIP"))))
        muh = str(r.get("ban_muh_kod", r.get("BAN_MUH_KOD")) or r.get("muh_kod", r.get("MUH_KOD")) or "")
        bankalar.append((kod, net, bh, ah, tip, muh))

    bankalar.sort(key=lambda x: -abs(x[1]))
    print("\nEN BÜYÜK 10 BANKA (net = borç hareket − alacak hareket):")
    print("  [tip: 0=mevduat 1=kredi — nakitte yalnızca mevduat sayılır]")
    for kod, net, bh, ah, tip, muh in bankalar[:10]:
        etiket = "KREDİ" if tip == 1 else "mevduat"
        print(f"  {kod:<12} {etiket:<8} net {tl(net):>14}  muh={muh}")

    print("\nMikro'da Bankalar listesindeki bakiyeyle üstteki netleri kıyaslayın.")
    print("Fark varsa hangi ban_kod olduğunu not edin.")


if __name__ == "__main__":
    main()
