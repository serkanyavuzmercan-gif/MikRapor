# Microsoft Store — Mağaza listesi metinleri (tr-TR)

Partner Center → **Store listings → Turkish (Türkiye)** sayfasındaki alanların birebir
karşılığı. Her blok olduğu gibi kopyalanıp yapıştırılmak içindir.

Metinler koddan türetildi, uydurulmadı: sekme adları `domain/lisans.py`, ücretsiz/premium
bölünmesi aynı dosya, sekme açıklamaları `ui/tabs/*.ACIKLAMA`, künye `infra/surum.py`,
gizlilik `PRIVACY.md`. Bir sekme adı değişirse **burası da değişir** (kural 5: aynı rapor,
tek isim).

---

## Product name

Rezerve edilmiş ad `Mikrapor`, uygulamanın kendi adı ise `MikRapor` (büyük R).

**Bırakın `Mikrapor` seçili kalsın.** «Reserve more names» ile `MikRapor` rezerve etmeyi
deneyebilirsiniz; Partner Center büyük/küçük harf farkını aynı ad sayıp reddedebilir.
Reddederse mesele kozmetiktir, listede `Mikrapor` yazar, kurulan uygulamanın adı yine
`MikRapor` olur (`AppxManifest.xml: Properties/DisplayName`).

**Paket kimliğine dokunmayın.** `Identity/Name = Hidroteknik.Mikrapor` ve
`Publisher = CN=119D3611-…` Partner Center'dan gelir; tek karakterlik fark yüklemeyi
reddettirir. Listeye yeni ad eklemek kimliği değiştirmez, birincil adı değiştirmek
değiştirir — birincil adı değiştirmeyin.

---

## ⚠ ÖNCE ŞUNU KARARA BAĞLA: premium bölünmesi değişiyor

Aşağıdaki açıklamada «ÜCRETSİZ NE VAR, EKLENTİ NE AÇIYOR» paragrafı **bugünkü**
bölünmeyi anlatıyor (beş sekme premium). Paralel bir çalışmada bölünme **yalnız Yapay
Zekâ Yorumu + PDF/CSV çıktısı** premium olacak şekilde değişiyor.

**Mağaza metni uygulamanın davranışını yanlış anlatamaz** — hem sertifikasyonda
gerekçe olur hem de ödeyen müşteri beklediğini bulamaz. Hangisi yayına girecekse o
paragraf kullanılır:

**A) Bugünkü bölünme** (açıklamanın içindeki hâli — beş sekme premium)

**B) Yeni bölünme** — değişiklik indiğinde o paragrafın yerine bunu koy:

```
ÜCRETSİZ NE VAR, EKLENTİ NE AÇIYOR

Uygulama ücretsiz kurulur ve sekiz raporun tamamı ücretsiz açılır: Alacak & Borç, Nakit Akış, Nakit & Kârlılık, Mukayese & Oranlar, Tahmin & Projeksiyon, Reel Değer, Bilanço ve Gelir Tablosu. Süre sınırı yoktur, rapor sayısı sınırı yoktur, veri kısıtlanmaz.

Tek seferlik eklenti iki şeyi açar: Yapay Zekâ Yorumu sekmesi ve raporların kurumsal PDF / Excel uyumlu CSV olarak dışa aktarımı. Abonelik değildir.
```

Bu değişirse **Product features listesindeki** «Her rapor kurumsal PDF ve Excel uyumlu
CSV olarak dışa aktarılır» maddesi de şöyle olmalı: *«Kurumsal PDF ve Excel uyumlu CSV
dışa aktarım (eklenti ile)»* — yoksa ücretsiz sanılır.

---

## Description *(zorunlu · en fazla 10.000 karakter)*

