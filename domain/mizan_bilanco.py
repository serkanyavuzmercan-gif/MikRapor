"""
Mizan → Bilanço motoru (Mikro GL'den, canlı doğrulanmış).

Mikro MUHASEBE_FISLERI'nden tarih itibarıyla mizan (hesap başına borç/alacak/bakiye) ve
Tek Düzen Hesap Planı yapısında bilanço kurar. `bilanco_cli.py` ile Mikro'nun kendi mizanına
KURUŞU KURUŞUNA tutturuldu (100,102,120,153,252,300,320,500,502,590 … hepsi).

Kritik: `fis_meblag0` = İŞARETLİ TL tutar (poz=borç, neg=alacak). meblag1=USD (alacak DEĞİL).
Bakiye = SUM(fis_meblag0). Bkz. MIKRO-SEMA-NOTLARI.md.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from html import escape

from domain.ortak import csv_metin, csv_sayi, tl
from domain.ortak import to_float as _f

# Tek Düzen Hesap Planı — yaygın ana hesap adları (bilinmeyen kod numarasıyla görünür)
HESAP_ADLARI: dict[str, str] = {
    # 1 — Dönen Varlıklar
    "100": "Kasa", "101": "Alınan Çekler", "102": "Bankalar",
    "103": "Verilen Çekler ve Ödeme Emirleri (-)", "108": "Diğer Hazır Değerler",
    "110": "Hisse Senetleri", "120": "Alıcılar", "121": "Alacak Senetleri",
    "122": "Alacak Senetleri Reeskontu (-)", "126": "Verilen Depozito ve Teminatlar",
    "128": "Şüpheli Ticari Alacaklar", "129": "Şüpheli Ticari Alacaklar Karşılığı (-)",
    "131": "Ortaklardan Alacaklar", "136": "Diğer Çeşitli Alacaklar",
    "150": "İlk Madde ve Malzeme", "151": "Yarı Mamuller", "152": "Mamuller",
    "153": "Ticari Mallar", "157": "Diğer Stoklar", "159": "Verilen Sipariş Avansları",
    "180": "Gelecek Aylara Ait Giderler", "190": "Devreden KDV", "191": "İndirilecek KDV",
    "193": "Peşin Ödenen Vergiler ve Fonlar", "195": "İş Avansları", "196": "Personel Avansları",
    "197": "Sayım ve Tesellüm Noksanları",
    # 2 — Duran Varlıklar
    "220": "Alıcılar (UV)", "226": "Verilen Depozito ve Teminatlar (UV)",
    "240": "Bağlı Menkul Kıymetler", "250": "Arazi ve Arsalar", "251": "Yeraltı/Yerüstü Düzenleri",
    "252": "Binalar", "253": "Tesis, Makine ve Cihazlar", "254": "Taşıtlar", "255": "Demirbaşlar",
    "256": "Diğer Maddi Duran Varlıklar", "257": "Birikmiş Amortismanlar (-)",
    "258": "Yapılmakta Olan Yatırımlar", "260": "Haklar", "264": "Özel Maliyetler",
    "267": "Diğer Maddi Olmayan Duran Varlıklar", "268": "Birikmiş Amortismanlar (-)",
    "280": "Gelecek Yıllara Ait Giderler",
    # 3 — Kısa Vadeli Yabancı Kaynaklar
    "300": "Banka Kredileri", "303": "Uzun Vad. Kredilerin Anapara Taksitleri",
    "320": "Satıcılar", "321": "Borç Senetleri", "322": "Borç Senetleri Reeskontu (-)",
    "326": "Alınan Depozito ve Teminatlar", "329": "Diğer Ticari Borçlar",
    "331": "Ortaklara Borçlar", "335": "Personele Borçlar", "336": "Diğer Çeşitli Borçlar",
    "340": "Alınan Sipariş Avansları", "360": "Ödenecek Vergi ve Fonlar",
    "361": "Ödenecek Sosyal Güvenlik Kesintileri", "368": "Vadesi Geçmiş Ertelenmiş Vergi",
    "369": "Ödenecek Diğer Yükümlülükler", "370": "Dönem Kârı Vergi Karşılığı",
    "371": "Dönem Kârının Peşin Öd. Vergi (-)", "372": "Kıdem Tazminatı Karşılığı",
    "373": "Maliyet Giderleri Karşılığı", "381": "Gider Tahakkukları", "391": "Hesaplanan KDV",
    "397": "Sayım ve Tesellüm Fazlaları",
    # 4 — Uzun Vadeli Yabancı Kaynaklar
    "400": "Banka Kredileri (UV)", "420": "Satıcılar (UV)", "421": "Borç Senetleri (UV)",
    "426": "Alınan Depozito ve Teminatlar (UV)", "472": "Kıdem Tazminatı Karşılığı",
    "479": "Diğer Borç ve Gider Karşılıkları",
    # 5 — Özkaynaklar
    "500": "Sermaye", "501": "Ödenmemiş Sermaye (-)", "502": "Sermaye Düzeltmesi Olumlu Farkları",
    "503": "Sermaye Düzeltmesi Olumsuz Farkları (-)", "520": "Hisse Senedi İhraç Primleri",
    "540": "Yasal Yedekler", "541": "Statü Yedekleri", "542": "Olağanüstü Yedekler",
    "548": "Diğer Kâr Yedekleri", "549": "Özel Fonlar", "570": "Geçmiş Yıllar Kârları",
    "580": "Geçmiş Yıllar Zararları (-)", "590": "Dönem Net Kârı", "591": "Dönem Net Zararı (-)",
}

# Bölüm başlıkları (ilk haneye göre)
AKTIF_BOLUM = {"1": "I. DÖNEN VARLIKLAR", "2": "II. DURAN VARLIKLAR"}
PASIF_BOLUM = {
    "3": "III. KISA VADELİ YABANCI KAYNAKLAR",
    "4": "IV. UZUN VADELİ YABANCI KAYNAKLAR",
    "5": "V. ÖZKAYNAKLAR",
}


def ana_hesap(kod: object) -> str:
    """'320.01.0018' -> '320' · '102' -> '102'."""
    k = str(kod or "").split(".")[0].strip()
    return k[:3]


def hesap_adi(ana: str) -> str:
    return HESAP_ADLARI.get(ana, f"{ana} Hesabı")


@dataclass
class BilancoSatir:
    ana: str
    ad: str
    tutar: float


@dataclass
class Bilanco:
    asof: str = ""
    aktif: list[BilancoSatir] = field(default_factory=list)   # 1,2
    pasif: list[BilancoSatir] = field(default_factory=list)   # 3,4,5
    sonuc: list[BilancoSatir] = field(default_factory=list)   # 6,7,8,9
    donem_kz: float = 0.0
    digit_net: dict = field(default_factory=dict)
    aktif_toplam: float = 0.0
    pasif_toplam: float = 0.0

    @property
    def fark(self) -> float:
        return self.aktif_toplam - self.pasif_toplam

    @property
    def denge_yuzde(self) -> float:
        return (abs(self.fark) / self.aktif_toplam * 100) if self.aktif_toplam else 0.0

    @property
    def dengede(self) -> bool:
        return abs(self.fark) < 1.0 or self.denge_yuzde < 1.0


def build_bilanco(rows: list[dict], asof: str = "") -> Bilanco:
    """
    Mizan satırlarından (hesap_kodu, borc, alacak) bilanço kurar.
    Çift kayıt: Σ bakiye(tüm) = 0 → AKTİF(1,2) = PASİF(3,4,5) + Dönem K/Z (= -(Σ bakiye 6,7,8,9)).
    """
    grup: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        kod = r.get("hesap_kodu") or r.get("HESAP_KODU") or r.get("fis_hesap_kod")
        ana = ana_hesap(kod)
        if not ana or not ana[:1].isdigit():
            continue
        grup[ana][0] += _f(r.get("borc", r.get("BORC")))
        grup[ana][1] += _f(r.get("alacak", r.get("ALACAK")))

    b = Bilanco(asof=asof)
    donem_kz = 0.0
    digit_net: dict[str, float] = defaultdict(float)
    for ana in sorted(grup):
        borc, alacak = grup[ana]
        bakiye = borc - alacak
        d = ana[:1]
        digit_net[d] += bakiye
        if d in ("1", "2"):
            if abs(bakiye) >= 0.005:
                b.aktif.append(BilancoSatir(ana, hesap_adi(ana), bakiye))
            b.aktif_toplam += bakiye
        elif d in ("3", "4", "5"):
            kaynak = -bakiye
            if abs(kaynak) >= 0.005:
                b.pasif.append(BilancoSatir(ana, hesap_adi(ana), kaynak))
            b.pasif_toplam += kaynak
        else:  # 6,7,8,9 → dönem sonucuna kapanır
            donem_kz += -bakiye
            if abs(bakiye) >= 0.005:
                b.sonuc.append(BilancoSatir(ana, hesap_adi(ana), -bakiye))

    b.donem_kz = donem_kz
    b.pasif_toplam += donem_kz
    b.digit_net = dict(digit_net)
    return b


# --- Metin raporu (CLI) ---

def bilanco_metni(b: Bilanco) -> str:
    out = [f"BİLANÇO — {b.asof} tarihi itibarıyla (canlı/yönetim bilançosu)", "=" * 64]

    def blok(satirlar, bolumler):
        for d, baslik in bolumler.items():
            ds = [s for s in satirlar if s.ana[:1] == d]
            if not ds:
                continue
            out.append(f"\n{baslik}")
            for s in ds:
                out.append(f"   {s.ana}  {s.ad:<40} {tl(s.tutar):>18}")

    out.append("\n### AKTİF (VARLIKLAR)")
    blok(b.aktif, AKTIF_BOLUM)
    out.append("-" * 64)
    out.append(f"   {'AKTİF TOPLAMI':<46} {tl(b.aktif_toplam):>18}")
    out.append("\n### PASİF (KAYNAKLAR)")
    blok(b.pasif, PASIF_BOLUM)
    out.append(f"\n   {'Dönem Net Kârı/Zararı':<46} {tl(b.donem_kz):>18}")
    out.append("-" * 64)
    out.append(f"   {'PASİF TOPLAMI':<46} {tl(b.pasif_toplam):>18}")
    out.append("\n" + "=" * 64)
    durum = "✓ DENGEDE" if abs(b.fark) < 1.0 else (
        f"≈ DENGEDE (kalan %{b.denge_yuzde:.2f})" if b.dengede else "✗ FARK VAR")
    out.append(f"DENGE: AKTİF {tl(b.aktif_toplam)} | PASİF {tl(b.pasif_toplam)} | FARK {tl(b.fark)}  {durum}")
    return "\n".join(out)


def bilanco_csv(b: Bilanco) -> str:
    """Bilançoyu CSV'ye çevirir (; ayraç, Türkçe ondalık — TR Excel uyumlu)."""
    s = csv_sayi
    ad = csv_metin

    out = ["Taraf;Bölüm;Hesap;Tutar (TL)"]
    out.append(f"BİLANÇO;{b.asof} tarihi itibarıyla;;")

    def blok(taraf: str, satirlar: list, bolumler: dict) -> None:
        for d, baslik in bolumler.items():
            ds = [x for x in satirlar if x.ana[:1] == d]
            if not ds and not (taraf == "PASİF" and d == "5"):
                continue
            for x in ds:
                out.append(f"{taraf};{ad(baslik)};{x.ana} {ad(x.ad)};{s(x.tutar)}")
            if taraf == "PASİF" and d == "5":
                out.append(f"{taraf};{ad(baslik)};Dönem Net Kârı/Zararı;{s(b.donem_kz)}")

    blok("AKTİF", b.aktif, AKTIF_BOLUM)
    out.append(f"AKTİF;;AKTİF TOPLAMI;{s(b.aktif_toplam)}")
    blok("PASİF", b.pasif, PASIF_BOLUM)
    out.append(f"PASİF;;PASİF TOPLAMI;{s(b.pasif_toplam)}")
    out.append(f"DENGE;;Aktif-Pasif Farkı;{s(b.fark)}")
    return "\r\n".join(out)


