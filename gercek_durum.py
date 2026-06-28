"""
Gerçek Durum motoru — Mikro'dan DOĞRUDAN, operasyonel gerçeği gösterir.

Resmi tablolar (Bilanço / Gelir Tablosu) tek düzen hesap planı üzerinden kurulur ve mali
müşavir 602/623 gibi "Diğer" kalemlerle, maliyet kapanışı zamanlamasıyla kâr marjını sektör
ortalamasına çekebilir. Bu motor ise GL'nin oynanabilir kısmından bağımsız iki sert kaynağa
dayanır:

  1) STOK_HAREKETLERI → fiilen depodan çıkan satış / giren alış → operasyonel brüt marj
  2) Banka hareketleri (CARI_HESAP_HAREKETLERI ⨝ BANKALAR) → fiilen giren/çıkan nakit
  3) Cari hareket bakiyeleri (CARI_HESAP_HAREKETLERI) → nakit, alacak, borç
     (GL mizanı yerine — Mikro cari modülüyle aynı kaynak)

Ayrıca resmi Gelir Tablosu (varsa) ile yan yana konup FARK (gizlenen marj) sayısallaştırılır.

İŞARET KURALI: STOK_HAREKETLERI.sth_tutar pozitif (satır tutarı); sınıflama sth_tip/sth_evraktip
ile yapılır. Bakiye = SUM(fis_meblag0): poz=borç (varlık), neg=alacak (borç). Bkz. MIKRO-SEMA-NOTLARI.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from mizan_bilanco import Bilanco

from gercek_durum_ayarlar import GercekDurumAyarlar

# --- Hareket sınıflama (MIKRO-SEMA-NOTLARI ile doğrulanmış tip/evraktip kodları) ---
SATIS_TIP = 1   # çıkış
ALIS_TIP = 0    # giriş
EVRAKTIP_SATIS_IRSALIYE = 1
EVRAKTIP_SATIS_FATURA = 4
EVRAKTIP_ALIS_FATURA = 3
EVRAKTIP_ALIS_IRSALIYE = 12

# Satış / alış evraktip kümeleri — ayrı seçilir (Mikro kayıt tarzı firmaya göre değişir).
SATIS_EVRAKTIPLERI = {
    "sevk": {EVRAKTIP_SATIS_IRSALIYE, EVRAKTIP_SATIS_FATURA},
    "fatura": {EVRAKTIP_SATIS_FATURA},
}


def _alis_evraktip_kumesi(alis_bazi: str) -> set[int]:
    if alis_bazi == "irsaliye":
        return {EVRAKTIP_ALIS_IRSALIYE}
    if alis_bazi == "ikisi":
        return {EVRAKTIP_ALIS_FATURA, EVRAKTIP_ALIS_IRSALIYE}
    return {EVRAKTIP_ALIS_FATURA}

# Bilanço ile aynı nakit hesapları (103 Verilen Çekler hariç — kontra, nakit değil)
_NAKIT_ANA = frozenset({"100", "101", "102", "108"})

# Mikro cha_cari_cins
_CARI_CINS = 0
_BANKA_CINS = 2
_KASA_CINS = 4


def _f(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _i(v: object) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return -1


def yuzde(v: float) -> str:
    """12.5 -> '%12,5' (Türkçe ondalık)."""
    return ("%" + f"{v:.1f}").replace(".", ",")


@dataclass
class AyTrend:
    """Bir ayın (YYYY-MM) operasyonel & nakit özeti — trend grafiği için."""
    ay: str
    satis: float = 0.0
    alis: float = 0.0
    nakit_giren: float = 0.0
    nakit_cikan: float = 0.0

    @property
    def brut(self) -> float:
        return self.satis - self.alis

    @property
    def nakit_net(self) -> float:
        return self.nakit_giren - self.nakit_cikan


@dataclass
class GercekDurum:
    bas: str = ""
    bit: str = ""
    satis_bazi: str = "sevk"  # "sevk" | "fatura"

    # Operasyonel (stok hareketinden)
    gercek_satis: float = 0.0
    gercek_alis: float = 0.0
    satis_irsaliye: float = 0.0
    satis_fatura: float = 0.0
    alis_fatura: float = 0.0
    alis_irsaliye: float = 0.0
    tum_cikis: float = 0.0          # tip=1 tüm çıkışlar (evraktip filtresiz)
    tum_giris: float = 0.0          # tip=0 tüm girişler
    siniflandirilmayan_cikis: float = 0.0
    siniflandirilmayan_giris: float = 0.0
    stok_kirilim_sayisi: int = 0
    stok_hareket_adet: int = 0
    siniflandirma_fallback: bool = False  # bilinen evraktip dışı → tüm çıkış/giriş kullanıldı

    # Nakit (banka)
    nakit_giren: float = 0.0
    nakit_cikan: float = 0.0

    # Bakiyeler (asof = bit) — varsayılan kaynak: cari hareketleri
    nakit_mevcut: float = 0.0   # banka + kasa
    nakit_banka: float = 0.0
    nakit_kasa: float = 0.0
    alacak: float = 0.0         # müşteriden tahsil edilecek
    borc: float = 0.0           # satıcıya ödenecek
    musteri_avans: float = 0.0
    satici_avans: float = 0.0
    bakiye_kaynagi: str = ""    # "cari" | "cari+gl" | "mizan" | "bakiye_ozet"
    cari_hesap_sayisi: int = 0
    musteri_avans_goster: bool = True
    ayar_ozet: str = ""

    # GL mizan karşılaştırması (varsa)
    gl_nakit_mevcut: float | None = None
    gl_alacak: float | None = None
    gl_borc: float | None = None

    # Resmi GL (varsa, karşılaştırma için)
    resmi_brut_marj: float | None = None
    resmi_net_marj: float | None = None
    resmi_net_kar: float | None = None
    resmi_net_satis: float | None = None
    resmi_brut_kar: float | None = None
    resmi_smm: float | None = None   # |62xx| toplam (GL satışların maliyeti)

    trend: list[AyTrend] = field(default_factory=list)

    @property
    def smm_stok_farki(self) -> float | None:
        """Resmi SMM − stok alışı ≈ 623 + stok değişimi + maliyet kapanışı farkı."""
        if self.resmi_smm is None:
            return None
        return self.resmi_smm - self.gercek_alis

    @property
    def stok_degisim_etkisi(self) -> float | None:
        """Operasyonel brüt − resmi brüt (≈ smm_stok_farki, satışlar uyumluysa)."""
        if self.resmi_brut_kar is None:
            return None
        return self.gercek_brut_kar - self.resmi_brut_kar

    # --- Operasyonel sonuçlar ---
    @property
    def gercek_brut_kar(self) -> float:
        return self.gercek_satis - self.gercek_alis

    @property
    def gercek_brut_marj(self) -> float:
        return (self.gercek_brut_kar / self.gercek_satis * 100) if self.gercek_satis else 0.0

    @property
    def nakit_net(self) -> float:
        return self.nakit_giren - self.nakit_cikan

    @property
    def net_isletme_sermayesi(self) -> float:
        """Nakit + alacak − borç − müşteri avansı + satıcı avansı."""
        return self.nakit_mevcut + self.alacak - self.borc - self.musteri_avans + self.satici_avans

    @property
    def veri_eksik(self) -> bool:
        """Dönemde stok hareketi yok veya sınıflandırılamadı."""
        return self.stok_kirilim_sayisi == 0 or (
            self.gercek_satis == 0 and self.tum_cikis > 0
        )

    # --- Resmi ile fark (gizlenen marj) ---
    @property
    def marj_farki(self) -> float | None:
        if self.resmi_brut_marj is None:
            return None
        return self.gercek_brut_marj - self.resmi_brut_marj

    @property
    def gizlenen_brut(self) -> float | None:
        """Gerçek marj resmi net satışa uygulanınca ortaya çıkan ek brüt kâr (yaklaşık)."""
        if self.resmi_brut_marj is None or self.resmi_net_satis is None:
            return None
        return (self.gercek_brut_marj - self.resmi_brut_marj) / 100 * self.resmi_net_satis


def _siniflandir_stok(
    rows: list[dict], satis_bazi: str, alis_bazi: str = "fatura",
) -> dict[str, float]:
    """STOK_HAREKETLERI ham kırılımını satış/alış toplamlarına indirger."""
    sat_kume = SATIS_EVRAKTIPLERI.get(satis_bazi, SATIS_EVRAKTIPLERI["sevk"])
    alis_kume = _alis_evraktip_kumesi(alis_bazi)
    out = {
        "satis": 0.0, "alis": 0.0,
        "satis_irsaliye": 0.0, "satis_fatura": 0.0,
        "alis_fatura": 0.0, "alis_irsaliye": 0.0,
        "tum_cikis": 0.0, "tum_giris": 0.0,
        "siniflandirilmayan_cikis": 0.0, "siniflandirilmayan_giris": 0.0,
        "hareket_adet": 0.0,
    }
    for r in rows:
        tip = _i(r.get("sth_tip", r.get("STH_TIP")))
        ev = _i(r.get("sth_evraktip", r.get("STH_EVRAKTIP")))
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        out["hareket_adet"] += _f(r.get("adet", r.get("ADET")))
        if tip == SATIS_TIP:
            out["tum_cikis"] += tutar
            if ev == EVRAKTIP_SATIS_IRSALIYE:
                out["satis_irsaliye"] += tutar
            elif ev == EVRAKTIP_SATIS_FATURA:
                out["satis_fatura"] += tutar
            if ev in sat_kume:
                out["satis"] += tutar
            else:
                out["siniflandirilmayan_cikis"] += tutar
        elif tip == ALIS_TIP:
            out["tum_giris"] += tutar
            if ev == EVRAKTIP_ALIS_FATURA:
                out["alis_fatura"] += tutar
            elif ev == EVRAKTIP_ALIS_IRSALIYE:
                out["alis_irsaliye"] += tutar
            if ev in alis_kume:
                out["alis"] += tutar
            else:
                out["siniflandirilmayan_giris"] += tutar
    # Bilinen evraktip dışı hareket varsa tüm çıkış/girişe düş (sıfır görünmesin)
    if out["satis"] < 0.005 and out["tum_cikis"] > 0.005:
        out["satis"] = out["tum_cikis"]
        out["siniflandirma_fallback"] = 1.0
    if out["alis"] < 0.005 and out["tum_giris"] > 0.005:
        out["alis"] = out["tum_giris"]
        out["siniflandirma_fallback"] = 1.0
    return out


def _aylik_trend(
    stok_aylik: list[dict], nakit_aylik: list[dict],
    satis_bazi: str, alis_bazi: str = "fatura",
) -> list[AyTrend]:
    sat_kume = SATIS_EVRAKTIPLERI.get(satis_bazi, SATIS_EVRAKTIPLERI["sevk"])
    alis_kume = _alis_evraktip_kumesi(alis_bazi)
    aylar: dict[str, AyTrend] = defaultdict(lambda: AyTrend(ay=""))
    for r in stok_aylik:
        ay = str(r.get("ay", r.get("AY")) or "")
        if not ay:
            continue
        a = aylar[ay]
        a.ay = ay
        tip = _i(r.get("sth_tip", r.get("STH_TIP")))
        ev = _i(r.get("sth_evraktip", r.get("STH_EVRAKTIP")))
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        if tip == SATIS_TIP and ev in sat_kume:
            a.satis += tutar
        elif tip == ALIS_TIP and ev in alis_kume:
            a.alis += tutar
    for r in nakit_aylik:
        ay = str(r.get("ay", r.get("AY")) or "")
        if not ay:
            continue
        a = aylar[ay]
        a.ay = ay
        a.nakit_giren += _f(r.get("giren", r.get("GIREN")))
        a.nakit_cikan += _f(r.get("cikan", r.get("CIKAN")))
    return [aylar[k] for k in sorted(aylar)]


def _bakiye_bilancodan(b: Bilanco) -> dict[str, float]:
    """Bilanço sekmesiyle birebir aynı nakit/alacak/borç (mizan → build_bilanco yolu)."""
    nak = _nakit_gl_ayir(b)
    alacak = 0.0
    musteri_avans = 0.0
    for s in b.aktif:
        if s.ana[:2] != "12":
            continue
        if s.tutar >= 0:
            alacak += s.tutar
        else:
            musteri_avans += -s.tutar
    borc = sum(s.tutar for s in b.pasif if s.ana[:2] == "32")
    satici_avans = 0.0
    for s in b.pasif:
        if s.ana[:2] != "32":
            continue
        if s.tutar < 0:
            satici_avans += -s.tutar
    return {
        "nakit_mevcut": nak["nakit_mevcut"],
        "nakit_banka": nak["nakit_banka"],
        "nakit_kasa": nak["nakit_kasa"],
        "alacak": alacak,
        "borc": borc,
        "musteri_avans": musteri_avans,
        "satici_avans": satici_avans,
    }


def _nakit_gl_ayir(b: Bilanco) -> dict[str, float]:
    """GL mizandan 100/101 kasa, 102/108 banka ayrımı."""
    banka = kasa = 0.0
    for s in b.aktif:
        if s.ana in ("100", "101"):
            kasa += s.tutar
        elif s.ana in ("102", "108"):
            banka += s.tutar
    return {"nakit_mevcut": banka + kasa, "nakit_banka": banka, "nakit_kasa": kasa}


def _muh_sinifi(muh_kod: str) -> str:
    """cari_muh_kod / ban_muh_kod ön eki → müşteri veya satıcı."""
    ana = str(muh_kod or "").strip().split(".")[0][:3]
    if ana in ("320", "321", "329"):
        return "supplier"
    if ana in ("120", "121"):
        return "customer"
    return ""


def _cari_kovala(
    borc_h: float, alacak_h: float, hareket_tipi: int, baglanti_tipi: int,
    *, muh_kod: str = "",
) -> dict[str, float]:
    """
    Mikro cari listesi mantığı: borç/alacak kolonları ayrı toplanır.
    cari_muh_kod (120/320) kart tipinden önce gelir — hatalı kart tanımlarını düzeltir.
    """
    out = {"alacak": 0.0, "borc": 0.0, "musteri_avans": 0.0, "satici_avans": 0.0}
    if borc_h < 0.005 and alacak_h < 0.005:
        return out
    muh = _muh_sinifi(muh_kod)
    ht, bt = hareket_tipi, baglanti_tipi

    if muh == "supplier":
        if alacak_h > borc_h + 0.005:
            out["borc"] = alacak_h - borc_h
        elif borc_h > alacak_h + 0.005:
            out["borc"] = borc_h - alacak_h
        return out
    if muh == "customer":
        if borc_h > alacak_h + 0.005:
            out["alacak"] = borc_h - alacak_h
        elif alacak_h > borc_h + 0.005:
            out["musteri_avans"] = alacak_h - borc_h
        return out

    if ht == 2:  # sadece alış
        if alacak_h > borc_h + 0.005:
            out["borc"] = alacak_h - borc_h
        elif borc_h > alacak_h + 0.005:
            out["borc"] = borc_h - alacak_h
        return out
    if ht == 1:  # sadece satış
        if borc_h > alacak_h + 0.005:
            out["alacak"] = borc_h - alacak_h
        elif alacak_h > borc_h + 0.005:
            out["musteri_avans"] = alacak_h - borc_h
        return out
    if bt == 1:  # satıcı
        if alacak_h > borc_h + 0.005:
            out["borc"] = alacak_h - borc_h
        elif borc_h > alacak_h + 0.005:
            out["borc"] = borc_h - alacak_h
        return out
    if bt == 0:  # müşteri
        if borc_h > alacak_h + 0.005:
            out["alacak"] = borc_h - alacak_h
        elif alacak_h > borc_h + 0.005:
            out["musteri_avans"] = alacak_h - borc_h
        return out
    if borc_h > alacak_h + 0.005:
        out["alacak"] += borc_h - alacak_h
    elif alacak_h > borc_h + 0.005:
        out["borc"] += alacak_h - borc_h
    return out


def _bakiye_caridan(rows: list[dict], *, banka_kredi_haric: bool = True) -> dict[str, float]:
    """CARI_HESAP_HAREKETLERI satırlarından operasyonel bakiye özeti."""
    out = {
        "nakit_mevcut": 0.0,
        "nakit_banka": 0.0,
        "nakit_kasa": 0.0,
        "alacak": 0.0,
        "borc": 0.0,
        "musteri_avans": 0.0,
        "satici_avans": 0.0,
        "cari_hesap_sayisi": 0,
    }
    for r in rows:
        cins = _i(r.get("cins", r.get("CINS")))
        borc_h = _f(r.get("borc_h", r.get("BORC_H")))
        alacak_h = _f(r.get("alacak_h", r.get("ALACAK_H")))
        if borc_h < 0.005 and alacak_h < 0.005:
            bakiye = _f(r.get("bakiye", r.get("BAKIYE")))
            if abs(bakiye) < 0.005:
                continue
            borc_h = max(bakiye, 0.0)
            alacak_h = max(-bakiye, 0.0)
        if borc_h < 0.005 and alacak_h < 0.005:
            continue
        out["cari_hesap_sayisi"] += 1
        if cins == _BANKA_CINS:
            tip = _i(r.get("ban_hesap_tip", r.get("BAN_HESAP_TIP")))
            if banka_kredi_haric and tip == 1:
                continue
            kod = str(r.get("kod", r.get("KOD")) or "")
            muh = str(r.get("muh_kod", r.get("MUH_KOD")) or "")
            if not muh:
                muh = str(r.get("ban_muh_kod", r.get("BAN_MUH_KOD")) or "")
            if banka_kredi_haric and _muh_sinifi(muh) == "supplier":
                continue
            if banka_kredi_haric and (muh.startswith("300") or kod.upper().startswith("300")):
                continue
            net = borc_h - alacak_h
            out["nakit_banka"] += net
            out["nakit_mevcut"] += net
            continue
        if cins == _KASA_CINS:
            net = borc_h - alacak_h
            out["nakit_kasa"] += net
            out["nakit_mevcut"] += net
            continue
        if cins != _CARI_CINS:
            continue
        k = _cari_kovala(
            borc_h, alacak_h,
            _i(r.get("hareket_tipi", r.get("HAREKET_TIPI"))),
            _i(r.get("baglanti_tipi", r.get("BAGLANTI_TIPI"))),
            muh_kod=str(
                r.get("muh_kod", r.get("MUH_KOD"))
                or r.get("cari_muh_kod", r.get("CARI_MUH_KOD"))
                or r.get("ban_muh_kod", r.get("BAN_MUH_KOD"))
                or ""
            ),
        )
        for key in ("alacak", "borc", "musteri_avans", "satici_avans"):
            out[key] += k[key]
    return out


def _nakit_kaynak_uygula(
    bk: dict[str, float], bilanco: Bilanco | None, nakit_kaynak: str,
) -> tuple[dict[str, float], str]:
    """Nakit bakiyesini ayara göre cari veya GL'den seçer."""
    if bilanco is None:
        return bk, "cari"
    gl_n = _nakit_gl_ayir(bilanco)
    kaynak = nakit_kaynak
    if kaynak == "otomatik":
        cari_n = bk["nakit_mevcut"]
        gl_nakit = gl_n["nakit_mevcut"]
        kaynak = "gl" if cari_n > max(gl_nakit * 2, 1000) and gl_nakit >= 0 else "cari"
    if kaynak == "gl":
        out = dict(bk)
        out["nakit_mevcut"] = gl_n["nakit_mevcut"]
        out["nakit_banka"] = gl_n["nakit_banka"]
        out["nakit_kasa"] = gl_n["nakit_kasa"]
        return out, "cari+gl" if bk["nakit_mevcut"] != gl_n["nakit_mevcut"] else "gl"
    return bk, "cari"