```
Mikro ERP verinizi mali müşavir raporu beklemeden okunur hâle getirir. Tarih aralığını seçersiniz, rapor saniyeler içinde ekranda olur. Bilanço, gelir tablosu, nakit akışı, alacak yaşlandırması, kârlılık ve yıllar arası mukayese — hepsi doğrudan kendi sunucunuzdaki veriden hesaplanır.

Ay sonunu beklemek yerine bugünün rakamına bakarsınız: kimden ne zaman para girecek, bu ay kaç TL nakit çıktı, hangi müşteri ne kadar geciktiriyor, kâr gerçekten kâr mı.

NASIL ÇALIŞIR

1. Mikro bağlantı bilgilerinizi girersiniz (API adresi, firma kodu, kullanıcı). Bilgiler yalnız o bilgisayarda, şifreli saklanır.
2. Tarih aralığını seçersiniz — bu ay, çeyrek, yıl ya da serbest aralık. Yılları ayrı veritabanlarında tutuyorsanız program hangi yılın nerede olduğunu kendi bulur.
3. Raporu getirirsiniz. Beğendiğinizi kurumsal PDF ya da Excel uyumlu CSV olarak dışarı alırsınız.

RAPORLAR

• Alacak & Borç — Açık alacak ve borçların vadeye göre yaşlandırması, dönem tahsilat/ödeme performansı (DSO/DPO) ve ileriye dönük net vade takvimi: ne girecek, ne çıkacak. En çok alacaklı ve borçlu cariler.

• Nakit Akış — Banka ve kasadan fiilen geçen para, karşı tarafına göre kategorize: müşteri tahsilatı, satıcı ödemesi, kredi kullanım/ödemesi, vergi, SGK, personel, genel giderler. Açılış → girişler − çıkışlar → kapanış. Bir kategoriye tıklayınca arkasındaki fişler tarih, yevmiye no ve tutarıyla açılır. KDV'nin kaç gün kendi kesenizden finanse edildiğini ayrıca gösterir.

• Bilanço — Seçtiğiniz tarih itibarıyla Tek Düzen Hesap Planı bilançosu: AKTİF/PASİF, bölüm alt toplamları, denge kontrolü ve dönem net kâr/zararı.

• Gelir Tablosu — Net satıştan dönem net kârına kâr/zarar şelalesi (satışların maliyeti, faaliyet, diğer, finansman) ve brüt/faaliyet/net marj. Dönem kârı bilançoyla birebir tutar.

• Nakit & Kârlılık — Faturalar muhasebeleştirilmeyi beklemeden, deponuzdan geçen mal ve bankadan geçen para üzerinden fiili brüt marj, nakit akışı ve işletme sermayesi; resmî gelir tablosuyla mutabakatı.

• Mukayese & Oranlar — Aylık satış, alış, brüt kâr ve nakit trendi; cari oran, asit-test ve borç/özkaynak yan yana. İsterseniz geçmiş yılların aynı dönemiyle mukayese.

• Tahmin & Projeksiyon — Geçmişten otomatik doldurulan ama elinizle değiştirebileceğiniz varsayımlarla (aylık ciro, büyüme, brüt marj, sabit gider) 36 aya kadar ciro, kâr ve kümülatif nakit projeksiyonu. Nakit eksiye düşüyorsa hangi ay düşeceğini söyler.

• Reel Değer — Vadeli satmak size neye mal oluyor, vadeli almak ne kazandırıyor? Açık alacak ve borçları vade yapısına göre bugünkü değerine çevirir. Muhasebe tutarlarını değiştirmez.

• Yapay Zekâ Yorumu — Dönemin raporlarından sade Türkçe bir yönetim yorumu: özet, iyi gidenler, riskler, bu ay yapılacaklar. Kendi API anahtarınızla çalışır (Anthropic, OpenAI, Google Gemini, DeepSeek, xAI ya da OpenAI uyumlu özel bir adres). Model seçmeniz gerekmez.

RAKAMIN ARKASI GÖRÜNÜR

Şüpheli rakam gösterilmez. Bir değer güvenilir biçimde hesaplanamıyorsa boş bırakılır ve sebebi rakamın yanında yazar — «hesaplanamadı» demek, yanlış rakam basmaktan iyidir. Aykırı kayıtlar (yanlış girilmiş tutarlar) rapor toplamlarından çıkarılır ve kaçının çıkarıldığı ekranda yazar. Ayrıca Veri Sağlığı penceresi Mikro kayıtlarınızdaki bozuk kayıtları hangi evrak, hangi tarih olduğuyla listeler.

VERİNİZ BİLGİSAYARINIZDAN ÇIKMAZ

MikRapor kapalı devre çalışır. Bağlantı doğrudan sizin Mikro sunucunuzladır; arada bize ait bir sunucu yoktur. Hesap açmanız istenmez, telemetri, analitik ve reklam yoktur. Mikro veritabanınıza yalnızca okuma için bağlanılır: hiçbir kayıt yazılmaz, değiştirilmez, silinmez.

Tek istisna «Yapay Zekâ Yorumu» sekmesidir. Orada da veri, ancak kendi API anahtarınızı girip paylaşım onayını işaretlediğinizde dışarı çıkar; ne gönderildiği ekranda yazar. Onayı kaldırdığınızda o yol tamamen kapanır.

ÜCRETSİZ NE VAR, EKLENTİ NE AÇIYOR

Uygulama ücretsiz kurulur. Alacak & Borç, Nakit Akış, Bilanço ve Gelir Tablosu sekmeleri ücretsizdir; süre sınırı ve rapor sayısı sınırı yoktur.

Nakit & Kârlılık, Mukayese & Oranlar, Tahmin & Projeksiyon, Reel Değer ve Yapay Zekâ Yorumu sekmeleri tek seferlik bir eklentiyle açılır — abonelik değildir. Kilitli sekmeler girilebilir ve ne yaptıklarını anlatır; bulanıklaştırılmış ya da uydurma rakam gösterilmez.

GEREKSİNİMLER

• Windows 10 sürüm 1809 (64-bit) veya üzeri.
• Çalışan bir Mikro ERP kurulumu ve ağınızdan erişilebilen Mikro REST API servisi. Uygulama Mikro'yu içermez; mevcut kurulumunuza bağlanır.
• Mikro kullanıcı bilgileriniz ve firma kodunuz.
• Yapay Zekâ Yorumu için kendi yapay zekâ sağlayıcı API anahtarınız (isteğe bağlı).

Arayüz ve raporların tamamı Türkçedir; hesap planı TDHP'dir.

Soru ve hata bildirimi: mikrapor@hidroteknik.com.tr

MikRapor bağımsız bir üründür; Mikro Yazılım ile ticari bir bağlantısı ya da onun onayı yoktur. «Mikro» adı yalnızca uyumluluğu belirtmek için kullanılmıştır.
```

