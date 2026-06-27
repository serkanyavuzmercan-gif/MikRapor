# MikRapor

Mikro ERP'den **anında finansal tablolar** üreten masaüstü uygulaması (PyQt6). Genel muhasebe verinizden, seçtiğiniz tarih/dönem için **bilanço** ve **gelir tablosunu** saniyeler içinde hazırlar; kurumsal **PDF** ve **CSV** olarak dışa aktarır.

Her kullanıcı uygulamayı **kendi ağında** çalıştırır ve **kendi Mikro sunucusuna** bağlanır. Bağlantı bilgileri yalnızca o bilgisayarda saklanır, dışarı gönderilmez.

## Sekmeler

- **Anında Bilanço** — tarih itibarıyla mizandan Tek Düzen Hesap Planı bilançosu (AKTİF / PASİF, bölüm alt toplamları, denge kontrolü, dönem net kâr/zarar). Mikro'nun kendi mizanına kuruşu kuruşuna doğrulanmıştır.
- **Gelir Tablosu** — başlangıç–bitiş dönemi için kâr/zarar şelalesi (Net Satış → Satışların Maliyeti → Brüt Kâr → Faaliyet/Diğer/Finansman → Dönem Net Kârı), brüt/faaliyet/net marj göstergeleriyle. Dönem net kârı bilançoyla birebir tutar (yerleşik mutabakat).
- **Trend ve Oranlar** — *(yakında)* çok dönem karşılaştırma + finansal oranlar.

## Özellikler

- Yerel Qt tabloları: satır üstüne gelince vurgu, zebra desen, ortalanmış kurumsal düzen
- **PDF** (kurumsal letterhead + alt toplamlar) ve **CSV** (Türkçe Excel uyumlu) dışa aktarım
- Firma ünvanı Mikro'dan otomatik (elle giriş de mümkün)
- Açık tema, tek-örnek pencere, tarih/dönem seçici

## Kurulum (geliştirme)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_dev.ps1
```

## Windows exe derleme

```powershell
.\build_exe.ps1
```
Çıktı: `dist\MikRapor.exe`

## Mikro bağlantısı

İlk açılışta üstteki **«Mikro Ayarları»**'ndan kendi Mikro sunucu bilgilerinizi girin (API adresi, anahtar, firma kodu, çalışma yılı, kullanıcı, şifre tuzu). **Bağlantıyı Test Et** → **Kaydet**. Bilgiler `%APPDATA%\MikRapor\config.json` içinde, yalnızca sizin bilgisayarınızda tutulur.

## Veri kaynağı hakkında

Tablolar Mikro'nun **genel (resmî) muhasebesinden** (`MUHASEBE_FISLERI`, TDHP hesapları) üretilir — mali müşavirin tuttuğu defter. Bu nedenle:

- **Kapatılmış dönemler** (önceki ay/yıl) tam olup resmî mali tablolarla uyumludur.
- **İçinde bulunulan açık dönem** mali müşavirin işlediği kadar günceldir; maliyet kapanışı yapılmadan satışların maliyeti (62) boş kalabilir — uygulama bu durumda kârın şişik görünebileceğini **uyarır**.
