# Mikro API Entegrasyonu

Bu belge, MikRapor'un elle Excel/CSV yükleme yanına eklenen **doğrudan Mikro REST API'den
veri çekme** yolunu açıklar.

## Neden masaüstü + API (web SaaS değil)

MikRapor'u "tüm Mikro kullanıcılarına aç + link'le paylaş" hedefinin en pratik yolu, masaüstü
uygulamayı **her kullanıcının kendi ağında** çalıştırmaktır:

- EXE, firmanın kendi yerel ağında çalışır → Mikro sunucusuna **doğrudan** ulaşır. Mikro'lar
  genelde firewall arkasında / on-prem olduğundan, bulut bir web app'in dışarıdan erişmesi
  ciddi güvenlik ve çok-kiracılık sorunu doğururdu. Masaüstü bunu doğal çözer.
- Bağlantı bilgileri **kullanıcının makinesinde** kalır (`config.json`); kimsenin Mikro şifresi
  veya mali verisi merkezi bir sunucuda toplanmaz → sıfır veri sorumluluğu.

İleride çıktının (raporun) salt-okunur bir web linki olarak paylaşılması ayrı/ince bir parça
olarak eklenebilir; bu, kimsenin Mikro'sunu dışarı açmadan "paylaşılabilirlik" sağlar.

## Mimari — analiz motoru hiç değişmedi

```
Mikro REST API ──► mikro_api.py ──► mikro_fetch.py ──► (DataFrame'ler) ──► analyzer.py ► rapor
                    (istemci)        (kontrat adaptörü)   STANDARD_*_COLUMNS   (DEĞİŞMEDİ)
```

- **`config.py`** — Mikro bağlantı ayarları. `%APPDATA%/MikRapor/config.json` (Windows) veya
  `~/.config/MikRapor/config.json`. Dosya yoksa `MIKRO_*` ortam değişkenlerine düşer (ss ile
  aynı isimler).
- **`mikro_api.py`** — `ss/lib/mikro-api.ts` auth desenini birebir taşıyan istemci: günlük
  rotasyonlu `MD5(YYYY-MM-DD[ +SIFRE_GUN])`, `POST {baseUrl}/{endpoint}`, `result[0].Data`
  zarfı, `SqlVeriOkuV2` ham SQL, retry, kapalı TLS doğrulaması. Stdlib `urllib` (yeni bağımlılık
  yok). `transport` enjekte edilebilir → network'süz test edilebilir.
- **`mikro_fetch.py`** — **kontrat adaptörü**. Mikro satırlarını mevcut parser'ların ürettiği
  DataFrame şekline (`STANDARD_MUAVIN/FATURA/BANK_COLUMNS`) **birebir** çevirir. İki katman:
  saf eşleme (`rows_to_*_df`, test edilir) ve SQL (`SORGULAR`, canlı doğrulanır).
- **`mikro_settings_dialog.py`** — Ayarlar ekranı + "Bağlantıyı Test Et".
- **`main.py`** — "Veri Yükleme" sekmesinde "Mikro Bağlantısı (API)" bölümü.

## ⚠️ İlk canlı bağlantıda DOĞRULANACAK: SQL sorguları

Buradan (canlı Mikro olmadan) doğrulanamayan **tek** şey, `mikro_fetch.py` içindeki `SORGULAR`
sözlüğündeki SQL'lerin Mikro şemasıyla uyumudur. Tablo/kolon adları Mikro sürümüne göre
değişebilir. İlk gerçek Mikro bağlantısında:

1. **Mikro Ayarları**'nı doldurup **Bağlantıyı Test Et** ile auth+ağı doğrula (`SELECT 1`).
2. Her kaynağı tek tek dene; gelen kolon adları beklenenden farklıysa **sadece `SORGULAR`**
   sözlüğünü düzelt (eşleme katmanı `get_row_value` ile büyük/küçük harfe ve farklı yazımlara
   toleranslıdır, çoğu fark kendiliğinden çözülür).

En emin sorgu fatura'dır (ss'de doğrulanmış `STOK_HAREKETLERI sth_*` üstüne kurulu). Muavin ve
banka GL sorguları (`MUHASEBE_HAREKETLERI`) en çok teyit isteyenlerdir — özellikle `sth_evraktip`
fatura filtresi ve `mha_RB` borç/alacak yönü.

## Şu an kapsam (v1)

- ✅ Muavin, alış faturaları, satış faturaları, banka — tek tıkla seçili ay için çekilir.
- ⏳ 120/320 planları — şimdilik elle yükleme (cari yaşlandırma SQL'i ayrı bir iş).
- ⏳ Çekme şu an UI thread'inde senkron çalışır (bekleme imleci ile). Ağır aylarda donmaması
  için ileride QThread'e taşınabilir.

## Testler

`test_mikro.py` (PyQt6 gerektirmez): parola hash, config kaydet/oku, SQL yanıt ayrıştırma,
istemci (sahte transport ile), ve **adaptörün analizörü uçtan uca beslediği** smoke testi.

```bash
python -m unittest test_operational test_mikro
```