---

## What's new in this version *(en fazla 1.500 karakter)*

**İlk gönderimde BOŞ BIRAKIN.** Formun kendi notu bunu söylüyor: «Leave blank if this is
the first submission for this product.» İlk sürümde buraya özellik listesi yazmak,
mağazada «Yenilikler» başlığı altında ürünün ta kendisini tekrar etmek olur (kural 5:
veri tekrarı yok).

Sonraki güncellemeler için kalıp — sürüm numarası `infra/surum.py: SURUM` ile aynı olmalı:

```
1.2.0
• (değişen ne varsa, kullanıcının gördüğü dille)
• (düzeltilen arıza: neyin yanlış göründüğü, artık ne gösterdiği)
```

---

## Product features *(madde başına en fazla 200 karakter · en çok 20 madde)*

Her satır ayrı bir «Product features» kutusudur; «Add more» ile sırayla eklenir.

```
Anlık bilanço: seçtiğiniz tarih itibarıyla TDHP formatında AKTİF/PASİF, bölüm alt toplamları ve denge kontrolü
Gelir tablosu: net satıştan dönem net kârına kâr/zarar şelalesi, brüt/faaliyet/net marj
Alacak & Borç: vadeye göre yaşlandırma, tahsilat performansı (DSO/DPO) ve ileriye dönük net vade takvimi
Nakit Akış: bankadan fiilen geçen para; tahsilat, satıcı ödemesi, kredi, vergi ve SGK kırılımıyla
Kategoriye tıklayınca arkasındaki fişler açılır: tarih, yevmiye no, karşı hesap, tutar
Nakit & Kârlılık: depodan geçen mal ve bankadan geçen paradan fiili brüt marj, resmî tabloyla mutabakat
Mukayese & Oranlar: aylık satış/alış/nakit trendi, cari oran, asit-test, borç/özkaynak ve yıllar arası mukayese
Tahmin: geçmişten doldurulan ama elle değiştirilebilen varsayımlarla 36 aya kadar nakit ve kâr projeksiyonu
Reel Değer: açık alacak ve borçların vade yapısını bugünkü değerine çevirir
Yapay Zekâ Yorumu: kendi API anahtarınızla dönemin raporlarından sade Türkçe yönetim yorumu
Her rapor kurumsal PDF ve Excel uyumlu CSV olarak dışa aktarılır
Veriniz kendi sunucunuzda kalır: telemetri yok, hesap açma yok, veritabanına yalnız okuma erişimi
```

---

## Short title *(isteğe bağlı · en fazla 50 karakter)*

```
MikRapor
```

## Voice title *(isteğe bağlı · en fazla 100 karakter)*

Boş bırakın — Xbox/sesli komut içindir, masaüstü uygulamasında kullanılmaz.

---

## Short description *(en fazla 1.000 karakter · önerilen 270)*

```
Mikro ERP verinizden bilanço, gelir tablosu, nakit akışı ve alacak yaşlandırmasını saniyeler içinde hazırlar. Ay sonunu beklemeyin: tarih aralığını seçin, rakamı görün, PDF ya da CSV alın. Veriniz kendi sunucunuzda kalır — arada bize ait bir sunucu yoktur.
```

---

## Keywords *(en çok 7 anahtar · her biri en fazla 40 karakter · toplam en fazla 21 kelime)*

Her satırı ayrı yazıp **Enter**'a basın.

```
mikro erp raporlama
bilanço gelir tablosu
nakit akışı raporu
alacak yaşlandırma
cari hesap analizi
finansal analiz
ön muhasebe raporu
```

Toplam 19 kelime — sınır 21.