def build_gercek_durum(
    *,
    stok_rows: list[dict] | None = None,
    stok_aylik: list[dict] | None = None,
    nakit_rows: list[dict] | None = None,
    nakit_aylik: list[dict] | None = None,
    bakiye_rows: list[dict] | None = None,
    cari_bakiye_rows: list[dict] | None = None,
    bilanco: Bilanco | None = None,
    gelir_tablosu=None,
    bas: str = "",
    bit: str = "",
    satis_bazi: str = "",
    alis_bazi: str = "",
    ayarlar: GercekDurumAyarlar | None = None,
) -> GercekDurum:
    """Mikro'dan çekilmiş ham satırlardan Gerçek Durum modelini kurar."""
    a = ayarlar or GercekDurumAyarlar.varsayilan()
    if not satis_bazi:
        satis_bazi = a.satis_bazi
    if not alis_bazi:
        alis_bazi = a.alis_bazi
    gd = GercekDurum(bas=bas, bit=bit, satis_bazi=satis_bazi)
    gd.musteri_avans_goster = a.musteri_avans_goster
    gd.ayar_ozet = a.ozet()

    s = _siniflandir_stok(stok_rows or [], satis_bazi, alis_bazi)
    gd.gercek_satis = s["satis"]
    gd.gercek_alis = s["alis"]
    gd.satis_irsaliye = s["satis_irsaliye"]
    gd.satis_fatura = s["satis_fatura"]
    gd.alis_fatura = s["alis_fatura"]
    gd.alis_irsaliye = s["alis_irsaliye"]
    gd.tum_cikis = s["tum_cikis"]
    gd.tum_giris = s["tum_giris"]
    gd.siniflandirilmayan_cikis = s["siniflandirilmayan_cikis"]
    gd.siniflandirilmayan_giris = s["siniflandirilmayan_giris"]
    gd.stok_kirilim_sayisi = len(stok_rows or [])
    gd.stok_hareket_adet = int(s["hareket_adet"])
    gd.siniflandirma_fallback = bool(s.get("siniflandirma_fallback"))

    for r in (nakit_rows or []):
        gd.nakit_giren += _f(r.get("giren", r.get("GIREN")))
        gd.nakit_cikan += _f(r.get("cikan", r.get("CIKAN")))

    if bilanco is not None:
        gl = _bakiye_bilancodan(bilanco)
        gd.gl_nakit_mevcut = gl["nakit_mevcut"]
        gd.gl_alacak = gl["alacak"]
        gd.gl_borc = gl["borc"]

    if cari_bakiye_rows is not None:
        bk = _bakiye_caridan(cari_bakiye_rows, banka_kredi_haric=a.banka_kredi_haric)
        if bilanco is not None and a.alacak_borc_kaynak == "gl":
            gl_bk = _bakiye_bilancodan(bilanco)
            gd.alacak = gl_bk["alacak"]
            gd.borc = gl_bk["borc"]
            gd.musteri_avans = gl_bk["musteri_avans"]
            gd.satici_avans = gl_bk["satici_avans"]
            gd.bakiye_kaynagi = "mizan"
        else:
            gd.alacak = bk["alacak"]
            gd.borc = bk["borc"]
            gd.musteri_avans = bk["musteri_avans"]
            gd.satici_avans = bk["satici_avans"]
            gd.bakiye_kaynagi = "cari"
        gd.cari_hesap_sayisi = bk["cari_hesap_sayisi"]
        nak_bk, nak_etiket = _nakit_kaynak_uygula(bk, bilanco, a.nakit_kaynak)
        gd.nakit_mevcut = nak_bk["nakit_mevcut"]
        gd.nakit_banka = nak_bk["nakit_banka"]
        gd.nakit_kasa = nak_bk["nakit_kasa"]
        if a.alacak_borc_kaynak == "cari" and nak_etiket in ("cari+gl", "gl"):
            gd.bakiye_kaynagi = nak_etiket
        elif gd.bakiye_kaynagi == "cari" and nak_etiket == "gl":
            gd.bakiye_kaynagi = "gl"
    elif bilanco is not None:
        bk = _bakiye_bilancodan(bilanco)
        gd.nakit_mevcut = bk["nakit_mevcut"]
        gd.alacak = bk["alacak"]
        gd.borc = bk["borc"]
        gd.musteri_avans = bk["musteri_avans"]
        gd.satici_avans = bk["satici_avans"]
        gd.bakiye_kaynagi = "mizan"
    else:
        nakit_bakiye = 0.0
        alacak = 0.0
        borc = 0.0
        musteri_avans = 0.0
        satici_avans = 0.0
        for r in (bakiye_rows or []):
            ana = str(r.get("ana", r.get("ANA")) or "").strip()
            bakiye = _f(r.get("bakiye", r.get("BAKIYE")))
            if ana in _NAKIT_ANA:
                nakit_bakiye += bakiye
            elif ana[:2] == "12":
                if bakiye >= 0:
                    alacak += bakiye
                else:
                    musteri_avans += -bakiye
            elif ana[:2] == "32":
                if bakiye <= 0:
                    borc += -bakiye
                else:
                    satici_avans += bakiye
        gd.nakit_mevcut = nakit_bakiye
        gd.alacak = alacak
        gd.borc = borc
        gd.musteri_avans = musteri_avans
        gd.satici_avans = satici_avans
        gd.bakiye_kaynagi = "bakiye_ozet"

    if gelir_tablosu is not None:
        gd.resmi_brut_marj = gelir_tablosu.brut_marj
        gd.resmi_net_marj = gelir_tablosu.net_marj
        gd.resmi_net_kar = gelir_tablosu.net_kar
        gd.resmi_net_satis = gelir_tablosu.net_satislar
        gd.resmi_brut_kar = gelir_tablosu.brut_kar
        gd.resmi_smm = abs(gelir_tablosu.smm)

    gd.trend = _aylik_trend(stok_aylik or [], nakit_aylik or [], satis_bazi, alis_bazi)
    return gd


