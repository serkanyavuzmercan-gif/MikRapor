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

from domain.mizan_bilanco import bilanco_metni, build_bilanco, tl
from infra.config import load_config
from infra.mikro_api import MikroClient
from infra.mikro_fetch import fetch_mizan


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

    # Cari bakiye karşılaştırması (Nakit & Kârlılık'ın kullandığı kaynak)
    try:
        from domain.gercek_durum import _bakiye_bilancodan, _bakiye_caridan
        from infra.mikro_fetch import fetch_cari_bakiye

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
    if asof.endswith("-12-31"):
        _kapanis_teshisi(client, asof, b)

    print("\nNOT: AKTİF=PASİF (FARK≈0) ise mizan doğru. Kapanmış ay sonu (ör. 31.05) en temiz sonucu verir.")


def _kapanis_teshisi(client, asof: str, b) -> None:
    """
    31 Aralık bilançosu neden çökük çıkıyor? — yıl sonu kapanış fişi teşhisi.

    Kapanış fişi tam o gün bütün bakiyeleri sıfırlar; kümülatif mizan o güne kadar
    alınınca bilanço boşalmış görünür (canlıda 134 milyon ciroluk firmada aktif
    toplamı 176 bin TL çıktı). Bir gün öncesiyle kıyaslamak sorunu kesinleştirir.
    """
    from datetime import timedelta

    from domain.ortak import to_float as _f
    from infra.mikro_fetch import fetch_gl_gun_fisleri

    onceki = (date.fromisoformat(asof) - timedelta(days=1)).isoformat()
    print(f"\nKAPANIŞ TEŞHİSİ — {asof} bir yıl sonu; kapanış fişi bakiyeleri sıfırlar mı?")
    onceki_b = build_bilanco(fetch_mizan(client, onceki), asof=onceki)
    print(f"   Aktif toplamı  {onceki}:  {tl(onceki_b.aktif_toplam):>20}")
    print(f"   Aktif toplamı  {asof}:  {tl(b.aktif_toplam):>20}")

    fisler = fetch_gl_gun_fisleri(client, asof)
    kapanis = [f for f in fisler if _f(f.get("ozkaynak_var", f.get("OZKAYNAK_VAR"))) > 0]
    print(f"\n   {asof} günü {len(fisler)} yevmiye fişi var; "
          f"{len(kapanis)} tanesi özkaynak (5xx) satırı içeriyor:")
    print(f"      {'yevmiye':>10} {'satır':>7} {'borç toplamı':>22}  içerik")
    for f in fisler[:10]:
        oz = _f(f.get("ozkaynak_var", f.get("OZKAYNAK_VAR"))) > 0
        ge = _f(f.get("gelir_var", f.get("GELIR_VAR"))) > 0
        ic = " + ".join(x for x, v in (("5xx özkaynak", oz), ("6xx gelir", ge)) if v) or "—"
        print(f"      {str(f.get('yevmiye', f.get('YEVMIYE', ''))):>10} "
              f"{int(_f(f.get('satir', f.get('SATIR')))):>7} "
              f"{tl(_f(f.get('borc', f.get('BORC')))):>22}  {ic}")

    if onceki_b.aktif_toplam > b.aktif_toplam * 5:
        print(f"\n   → DOĞRULANDI: bir gün öncesi {onceki_b.aktif_toplam / max(b.aktif_toplam, 1):.0f} "
              "kat büyük. 31 Aralık bilançosu kapanış fişini içerdiği için çöküyor.")
        print(f"      Gerçek yıl sonu bilançosu için {onceki} tarihini kullanın.")
    else:
        print("\n   → Kapanış fişi bakiyeleri sıfırlamıyor; sorun başka yerde.")


if __name__ == "__main__":
    main()
