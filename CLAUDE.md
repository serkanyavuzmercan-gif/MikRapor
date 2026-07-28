# MikRapor — değişmez kurallar

Bu dosya, üzerinde tartışılmış ve karara bağlanmış kuralları tutar. Bir değişiklik
bunlardan biriyle çakışıyorsa değişiklik yanlıştır, kural değil.

---

## 1. TARİH ARALIĞI KUTSAL

**Kullanıcının seçtiği tarih aralığı her şeyi belirler. Aralığın bir gün öncesi ya da
bir gün sonrası rapora giremez.**

- Aralık dışından **tek gün bile** veri okunmaz, hesaplanmaz, ekrana yazılmaz.
- Bir değeri hesaplamak aralık dışı veri gerektiriyorsa **o değer `—` gösterilir.**
  Aralık dışına çıkarak "daha doğru" bir rakam üretmek yasaktır.
- Bu kural **bütün sekmeler** için geçerlidir; istisnası yoktur.

### Neden bu kadar katı

Program birkaç yerde "daha iyisini bilerek" aralığı genişletiyordu ve her seferinde
gerekçesi kendi içinde tutarlıydı:

| Yer | Ne yapıyordu | Neden yanlıştı |
|---|---|---|
| Yıllar arası mukayese | Her yılı 1 Ocak'tan okuyordu | 28.07.2025 seçilmişken tabloya 01.01.2025 verisi giriyordu |
| Trend grafiği | Kısa dönemde grafiği 12 aya genişletiyordu | Kullanıcının seçmediği aylar ekrandaydı |
| Tahmin öğrenme penceresi | `bit`ten 12 ay geriye uzuyordu | Aynı |
| Nakit Akış runway | Bitişten 90 gün geriye, `bas`tan bağımsız | Aynı |
| Yapay Zekâ ham verisi | Odak yılın 1 Ocak'ından okuyordu | Modele seçilmemiş günlerin verisi gidiyordu |

Kullanıcının kararı: *"BANA SEÇTİĞİM TARİH ARALIĞI DIŞINDA DATA GETİRME. TARİH ARALIĞI
SEÇİM KUTSAL HER ŞEYİ O BELİRLİYOR."*

Pencere kısalıyorsa kısalsın. Dar dönemin dalgalı çıkması kullanıcının bilerek aldığı
sonuçtur; onun adına karar vermiyoruz.

### Uygulamada

- Yıllar arası mukayesede her sütun, o yılın **seçili aralıkla kesişimidir**
  (`yillari_cek(cfg, bas, bit)`). Sütun başlığı gerçek pencereyi yazar:
  `2025 (28.07–31.12)`.
- Referans pencereler `max(bas, geri)` ile kırpılır — asla `min`.
- Akış sorguları `donem_satirlari` / `donem_toplami` ile aralık içinde bölünür.
- Bakiye/fotoğraf sorguları aralığın **bitiş** tarihinde okunur.

İhlali engelleyen testler: `test_mukayese_fetch.TestSecilenAralikKutsal`,
`TestYardimciPencereKirpma`.

---

## 2. Güvenilmez veri gösterilmez

Rakam şüpheliyse `—` yazılır ve **sebebi rakamın yanında** söylenir. Boş hücreyi
açıklamasız bırakmak da, şişik rakamı sessizce basmak da kabul edilmez.

Örnek: satışların maliyeti (62) muhasebeye işlenmemişse eksik `621/153` fişinin iki
ayağı vardır — kâr **ve** stok aynı tutarda şişer. O yılın kâr kalemleri, stoğu,
özkaynağı, aktif toplamı ve bunlardan türeyen oranları boş bırakılır. Asit-Test
etkilenmez: `(dönen − stok)` şişkinliği zaten götürür.

## 3. Hesaplayabiliyorsak gizlemeyiz

Gizlemek çare değil. Bir rakam canlı veriden hesaplanabiliyorsa hesaplanır. Ama
hesaplanamıyorsa **tahmin edilmez** — ölçülmüş tek yönlü sınır varsa o yazılır
("en az X"), yoksa `—` kalır.

## 4. LESS IS MORE

Kısa ve öz. Etiket, uyarı ve not şişkinliği yok. Tablo altına altı paragraf uyarı
yazmak, hiç yazmamaktan kötüdür — kimse okumaz ve içlerinden biri eskiyip yanlış olur.
(Canlıda "Tutarlar TL'dir" notu, TL bölümü tablodan kaldırıldıktan sonra orada kalıp
dolar rakamlarını TL sandırıyordu.)

## 5. Aynı rapor, tek isim

Sekme adı = PDF başlığı = sayfa başlığı. Sekmeler arasında veri tekrarı yok.
Her tabloda satır vurgusu (row hover) standarttır, ayrıca istenmesi gerekmez.

## 6. Veri dışarı çıkmaz

MikRapor'un dışarıya veri gönderdiği **tek** yer Yapay Zekâ Yorumu sekmesidir; API
anahtarı **ve** açık onay kutusu birlikte olmadan hiçbir ağ çağrısı yapılmaz.

---

## Teknik notlar

- **Veritabanını firma kodu seçer**, `CalismaYili` değil. Bir firma DB'si birden çok
  yıl tutabilir (canlıda 20 → 2020-2025, 26 → 2026+). Yıl → firma eşlemesi
  `infra/veritabani.py` kataloğundan gelir; sekmeler `yil_client(cfg, yil)` kullanır,
  `MikroClient(cfg)` kurmaz.
- **Kapanış/açılış fişleri**: 31 Aralık kapanış fişi bütün bakiyeleri sıfırlar,
  1 Ocak açılış fişi geri yükler. Mizan sorgusu ikisini de eler.
- **Sargability**: `LEFT(LTRIM(kol),3) = 'x'` ve `LEFT(kol,6)` üzerinden join indeks
  kullandırmaz → tam tarama → zaman aşımı. Önce küçük tablodan kodu çöz, sonra
  `kol LIKE 'kod%'`.
- **Qt tuzağı**: bir widget'a QSS verilince Qt tüm çizimi stil sayfasına devreder;
  `setForeground()` ve `Fixed` sütun genişliği ezilir. `setStretchLastSection(False)`
  elle verilmeli.
- **Qt ölümcül tuzağı**: çalışan bir `QThread` üzerinde `deleteLater()` çağırmak
  süreci çökertir. Silme işini `finished` sinyaline bırak.
- Şifre `MD5("YYYY-AA-GG <şifre>")` — **yerel** tarihle (Türkiye UTC+3).

## Komutlar

```
python3 -m unittest discover -s . -p "test_*.py" -q     # test (pytest YOK)
ruff check . --fix                                      # lint
```

Teşhis araçları: `stok_diag_cli.py` (`--kolonlar`, `--maliyet`, `--fatura`),
`bilanco_cli.py --teshis`, `cari_diag_cli.py`.

## Dal ve deploy

Geliştirme `claude/microproject-code-review-b4g4jy` dalında. Kullanıcı **"deploy"**
dediğinde: push → PR (base `master`) → merge. Başka dala push yok.