def gercek_durum_csv(gd: GercekDurum) -> str:
    """Gerçek Durum özetini CSV'ye çevirir (; ayraç, Türkçe ondalık — TR Excel uyumlu)."""
    def s(v: float | None) -> str:
        return "" if v is None else f"{v:.2f}".replace(".", ",")

    out = ["Bölüm;Kalem;Tutar (TL)"]
    out.append(f"DÖNEM;{gd.bas} - {gd.bit} (satış bazı: {gd.satis_bazi});")
    out.append(f"OPERASYONEL;Gerçek Satış;{s(gd.gercek_satis)}")
    out.append(f"OPERASYONEL;Gerçek Alış;{s(gd.gercek_alis)}")
    out.append(f"OPERASYONEL;Gerçek Brüt Kâr;{s(gd.gercek_brut_kar)}")
    out.append(f"OPERASYONEL;Gerçek Brüt Marj;{yuzde(gd.gercek_brut_marj)}")
    out.append(f"NAKİT;Para Giren;{s(gd.nakit_giren)}")
    out.append(f"NAKİT;Para Çıkan;{s(gd.nakit_cikan)}")
    out.append(f"NAKİT;Net Nakit Akışı;{s(gd.nakit_net)}")
    out.append(f"BAKİYE;Nakit Mevcudu (banka+kasa);{s(gd.nakit_mevcut)}")
    if gd.nakit_banka > 0.005 or gd.nakit_kasa > 0.005:
        out.append(f"BAKİYE;  • banka;{s(gd.nakit_banka)}")
        out.append(f"BAKİYE;  • kasa;{s(gd.nakit_kasa)}")
    out.append(f"BAKİYE;Alacaklar (müşteri);{s(gd.alacak)}")
    out.append(f"BAKİYE;Borçlar (satıcı);{s(gd.borc)}")
    out.append(f"BAKİYE;Net İşletme Sermayesi;{s(gd.net_isletme_sermayesi)}")
    if gd.resmi_brut_marj is not None:
        out.append(f"KARŞILAŞTIRMA;Resmi Brüt Marj;{yuzde(gd.resmi_brut_marj)}")
        out.append(f"KARŞILAŞTIRMA;Gerçek Brüt Marj;{yuzde(gd.gercek_brut_marj)}")
        if gd.marj_farki is not None:
            out.append(f"KARŞILAŞTIRMA;Marj Farkı;{yuzde(gd.marj_farki)}")
        if gd.gizlenen_brut is not None:
            out.append(f"KARŞILAŞTIRMA;Gizlenen Brüt (yaklaşık);{s(gd.gizlenen_brut)}")
    return "\r\n".join(out)