# --- HTML (GUI ekranı için: özet KPI kartları + Aktif | Pasif yan yana) ---

def _kpi_hucre(baslik: str, deger: str, bg: str, vrenk: str) -> str:
    return (
        f'<td width="25%" bgcolor="{bg}" style="padding:12px 14px;">'
        f'<div style="font-size:11px; color:#64748b;">{escape(baslik)}</div>'
        f'<div style="font-size:18px; font-weight:800; color:{vrenk};">{escape(deger)}</div>'
        f'</td>'
    )


def bilanco_html(b: Bilanco, firma: str = "") -> str:
    # Detay kolonları
    def aktif_kolon():
        h = []
        for d, baslik in AKTIF_BOLUM.items():
            ds = [s for s in b.aktif if s.ana[:1] == d]
            if not ds:
                continue
            h.append(f'<tr><td colspan="2" class="bolum">{escape(baslik)}</td></tr>')
            for s in ds:
                h.append(f'<tr><td class="hesap">{s.ana} &nbsp; {escape(s.ad)}</td>'
                         f'<td class="tutar">{tl(s.tutar)}</td></tr>')
        h.append(f'<tr class="toplam"><td>AKTİF TOPLAMI</td><td class="tutar">{tl(b.aktif_toplam)}</td></tr>')
        return "".join(h)

    def pasif_kolon():
        h = []
        for d, baslik in PASIF_BOLUM.items():
            ds = [s for s in b.pasif if s.ana[:1] == d]
            if not ds and d != "5":
                continue
            h.append(f'<tr><td colspan="2" class="bolum">{escape(baslik)}</td></tr>')
            for s in ds:
                h.append(f'<tr><td class="hesap">{s.ana} &nbsp; {escape(s.ad)}</td>'
                         f'<td class="tutar">{tl(s.tutar)}</td></tr>')
            if d == "5":
                h.append('<tr><td class="hesap"><b>Dönem Net Kârı/Zararı</b></td>'
                         f'<td class="tutar"><b>{tl(b.donem_kz)}</b></td></tr>')
        h.append(f'<tr class="toplam"><td>PASİF TOPLAMI</td><td class="tutar">{tl(b.pasif_toplam)}</td></tr>')
        return "".join(h)

    # Denge & dönem K/Z renkleri
    if abs(b.fark) < 1.0:
        denge_txt, denge_bg, denge_vr = "✓ DENGEDE", "#e8f6ee", "#15803d"
    elif b.dengede:
        denge_txt, denge_bg, denge_vr = f"≈ %{b.denge_yuzde:.2f}", "#fdf3e0", "#b45309"
    else:
        denge_txt, denge_bg, denge_vr = "✗ FARK", "#fdecec", "#b91c1c"
    kz_bg, kz_vr = ("#e8f6ee", "#15803d") if b.donem_kz >= 0 else ("#fdecec", "#b91c1c")

    kpi = (
        '<table width="100%" cellspacing="8" cellpadding="0"><tr>'
        + _kpi_hucre("TOPLAM AKTİF", tl(b.aktif_toplam), "#eef4ff", "#1d4ed8")
        + _kpi_hucre("TOPLAM PASİF", tl(b.pasif_toplam), "#eef4ff", "#1d4ed8")
        + _kpi_hucre("DÖNEM NET K/Z", tl(b.donem_kz), kz_bg, kz_vr)
        + _kpi_hucre("DENGE", denge_txt, denge_bg, denge_vr)
        + '</tr></table>'
    )

    firma_satir = f'&nbsp;·&nbsp; <b>{escape(firma)}</b>' if firma else ""
    # İçerik sabit genişlikli (1040px) ve ortalanmış: geniş ekranda iki uca yapışıp
    # ortada boşluk kalmasın, belge gibi dursun. Boş yan hücreler içeriği ortalar.
    return f"""
<html><head><style>
  body {{ font-family:'Segoe UI',sans-serif; color:#1f2937; font-size:12px; }}
  .alt {{ color:#6b7280; font-size:11px; }}
  table.ic {{ border-collapse:collapse; }}
  td.bolum {{ font-weight:700; color:#374151; padding:12px 4px 5px; border-bottom:1px solid #e2e6ec; }}
  td.hesap {{ padding:4px 4px; color:#374151; }}
  td.tutar {{ padding:4px 4px; text-align:right; white-space:nowrap; }}
  tr.toplam td {{ font-weight:800; color:#111827; border-top:2px solid #cbd2dc; padding-top:7px; }}
  h3 {{ color:#2f6fed; margin:0 0 6px; font-size:14px; }}
</style></head><body>
<table width="100%" cellspacing="0" cellpadding="0"><tr>
  <td>&nbsp;</td>
  <td width="1040">
    <div class="alt">ANINDA BİLANÇO &nbsp;·&nbsp; {escape(b.asof)} tarihi itibarıyla{firma_satir}<br>
    <span style="color:#94a3b8;">canlı/yönetim bilançosu — kesin dönem sonucu için ay sonu kapanışı esastır</span></div>
    <br>
    {kpi}
    <br>
    <table width="1040" cellspacing="16" cellpadding="0"><tr>
      <td width="504" valign="top" bgcolor="#f7f9fc" style="padding:14px 16px;">
        <h3>AKTİF (VARLIKLAR)</h3><table class="ic" width="100%">{aktif_kolon()}</table></td>
      <td width="504" valign="top" bgcolor="#f7f9fc" style="padding:14px 16px;">
        <h3>PASİF (KAYNAKLAR)</h3><table class="ic" width="100%">{pasif_kolon()}</table></td>
    </tr></table>
  </td>
  <td>&nbsp;</td>
</tr></table>
</body></html>
"""