`mikro erp raporlama` bilerek duruyor: kullanıcının arama kutusuna yazdığı ilk şey o.
Başkasının markasını anahtar kelimede kullanmak Store politikasında yanıltıcı olmamak
koşuluna bağlıdır; açıklamanın sonundaki «bağımsız üründür» cümlesi tam bu yüzden var.
Rahatsız ederse o satırı `mikro uyumlu raporlama` yapın, kelime sayısı değişmez.

---

## Copyright and trademark info *(en fazla 200 karakter)*

```
© 2026 Hidroteknik Fabr. Malz. San. Tic. A.Ş. Tüm hakları saklıdır. «Mikro» ve «Mikro ERP» adları sahiplerinin markalarıdır; MikRapor bağımsız bir üründür.
```

---

## Additional license terms *(en fazla 10.000 karakter)*

**Boş bırakın.** Microsoft'un Standart Uygulama Lisans Koşulları yeterlidir; ek koşul
yazmak hem okunmaz hem eskir (kural 4). Uygulama zaten hiçbir kişisel veri toplamıyor,
garanti reddi standart koşullarda mevcut.

---

## Developed by *(en fazla 255 karakter)*

```
Hidroteknik A.Ş.
```

`PublisherDisplayName` ile aynı aileden olsun diye. Bu alan boş bırakılırsa listede hiç
görünmez.

---

## Bu formda BLOKE eden tek şey: ekran görüntüsü

En az bir masaüstü ekran görüntüsü zorunlu (form kırmızı uyarı veriyor). Kurallar:

| ne | değer |
|---|---|
| en küçük | 1366 × 768 (daha büyüğü önerilir) |
| biçim | .png |
| dosya | 50 MB'den küçük, en çok 10 adet |
| önerilen | cihaz ailesi başına en az 4 |

Depodaki eski ekran görüntüsü `web/ekran-gelir-tablosu.png` **760 × 483** — sınırın
altında, yüklenmez.

**Kareler artık betikle üretiliyor** (Mikro sunucusu gerekmez):

```
python -m demo.ekran_goruntusu ekran-goruntuleri
```

Sekiz kare, 1600 × 1000, kurgu firma `ÖRNEK SANAYİ VE TİCARET A.Ş.` — sıra satın alma
kararını veren sekmelerle başlar: Alacak & Borç → Nakit Akış → Bilanço → Mukayese &
Oranlar → Nakit & Kârlılık → Gelir Tablosu → Tahmin → Reel Değer. İlk dördü yüklemek
yeter; Store cihaz ailesi başına en az 4 öneriyor, en çok 10 kabul ediyor.

Gerçek cari ünvanı ya da gerçek ciro mağaza sayfasına **konmaz**; defter tamamen
kurgudur (`demo/defter.py`).

Uygulamayı elle gezip kendi karelerini almak istersen:

```
python -m demo.calistir                        # 1600×1000
MIKRAPOR_DEMO_BOYUT=1920x1080 python -m demo.calistir
```

Demo modunda premium kilitleri açıktır; uygulamanın kendi öntanımlı penceresi
(1220 × 840) Store asgarisinin **altında** olduğu için elle çekerken pencereyi
küçültme.

---

## Bu formda OLMAYAN ama gönderimden önce gereken alanlar

- **Gizlilik politikası adresi** (Properties sayfası) — zorunlu. `PRIVACY.md` yazıldı ama
  yayımlanmadı; `mikrapor.hidroteknik.com.tr` sayfasında yalnız özet bir bölüm var
  (`#gizlilik`). Tam metnin kendi adresi olmalı, ör.
  `https://mikrapor.hidroteknik.com.tr/gizlilik`.
- **Destek iletişimi** — `mikrapor@hidroteknik.com.tr` (`infra/surum.py: ILETISIM`).
- **Yaş derecelendirmesi** — iş uygulaması; anket «reklam yok, kullanıcı içeriği yok,
  veri toplama yok» olarak doldurulur.
- **Premium eklentisi** — `mikrapor-premium` / Store ID `9PF68PSTZNTP` ürünü aynı
  gönderimde yayımda olmalı; uygulamadaki «Premium'a geç» düğmesi doğrudan o sayfayı
  açıyor (`infra/surum.py: satin_alma_url`).
- **Store logoları** (bu formdaki isteğe bağlı kutular) — boş bırakılabilir; Store
  paketteki logoları kullanır (`assets/store/*`). Xbox görselleri gerekmez.

## Bir tutarsızlık: telif sahibi iki ad taşıyor

`LICENSE` dosyası «Copyright (c) 2026 **Mercan Software**» diyor, `infra/surum.py: TELIF`
ve README ise «© 2026 **Hidroteknik A.Ş.**». Mağaza yayıncı hesabı Hidroteknik olduğu için
listede Hidroteknik yazıyor. İkisinden biri düzeltilmeli — mağaza sayfası ile depodaki
lisans dosyasının farklı sahip göstermesi, marka itirazında savunulacak bir durum değil.
