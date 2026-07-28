"""
ANINDA BİLANÇO — CLI doğrulama aracı.

Kaydedilmiş Mikro ayarlarıyla GL'den tarih itibarıyla mizan→bilanço kurar ve AKTİF/PASİF/FARK
basar. Mantık `mizan_bilanco` modülünde (GUI ile aynı kaynak). Gizli değer yazmaz.

    .\\.venv\\Scripts\\python.exe bilanco_cli.py            # bugün itibarıyla
    .\\.venv\\Scripts\\python.exe bilanco_cli.py 2026-05-31 # belirli tarih
    .\\.venv\\Scripts\\python.exe bilanco_cli.py 2025-12-31 --teshis  # yalnız ucuz teşhis
"""

from __future__ import annotations

import sys
import time
from datetime import date

from domain.mizan_bilanco import bilanco_metni, build_bilanco, tl
from infra.config import load_config
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import fetch_mizan


def main() -> None:
    asof = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    cfg = load_config()
    if not cfg.is_complete():
        print("Ayarlar eksik:", cfg.eksik_alanlar())
        return
    client = MikroClient(cfg)
    print(f"Firma {cfg.firma_kodu}, çalışma yılı {cfg.calisma_yili}, tarih {asof}\n")

    # ÖNCE ucuz teşhis: tek günün fişleri. Mizan sorgusu (alt tarih sınırı yok →
    # tüm tabloyu tarar) canlıda 120 sn zaman aşımına takılıyor; teşhisin ona
    # bağımlı olmaması gerek. «--teshis» ile mizan hiç çekilmez.
    _gun_teshisi(client, asof)
    if "--teshis" in sys.argv:
        return

    print(f"\nGL mizanı çekiliyor (… {asof} tarihine kadar)… bu adım uzun sürebilir.")
    t0 = time.monotonic()
    try:
        rows = fetch_mizan(client, asof)
    except MikroAPIError as exc:
        print(f"   Mizan çekilemedi ({time.monotonic() - t0:.0f} sn sonra): {exc}")
        print("   → Sorgu tüm tabloyu tarıyor. Yukarıdaki açılış fişi bilgisi, mizanın")
        print("     yalnız o yıldan kurulup kurulamayacağını (yani hızlanıp hızlanamayacağını) söyler.")
        return
    print(f"{len(rows)} hesap geldi  ({time.monotonic() - t0:.1f} sn).\n")
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
        print(f"\n   Kalan aktif toplamı {tl(b.aktif_toplam)} — yukarıdaki kapanış fişiyle kıyaslayın.")

    print("\nNOT: AKTİF=PASİF (FARK≈0) ise mizan doğru. Kapanmış ay sonu (ör. 31.05) en temiz sonucu verir.")


def _gun_teshisi(client, asof: str) -> None:
    """
    Yıl sonu KAPANIŞ ve yıl başı AÇILIŞ fişleri — mizanı hiç çekmeden.

    İki soruyu ucuza cevaplar (tek günlük sorgular, tarih aralığı indeksli):

    1) 31 Aralık bilançosu neden çökük çıkıyor? Kapanış fişi o gün bütün bakiyeleri
       sıfırlar; kümülatif mizan tam o güne kadar alınınca bilanço boşalmış görünür
       (canlıda 134 milyon ciroluk firmada aktif toplamı 176 bin TL çıktı).
    2) Mizan neden bu kadar yavaş, hızlandırılabilir mi? Sorgunun alt tarih sınırı
       yok, tüm tabloyu tarıyor ve 120 sn zaman aşımına takılıyor. Yıl başında
       AÇILIŞ fişi varsa mizan yalnız o yıldan kurulabilir — açılış fişi önceki
       yılların bakiyesini zaten taşır.
    """
    from domain.ortak import to_float as _f
    from infra.mikro_fetch import fetch_gl_gun_fisleri

    def gun_dok(gun: str, baslik: str) -> float:
        print(f"{baslik} — {gun}")
        t0 = time.monotonic()
        try:
            fisler = fetch_gl_gun_fisleri(client, gun)
        except MikroAPIError as exc:
            print(f"   okunamadı: {exc}\n")
            return 0.0
        sure = time.monotonic() - t0
        if not fisler:
            print(f"   o gün hiç yevmiye fişi yok  ({sure:.1f} sn)\n")
            return 0.0
        ozkaynakli = [f for f in fisler
                      if _f(f.get("ozkaynak_var", f.get("OZKAYNAK_VAR"))) > 0]
        print(f"   {len(fisler)} fiş, {len(ozkaynakli)} tanesi özkaynak (5xx) satırlı  "
              f"({sure:.1f} sn)")
        print(f"      {'yevmiye':>10} {'satır':>7} {'borç toplamı':>22}  içerik")
        for f in fisler[:8]:
            oz = _f(f.get("ozkaynak_var", f.get("OZKAYNAK_VAR"))) > 0
            ge = _f(f.get("gelir_var", f.get("GELIR_VAR"))) > 0
            ic = " + ".join(x for x, v in (("5xx özkaynak", oz), ("6xx gelir", ge)) if v) or "—"
            print(f"      {str(f.get('yevmiye', f.get('YEVMIYE', ''))):>10} "
                  f"{int(_f(f.get('satir', f.get('SATIR')))):>7} "
                  f"{tl(_f(f.get('borc', f.get('BORC')))):>22}  {ic}")
        print()
        return max((_f(f.get("borc", f.get("BORC"))) for f in ozkaynakli), default=0.0)

    yil = int(asof[:4])
    kapanis = gun_dok(f"{yil}-12-31", "YIL SONU KAPANIŞ FİŞİ") if asof.endswith("-12-31") else 0.0
    acilis = gun_dok(f"{yil}-01-01", "YIL BAŞI AÇILIŞ FİŞİ")

    print("SONUÇ:")
    if kapanis > 0:
        print(f"   • {yil}-12-31'de {tl(kapanis)} tutarında kapanış fişi VAR. Bilanço tam o güne")
        print("     kadar alınınca bu fiş bakiyeleri sıfırlar → çökük bilanço. 30 Aralık'ı seçin.")
    elif asof.endswith("-12-31"):
        print("   • Yıl sonunda kapanış fişi yok; çökük bilançonun sebebi başka.")
    if acilis > 0:
        print(f"   • {yil}-01-01'de {tl(acilis)} tutarında açılış fişi VAR → mizan tüm geçmiş")
        print("     yerine yalnız bu yıldan kurulabilir. Sorgu bu sayede çok daha hızlanır.")
    else:
        print(f"   • {yil}-01-01'de açılış fişi YOK → mizan geriye doğru taranmak zorunda.")


if __name__ == "__main__":
    main()
