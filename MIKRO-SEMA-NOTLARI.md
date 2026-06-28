# Mikro MSSQL Şema Notları (canlı doğrulanmış)

Bu repoya bağlanan ajanlar için: MikRapor'un Mikro'dan veri çekerken kullandığı **gerçek**
tablo/kolon adları ve tip kodları. `diag_mikro.py` ile **canlı Mikro'da doğrulandı**
(2026-06, firma 26). Tahmin değil, yer gerçeği. SQL'ler `mikro_fetch.py` → `SORGULAR`.

## 🚨 EN KRİTİK TUZAK: geçersiz tablo/kolon = HATA DEĞİL, SESSİZ BOŞ SONUÇ

`SqlVeriOkuV2`, var olmayan bir **tabloya/kolona** atıfta bulunan sorguda çoğu zaman
`IsError` döndürmez — **boş sonuç** döner. Yani "0 satır" gördüğünde iki ihtimal var:
1. Gerçekten o aralıkta veri yok, **VEYA**
2. Sorgudaki tablo/kolon adı yanlış (şema hatası).

**Kural:** Beklenmedik "0 satır"da ÖNCE şemayı `INFORMATION_SCHEMA` ile doğrula:
```sql
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='X';
SELECT TABLE_NAME  FROM INFORMATION_SCHEMA.TABLES  WHERE TABLE_NAME LIKE '%X%';
```
(MikRapor'un ilk entegrasyonu tam bu yüzden 4 kaynakta da "0 satır" verdi: tahmini
`MUHASEBE_HAREKETLERI` tablosu ve `sth_vade_tarihi` kolonu **yoktu**, hata da gelmedi.)

Teşhis aracı: **`diag_mikro.py`** — kaydedilmiş ayarlarla şemayı tarar, gizli değer yazmaz.

## Fatura / irsaliye — `STOK_HAREKETLERI` (sth_*)

Satır bazlı hareket tablosu. `sth_tip` (0=giriş, 1=çıkış) + `sth_evraktip` ile ayrışır.
Son 120 gün dağılımı (firma 26, doğrulanmış):

| sth_tip | sth_evraktip | Anlam | Hacim (örnek) |
|---|---|---|---|
| 1 | 1 | **Satış (çıkış) irsaliyesi** | çok yüksek (~10.6k) |
| 0 | 3 | **Alış faturası** | orta (~1.5k) |
| 1 | 4 | **Satış faturası** | düşük (~90) |
| 0 | 12 | Alış irsaliyesi/depo girişi | ~370 |
| 1 | 16 | Sarf fişi (stok gider pusulası) | ~19 |

> Firma çoğunlukla **irsaliye ile sevk edip toplu faturalıyor** → satış *faturası* satırı az.
> MikRapor aylık P&L/nakit için **faturaları** baz alır (alış=3, satış=4). Eğer ciro çok düşük
> görünürse, satışta irsaliyeyi (evraktip 1) baz almak ayrı bir karar olarak değerlendirilebilir.
> **Gerçek Durum «sevk» modu:** satış = irsaliye+fatura (1+4), alış = **yalnız fatura (3)** —
> alış irsaliyesi (12) aynı malın çift sayımına yol açar; irsaliye satırı yalnız bilgi amaçlı gösterilir.

**Doğrulanmış kolonlar:** `sth_tarih`, `sth_belge_no`, `sth_cari_kodu`, `sth_stok_kod`,
`sth_miktar`, `sth_tutar`, `sth_evrakno_seri`, `sth_evrakno_sira`, `sth_evraktip`, `sth_tip`,
`sth_fis_tarihi`, `sth_belge_tarih`, `sth_teslim_tarihi`, `sth_malkbl_sevk_tarihi`.
**YOK:** `sth_vade_tarihi` (vade bu tabloda yok — fatura vadesi gerekiyorsa cari hareketten/başka).

## Banka — `CARI_HESAP_HAREKETLERI` (cha_*) ⨝ `BANKALAR` (ban_*)

Mikro'da **bankalar da "cari" gibi** tutulur. Bir hareketin **banka tarafı** satırı
`cha_kod = BANKALAR.ban_kod` olandır → `INNER JOIN BANKALAR ON ban_kod = cha_kod` çift
sayımı önler (yalnız banka tarafı). Kaynak: `ss/lib/banka-bildirim.ts` (canlı, çalışıyor).

**Gerçek Durum bakiyeleri** (nakit/alacak/borç) artık buradan okunur — GL mizanı değil.
Mikro cari modülündeki bakiyelerle aynı kaynak: `fetch_cari_bakiye()` → `cha_cari_cins`
0=Carimiz, 2=Bankamız, 4=Kasamız. Bakiye = Σ(borç hareket − alacak hareket) × kur.

