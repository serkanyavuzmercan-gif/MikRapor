# MikRapor tanıtım sayfası

Statik tek sayfa; derleme adımı yok. Vercel projesi: **mikrapor**
(takım `hidrotekniks-projects`), alan adı **mikrapor.hidroteknik.com.tr**.

## Dosyalar

| dosya | ne işe yarar |
|---|---|
| `index.html` | sayfanın tamamı; SEO etiketleri ve schema.org JSON-LD içinde |
| `gizlilik-politikasi.html` | gizlilik politikası — Microsoft Store başvurusu bu ADRESİ ister |
| `styles.css` | uygulamayla aynı teal/navy paleti; harici font/script yok |
| `robots.txt`, `sitemap.xml` | arama motoru |
| `og-mikrapor.png` | paylaşım önizlemesi (1200×630) |
| `logo.png` | favicon + başlık logosu |
| `ekran-*.png` | uygulama ekran görüntüleri — rakamlar KURGU demo verisidir |

Ekran görüntüleri `assets/` içindeki uygulamadan offscreen üretildi; gerçek firma
verisi kullanılmaz, firma adı «ÖRNEK SANAYİ VE TİCARET A.Ş.» olarak verilir.

## Yayına alma

Vercel projesi GitHub deposuna bağlanırsa `web/` kök dizin seçilerek her push
otomatik yayına çıkar. Bağlanana kadar dosyalar elle yükleniyor.

## Bekçi

`test_web.py`, sayfadaki sekme adlarını ve ücretsiz/premium bölünmesini
`domain/lisans.py` ile kıyaslar. Sayfa aylarca «Trend & oranlar» diye var olmayan
bir rapordan bahsetti; ürünün sattığı şeyle satış sayfası ayrışınca müşteri o raporu
arayıp bulamıyor. Sürüm numarası da `infra/surum.py`den doğrulanır.
