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
| `tanitim-genel.jpg`, `ekran-*.jpg` | ürün görselleri — rakamlar KURGU demo verisidir |

Görsellerde gerçek firma verisi kullanılmaz. Ham dosyalar 1,8 MB civarındaydı;
sayfaya konmadan 1400px genişliğe indirilip JPEG'e çevrilir (~150 KB). `test_web`
bunu 400 KB üst sınırıyla sınar — büyük dosya sessizce sayfaya giremesin.

## Yayına alma

Vercel projesi GitHub deposuna bağlanırsa `web/` kök dizin seçilerek her push
otomatik yayına çıkar. Bağlanana kadar dosyalar elle yükleniyor.

## Bekçi

`test_web.py`, sayfadaki sekme adlarını ve ücretsiz/premium bölünmesini
`domain/lisans.py` ile kıyaslar. Sayfa aylarca «Trend & oranlar» diye var olmayan
bir rapordan bahsetti; ürünün sattığı şeyle satış sayfası ayrışınca müşteri o raporu
arayıp bulamıyor. Sürüm numarası da `infra/surum.py`den doğrulanır.