- `cha_tip = 0` → **bankaya giriş** (borç, "para geldi")
- `cha_tip = 1` → **bankadan çıkış** (alacak, "para gitti")
- `cha_meblag` → tutar (hesap dövizinde); TL için `cha_meblag * ISNULL(cha_d_kur, 1)`
- `cha_tarihi` → işlem tarihi · `cha_create_date` → kaydın DB'ye girildiği an (polling imleci)
- `cha_aciklama`, `cha_evrakno_seri`, `cha_evrakno_sira`, `cha_belge_no`, `cha_Guid`, `cha_iptal`
- **Karşı taraf (cari):** aynı `cha_evrakno_seri`+`cha_evrakno_sira`'ya sahip, banka **olmayan**
  diğer satır (`NOT EXISTS BANKALAR`); onun `cha_kod`'u = karşı cari kodu. Bu sayede MikRapor'un
  `karsi_hesap_prefix` (120/320/102) ve `ic_transfer` (102↔102) mantığı çalışır.
- `BANKALAR.ban_ismi` → banka adı.
- `cha_iptal = 0` filtresi şart (iptal edilenleri dışla).

## Muavin / GL (operasyonel gider 7xx) — `MUHASEBE_FISLERI` (fis_*)

**Asıl GL/muavin satır tablosu `MUHASEBE_FISLERI`'dir** (her satır = bir hesaba borç/alacak
kaydı). Tahmini `MUHASEBE_HAREKETLERI` tablosu **bu Mikro'da YOK**. Canlı doğrulanmış kolonlar:

- `fis_tarih` → kayıt tarihi
- `fis_hesap_kod` → muhasebe hesap kodu (ör. `770.01`, `102.001`, `320.01.0018`)
- 🚨 **`fis_meblag0` = İŞARETLİ TL TUTAR** (POZİTİF = borç/debit, NEGATİF = alacak/credit).
  **Borç/alacak AYRI KOLON DEĞİLDİR — yön işaretten gelir.** Diğer meblag kolonları AYNI tutarın
  başka para birimleridir: **`fis_meblag1` = USD karşılığı** (asla alacak değil!), `fis_meblag2` =
  orijinal belge dövizi (TL ise meblag0'a eşit), `fis_meblag3` = EUR, `fis_meblag4..6` = alt/raporlama.
  - **Bakiye (TL):** `bakiye = SUM(fis_meblag0)`. Borç = pozitif kısım, Alacak = |negatif kısım|:
    `borc = SUM(CASE WHEN fis_meblag0>0 THEN fis_meblag0 ELSE 0 END)`,
    `alacak = SUM(CASE WHEN fis_meblag0<0 THEN -fis_meblag0 ELSE 0 END)`.
  - **TUZAK:** `meblag0 - meblag1` yapma! TL'den USD'yi çıkarmış olursun; mizan ~%5 tutmaz
    (gerçek vaka: Σmeblag0≈0 (dengeli) iken Σmeblag1=+1,93M → sahte 1,96M fark). `bilanco_cli.py`
    bunu canlı tespit etti.
  - **Denge testi:** `Σ(fis_meblag0)` tüm hesaplarda ≈ 0 olmalı (çift kayıt). Canlı bir kurulumda
    gün ortası anlık görüntüde ~%0,08 kalan (dönem-içi maliyet kapanışından) ihmal edilebilir çıktı.
- `fis_aciklama1` → açıklama · `fis_sira_no` → fiş sıra no · `fis_yevmiye_no` → yevmiye no · `fis_tur` → fiş tipi (0=normal)
- `fis_iptal = 0` filtresi şart.

> **NOT:** `mikro_fetch.py`'deki eski muavin sorgusu (`fis_meblag0 AS borc, fis_meblag1 AS alacak`)
> bu yüzden HATALIDIR (alacak yerine USD okur). Raporlama bilanço'ya pivot edildiği için o eski yol
> emekliye ayrılıyor; canlı/doğru yol `bilanco_cli.py`'deki CASE'li mizan sorgusudur.
- Hesap **adı** bu tabloda yok (gerekiyorsa `MUHASEBE_HESAP_*` plan tablosundan JOIN — MikRapor
  için gerekmiyor; analizör hesap koduna göre gruplar).

> **DİKKAT — `MUHASEBE_FIS_DETAYLARI` muavin DEĞİLDİR.** O tablo (mfd_*) Ba/Bs belge detayıdır
> (cari unvan/vergi no, `mfd_carikodu`, `mfd_caritutar`, `mfd_digerevrakadi`); borç/alacak per-hesap
> içermez. Muavin için **`MUHASEBE_FISLERI`** kullanın.

MikRapor muavin'i 7xx (730/740/750/760/770) gider hesaplarını toplar; ham olarak ayın tüm GL
satırları çekilir (Excel muavin dökümüyle aynı), filtrelemeyi analizör yapar.

## Genel kurallar (ss/lib/mikro-api.ts ile aynı)

- Auth: günlük `MD5(YYYY-MM-DD [+ ' ' + SIFRE_GUN])`, UTC tarih.
- `SqlVeriOkuV2` yanıtı: satırlar `SQLResult1 / SQLResult / Data / Rows` altında.
- Türkçe arama: `COLLATE Turkish_CI_AI`.
- Sorgularda `WITH (NOLOCK)` (canlı DB'yi kilitlememek için ss böyle yapıyor).
- Tarih aralığı: ay sonu için `< ay_başı+1` kullan (datetime'da `<= '...-30'` gün-içi saatleri kaçırabilir).
- Mikro alan adlarını **aynen koru** (`sth_*`, `cha_*`, `ban_*`); mapping katmanında yeniden adlandırma yok.
