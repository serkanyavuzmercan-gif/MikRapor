"""
Cari bakiye teşhisi — Mikro cari modülüyle kıyas için.

    .\\.venv\\Scripts\\python.exe cari_diag_cli.py
    .\\.venv\\Scripts\\python.exe cari_diag_cli.py 2025-12-31
    .\\.venv\\Scripts\\python.exe cari_diag_cli.py --banka        # banka hesabı kırılımı

--banka: cari banka rakamı BAKİYE mi yoksa başka bir şey mi? Borç/alacak kırılımını,
hareket sayısını ve tarih aralığını GL ile yan yana koyar. Cari ile GL 47 kat
ayrıştığında hangisinin doğru olduğunu bu kırılım söyler.
"""

from __future__ import annotations

import sys
from datetime import date

from domain.gercek_durum import _bakiye_bilancodan, _bakiye_caridan
from domain.mizan_bilanco import build_bilanco, tl
from domain.ortak import to_float as _f
from infra.config import load_config
from infra.mikro_api import MikroClient
from infra.mikro_fetch import (
    _bit_son,
    _cha_tl_sql,
    fetch_cari_bakiye,
    fetch_mizan,
    parse_sql_rows,
)
from infra.mukayese_fetch import yil_client


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


def _cari_banka_kirilim(client: MikroClient, asof: str) -> list[dict]:
    """
    Banka hesapları için cari hareketlerin BORÇ/ALACAK kırılımı + adet + tarih aralığı.

    Net rakamı tek başına «bakiye mi akış mı» sorusunu cevaplamıyor. Borç 40M / alacak
    33,6M → net 6,4M ise bu gerçek bir bakiyedir (para girdi, çıktı, kalanı bu).
    Borç 6,4M / alacak 0 ise tek yönlü kayıt var, yani bakiye değil.
    """
    tl_sql = _cha_tl_sql("c")
    sql = (
        "SELECT c.cha_kod AS kod, COUNT(*) AS adet, "
        f"SUM(CASE WHEN c.cha_tip = 0 THEN {tl_sql} ELSE 0 END) AS borc, "
        f"SUM(CASE WHEN c.cha_tip = 1 THEN {tl_sql} ELSE 0 END) AS alacak, "
        "MIN(c.cha_tarihi) AS ilk, MAX(c.cha_tarihi) AS son, "
        "MAX(ISNULL(b.ban_ismi, '')) AS ban_ismi, "
        "MAX(ISNULL(CAST(b.ban_hesap_tip AS int), -1)) AS hesap_tip "
        "FROM CARI_HESAP_HAREKETLERI c WITH (NOLOCK) "
        "JOIN BANKALAR b WITH (NOLOCK) ON b.ban_kod = c.cha_kod "
        "WHERE c.cha_iptal = 0 AND ISNULL(c.cha_hidden, 0) = 0 "
        f"AND c.cha_tarihi < '{_bit_son(asof)}' "
        "GROUP BY c.cha_kod ORDER BY COUNT(*) DESC"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=180, max_attempts=2))


def _banka_teshisi(client: MikroClient, asof: str) -> None:
    """Cari banka rakamının ne olduğunu GL ile yan yana koyarak gösterir."""
    satirlar = _cari_banka_kirilim(client, asof)
    gl_102 = _gl_102_bakiye(fetch_mizan(client, asof))
    if not satirlar:
        print("\nBanka hesabı için cari hareket bulunamadı.")
        return

    print(f"\nBANKA HESABI KIRILIMI — {asof} (kredi hesapları * ile işaretli)")
    print("Soru: cari rakamı bir BAKİYE mi? Borç ve alacak birlikte varsa evet.\n")
    print(f"{'hesap':16} {'adet':>6} {'cari borç':>16} {'cari alacak':>16} "
          f"{'cari net':>15} {'GL net':>14}  ilk → son")
    print("-" * 118)
    t_borc = t_alacak = t_gl = 0.0
    for r in satirlar[:15]:
        kod = str(r.get("kod", r.get("KOD")) or "")
        adet = int(_f(r.get("adet", r.get("ADET"))))
        borc = _f(r.get("borc", r.get("BORC")))
        alacak = _f(r.get("alacak", r.get("ALACAK")))
        gl = gl_102.get(kod, 0.0)
        kredi = int(_f(r.get("hesap_tip", r.get("HESAP_TIP")))) == 1
        ilk = str(r.get("ilk", r.get("ILK")) or "")[:10]
        son = str(r.get("son", r.get("SON")) or "")[:10]
        t_borc += borc
        t_alacak += alacak
        if not kredi:
            t_gl += gl
        isaret = "*" if kredi else " "
        print(f"{kod:15}{isaret} {adet:>6} {tl(borc):>16} {tl(alacak):>16} "
              f"{tl(borc - alacak):>15} {tl(gl):>14}  {ilk} → {son}")
    print("-" * 118)
    print(f"{'TOPLAM':16} {'':>6} {tl(t_borc):>16} {tl(t_alacak):>16} "
          f"{tl(t_borc - t_alacak):>15} {tl(t_gl):>14}")

    print("\nNASIL OKUNUR:")
    if t_alacak < abs(t_borc) * 0.05:
        print("  → Alacak tarafı neredeyse BOŞ: bu bir bakiye değil, tek yönlü kayıt.")
        print("    Cari rakamı nakit mevcudu olarak KULLANILMAMALI, GL doğru kaynaktır.")
    else:
        print("  → Borç ve alacak birlikte dolu: cari rakamı gerçek bir hareket bakiyesi.")
        print("    GL ile aradaki fark muhasebeleşmemiş banka fişi demektir.")
    print("  Kesin cevap: Mikro → Banka → Banka Hesap Durumu ekranındaki bakiyeyi")
    print("  yukarıdaki «cari net» ve «GL net» ile kıyaslayın; hangisine eşitse o doğru.")


def _yil(tarih: str) -> int | None:
    """Elle yazılan tarihi doğrular — typo traceback yerine tek satır uyarı versin."""
    try:
        return date.fromisoformat(tarih).year
    except ValueError:
        print(f"Geçersiz tarih: {tarih} (YYYY-AA-GG bekleniyor)")
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
    argv = [a for a in sys.argv[1:] if a != "--banka"]
    banka_modu = "--banka" in sys.argv
    asof = argv[0] if argv else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    # Veritabanını FİRMA KODU seçer; yıl→firma eşlemesi kataloğdan gelir.
    yil = _yil(asof)
    if yil is None:
        return
    client = yil_client(cfg, yil)
    print(f"Cari bakiye teşhisi — {asof} "
          f"(firma {client.cfg.firma_kodu}, yıl {client.cfg.calisma_yili})\n")
    if banka_modu:
        _banka_teshisi(client, asof)
        return
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

    # Yıl↔çalışma yılı uyumsuzluğu artık elle uyarılmıyor: istemci zaten tarihin
    # yılına göre kuruluyor, o yüzden ikinci bir "otomatik düzeltme" turu da yok.
    gl_102: dict[str, float] = {}
    try:
        gl_102, gl_102_top = _gl_karsilastir(
            client, asof, oz, etiket=f"firma {client.cfg.firma_kodu} / {asof[:4]}",
        )
        if abs(oz["nakit_banka"] - gl_102_top) > 1000:
            print(
                "\n  ⚠ Cari banka ile GL 102 arasında büyük fark."
                "\n    • Bu tarih için doğru veritabanı okundu mu (üstteki firma kodu)?"
                "\n    • Okunduysa cari hareketler muhasebeleşmemiş olabilir."
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
