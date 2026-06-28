"""
ANINDA BİLANÇO — CLI doğrulama aracı.

Kaydedilmiş Mikro ayarlarıyla GL'den tarih itibarıyla mizan→bilanço kurar ve AKTİF/PASİF/FARK
basar. Mantık `mizan_bilanco` modülünde (GUI ile aynı kaynak). Gizli değer yazmaz.

    .\\.venv\\Scripts\\python.exe bilanco_cli.py            # bugün itibarıyla
    .\\.venv\\Scripts\\python.exe bilanco_cli.py 2026-05-31 # belirli tarih
"""

from __future__ import annotations

import sys
from datetime import date

from config import load_config
from mikro_api import MikroClient
from mikro_fetch import fetch_mizan
from mizan_bilanco import bilanco_metni, build_bilanco, tl


def main() -> None:
    asof = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    client = MikroClient(cfg)
    print(f"GL çekiliyor (… {asof} tarihine kadar, firma {cfg.firma_kodu}, yıl {cfg.calisma_yili})…")
    rows = fetch_mizan(client, asof)
    print(f"{len(rows)} hesap geldi.\n")
    b = build_bilanco(rows, asof=asof)
    print(bilanco_metni(b))

    # Cari bakiye karşılaştırması (Gerçek Durum'un kullandığı kaynak)
    try:
        from gercek_durum import _bakiye_bilancodan, _bakiye_caridan
        from mikro_fetch import fetch_cari_bakiye

        cari_rows = fetch_cari_bakiye(client, asof)
        gl = _bakiye_bilancodan(b)
        cr = _bakiye_caridan(cari_rows)
        print("\nKARŞILAŞTIRMA — Cari hareket vs GL mizan:")
        print(f"   {'':20} {'Cari':>18} {'GL mizan':>18}")
        print(f"   {'Nakit':20} {tl(cr['nakit_mevcut']):>18} {tl(gl['nakit_mevcut']):>18}")
        print(f"   {'Alacak':20} {tl(cr['alacak']):>18} {tl(gl['alacak']):>18}")
        print(f"   {'Borç':20} {tl(cr['borc']):>18} {tl(gl['borc']):>18}")
        print(f"   ({cr['cari_hesap_sayisi']} cari/banka/kasa hesabı)")
    except Exception as exc:  # noqa: BLE001
        print(f"\nCari karşılaştırma atlandı: {exc}")

    # Teşhis: ana grup netleri + bilanço-dışı (8/9)
    print("\nTEŞHİS — ana grup netleri (bakiye = borç − alacak):")
    for d in "123456789":
        if d in b.digit_net and abs(b.digit_net[d]) >= 0.005:
            print(f"   {d}xx: {tl(b.digit_net[d]):>20}")
    suc = [s for s in b.sonuc if s.ana[:1] in ("8", "9")]
    if suc:
        print("   ↳ 8xx/9xx (bilanço-dışı):")
        for s in sorted(suc, key=lambda x: -abs(x.tutar))[:12]:
            print(f"      {s.ana}  {s.ad:<32} bakiye {tl(-s.tutar):>16}")
    print("\nNOT: AKTİF=PASİF (FARK≈0) ise mizan doğru. Kapanmış ay sonu (ör. 31.05) en temiz sonucu verir.")


if __name__ == "__main__":
    main()
