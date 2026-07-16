"""
Cari bakiye teşhisi — Mikro cari modülüyle kıyas için.

    .\\.venv\\Scripts\\python.exe cari_diag_cli.py
    .\\.venv\\Scripts\\python.exe cari_diag_cli.py 2025-12-31
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date

from config import load_config
from gercek_durum import _bakiye_bilancodan, _bakiye_caridan
from mikro_api import MikroClient
from mikro_fetch import fetch_cari_bakiye, fetch_mizan
from mizan_bilanco import build_bilanco, tl
from ortak import to_float as _f


def _gl_102_bakiye(mizan_rows: list[dict]) -> dict[str, float]:
    """GL mizandan 102.* hesap bakiyeleri (muh_kod eşleştirmesi için)."""
    out: dict[str, float] = {}
    for r in mizan_rows:
        kod = str(r.get("hesap_kodu", r.get("HESAP_KODU")) or "").strip()
        if not kod.startswith("102"):
            continue
        borc = _f(r.get("borc", r.get("BORC")))
        alacak = _f(r.get("alacak", r.get("ALACAK")))
        bakiye = borc - alacak
        if abs(bakiye) >= 0.005:
            out[kod] = bakiye
    return out


def _asof_yili(asof: str) -> int | None:
    try:
        return date.fromisoformat(asof).year
    except ValueError:
        return None


def _gl_karsilastir(
    client: MikroClient, asof: str, oz: dict[str, float], *, etiket: str,
) -> tuple[dict[str, float], float]:
    """GL mizan vs cari tablosu; gl_102 sözlüğü ve 102 toplamını döndürür."""
    mizan = fetch_mizan(client, asof)
    b = build_bilanco(mizan, asof=asof)
    gl = _bakiye_bilancodan(b)
    gl_102 = _gl_102_bakiye(mizan)
    gl_102_top = sum(gl_102.values())
    print(f"\nGL MİZAN KARŞILAŞTIRMA — {etiket}:")
    print(f"   {'':20} {'Cari':>18} {'GL mizan':>18}")
    print(f"   {'Nakit (100-102-108)':20} {tl(oz['nakit_mevcut']):>18} {tl(gl['nakit_mevcut']):>18}")
    print(f"   {'  • yalnız 102.*':20} {tl(oz['nakit_banka']):>18} {tl(gl_102_top):>18}")
    print(f"   {'Alacak (120)':20} {tl(oz['alacak']):>18} {tl(gl['alacak']):>18}")
    print(f"   {'Borç (320)':20} {tl(oz['borc']):>18} {tl(gl['borc']):>18}")
    return gl_102, gl_102_top


def main() -> None:
    asof = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    client = MikroClient(cfg)
    print(f"Cari bakiye teşhisi — {asof} (firma {cfg.firma_kodu}, yıl {cfg.calisma_yili})\n")
    rows = fetch_cari_bakiye(client, asof)
    if not rows:
        print("UYARI: 0 satır döndü — Mikro SQL sessiz hata veya bu tarihte hareket yok.")
        print("       Stok/satış çalışıyorsa sorgu şeması uyumsuz olabilir; geliştiriciye bildirin.\n")
    oz = _bakiye_caridan(rows)
    print("ÖZET (cari hareket):")
    print(f"  Banka net      {tl(oz['nakit_banka']):>18}")
    print(f"  Kasa net       {tl(oz['nakit_kasa']):>18}")
    print(f"  Alacak         {tl(oz['alacak']):>18}")
    print(f"  Borç           {tl(oz['borc']):>18}")
    print(f"  Müşteri avans  {tl(oz['musteri_avans']):>18}")
    print(f"  Satıcı avans   {tl(oz['satici_avans']):>18}")
    print(f"  Hesap sayısı   {oz['cari_hesap_sayisi']:>18}")

    asof_yil = _asof_yili(asof)
    cfg_yil = cfg.calisma_yili or date.today().year
    gl_102: dict[str, float] = {}
    if asof_yil and asof_yil != cfg_yil:
        print(
            f"\n⚠ ÇALIŞMA YILI UYUMSUZ: tarih {asof_yil}, Mikro ayarı {cfg_yil}."
            f"\n  GL mizan {cfg_yil} defterinden gelir — yeni yıl defteri boş veya eksik olabilir."
            f"\n  {asof_yil} bakiyesi için Mikro Ayarları'nda çalışma yılını {asof_yil} yapın."
        )

    try:
        gl_102, gl_102_top = _gl_karsilastir(
            client, asof, oz, etiket=f"çalışma yılı {cfg_yil}",
        )
        if asof_yil and asof_yil != cfg_yil:
            cfg_duz = replace(cfg.normalized(), calisma_yili=asof_yil)
            gl_102, gl_102_top = _gl_karsilastir(
                MikroClient(cfg_duz), asof, oz, etiket=f"tarih yılı {asof_yil} (otomatik)",
            )
        if abs(oz["nakit_banka"] - gl_102_top) > 1000:
            print(
                "\n  ⚠ Cari banka ile GL 102 arasında büyük fark."
                "\n    • Çalışma yılı tarihle uyumlu mu kontrol edin."
                "\n    • Uyumluysa cari hareketler muhasebeleşmemiş olabilir."
            )
    except Exception as exc:  # noqa: BLE001
        print(f"\nGL karşılaştırma atlandı: {exc}")
        gl_102 = {}

    bankalar_mev = []
    bankalar_kredi = []
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
        isim = str(r.get("ban_ismi", r.get("BAN_ISMI")) or "").strip()
        kredi = tip == 1 or muh.startswith("300") or kod.upper().startswith("300")
        gl_b = gl_102.get(muh) if muh else None
        (bankalar_kredi if kredi else bankalar_mev).append((kod, net, tip, muh, isim, gl_b))

    bankalar_mev.sort(key=lambda x: -abs(x[1]))
    bankalar_kredi.sort(key=lambda x: -abs(x[1]))
    print(f"\nMEVDUAT: {len(bankalar_mev)} hesap, toplam net {tl(sum(x[1] for x in bankalar_mev))}")
    print("EN BÜYÜK 10 (nakitte sayılan):")
    print("  [tip: 0=mevduat 1=kredi — 300.* kodları kredi sayılır]")
    for kod, net, _tip, muh, isim, gl_b in bankalar_mev[:10]:
        gl_s = f"  GL={tl(gl_b)}" if gl_b is not None else ""
        ad = f"  ({isim})" if isim else ""
        print(f"  {kod:<12} net {tl(net):>14}  muh={muh}{ad}{gl_s}")
    if bankalar_kredi:
        kredi_top = sum(x[1] for x in bankalar_kredi)
        print(f"\nKREDİ / 300.* (nakitten hariç): {len(bankalar_kredi)} hesap, toplam net {tl(kredi_top)}")

    print("\nMikro'da Bankalar listesindeki bakiyeyle üstteki netleri kıyaslayın.")
    print("Fark varsa hangi ban_kod olduğunu not edin.")
    print("Özellikle 102.009 gibi büyük hesapların Mikro'daki bakiyesini kontrol edin.")


if __name__ == "__main__":
    main()
