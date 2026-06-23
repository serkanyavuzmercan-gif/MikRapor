# MikRapor

PyQt6 tabanlı finansal analiz ve nakit akışı uygulaması. Muavin defteri, alış/satış faturaları, banka hareketleri ve manuel maaş girişlerini seçilen analiz ayına göre birleştirir.

## Özellikler

- Aylık kâr/zarar (P&L) ve nakit akışı özeti
- CFO erken uyarı göstergeleri (runway, nakit dönüşüm, veri eşleşme)
- 120/320 yaşlandırma ve tahsilat/ödeme planı mutabakatı
- Kural tabanlı yönetim tavsiyeleri
- PDF, Excel, Word ve metin rapor dışa aktarımı

## Geliştirme

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

## Veri kaynakları

İki yol vardır; ikisi de aynı analiz motorunu besler:

**A) Mikro API'den çekme (önerilen).** "Veri Yükleme" sekmesindeki **Mikro Ayarları**'na kendi
Mikro sunucu bilgilerinizi girin, ardından **Mikro'dan Çek (seçili ay)** ile muavin, alış/satış
faturaları ve banka hareketleri doğrudan çekilir. Detay: `MIKRO-API-ENTEGRASYONU.md`.

**B) Elle dosya yükleme (klasik).**
1. Aylık muavin defteri (Mikro Excel/CSV)
2. Alış ve satış faturaları
3. Banka hareketleri

Her iki yolda da:
4. Manuel resmi/harici maaş girişi
5. (İsteğe bağlı) 120 tahsilat ve 320 ödeme planı (şimdilik yalnızca elle yükleme)

Örnek dosyalar: `samples/`
