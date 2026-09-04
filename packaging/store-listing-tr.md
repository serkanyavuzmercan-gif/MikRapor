# Microsoft Store — Mağaza listesi metinleri (tr-TR)

Partner Center → **Store listings → Turkish (Türkiye)** sayfasındaki alanların birebir
karşılığı. Her blok olduğu gibi kopyalanıp yapıştırılmak içindir.

Metinler koddan türetildi, uydurulmadı: sekme adları ve ücretsiz/premium bölünmesi
`domain/lisans.py`, sekme anlatımları `ui/tabs/*.ACIKLAMA`, künye `infra/surum.py`,
gizlilik `PRIVACY.md`. Bir sekme adı değişirse **burası da değişir** (kural 5: aynı
rapor, tek isim).

Sürüm 1.4.0'a göre yazılmıştır.

---

## Canlıdaki listeleme NE DURUMDA (ölçüldü, tahmin değil)

Yayındaki metin Store'un açık katalog ucundan okunabilir — Partner Center'a girmeden,
hiçbir şeyi bozma riski olmadan:

```
https://displaycatalog.mp.microsoft.com/v7.0/products/9NB421K1Z0GB?market=TR&languages=tr-TR&fieldsTemplate=Details
```

(`apps.microsoft.com/detail/9NB421K1Z0GB` sayfası JS ile çizildiği için metin ham
HTML'de yoktur; yukarıdaki uç JSON döndürür.)

Son ölçümde:

| alan | canlı durum |
|---|---|
| Description | **221 karakter** — kısa açıklamanın birebir kopyası (sınır 10.000) |
| Product features | **0 madde** (sınır 20) |
| Ekran görüntüsü | 4 ✓ |
| Geliştiren / Yayıncı | Hidroteknik ✓ |
| Kategori · yaş derecesi | Productivity ✓ · tanımlı ✓ |
| Eklenti (IAP) | bağlı ✓ (`HasAddOns: true`) |
| Sürüm notu · anahtar kelime | boş |

**İYİ HABER: yanlış beyan YOK.** Açıklama premium bölünmesinden hiç söz etmiyor,
dolayısıyla eski bölünmeyi anlatan hatalı bir cümle de yok.

**ASIL EKSİK: uygulamanın Mikro ERP gerektirdiği hiçbir yerde yazmıyor.** Rozette
«In-App Purchases» görünüyor ama neyi açtığı da yazmıyor. Mikro'su olmayan biri kurup
çalıştıramayınca bu, kötü yorum ve iade olarak geri döner. Aşağıdaki metinlerin var
olma sebebi budur.

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

## Description *(zorunlu · en fazla 10.000 karakter)*

Premium bölünmesi bu metinde **yürürlükteki hâliyle** yazılıdır: sekiz rapor ücretsiz,
eklenti Yapay Zekâ Yorumu ile PDF/CSV çıktısını açar (`domain/lisans.py`).

```
Mikro ERP verinizi mali müşavir raporu beklemeden okunur hâle getirir. Tarih aralığını seçersiniz, rapor saniyeler içinde ekranda olur. Bilanço, gelir tablosu, nakit akışı, alacak yaşlandırması, kârlılık ve yıllar arası mukayese — hepsi doğrudan kendi sunucunuzdaki veriden hesaplanır.

Ay sonunu beklemek yerine bugünün rakamına bakarsınız: kimden ne zaman para girecek, bu ay kaç TL nakit çıktı, hangi müşteri ne kadar geciktiriyor, kâr gerçekten kâr mı.

NASIL ÇALIŞIR

1. Mikro bağlantı bilgilerinizi girersiniz (API adresi, firma kodu, kullanıcı). Bilgiler yalnız o bilgisayarda, şifreli saklanır.
2. Tarih aralığını seçersiniz — bu ay, çeyrek, yıl ya da serbest aralık. Yılları ayrı veritabanlarında tutuyorsanız program hangi yılın nerede olduğunu kendi bulur.
3. Raporu getirirsiniz. Rakamlar saniyeler içinde ekranda; dışarı almak isterseniz kurumsal PDF ve Excel uyumlu CSV eklentiyle açılır.

RAPORLAR

• Alacak & Borç — Açık alacak ve borçların vadeye göre yaşlandırması, dönem tahsilat/ödeme performansı (DSO/DPO) ve ileriye dönük net vade takvimi: ne girecek, ne çıkacak. En çok alacaklı ve borçlu cariler.

• Nakit Akış — Banka ve kasadan fiilen geçen para, karşı tarafına göre kategorize: müşteri tahsilatı, satıcı ödemesi, kredi kullanım/ödemesi, vergi, SGK, personel, genel giderler. Açılış → girişler − çıkışlar → kapanış. Bir kategoriye tıklayınca arkasındaki fişler tarih, yevmiye no ve tutarıyla açılır. KDV'nin kaç gün kendi kesenizden finanse edildiğini ayrıca gösterir.

• Bilanço — Seçtiğiniz tarih itibarıyla Tek Düzen Hesap Planı bilançosu: AKTİF/PASİF, bölüm alt toplamları, denge kontrolü ve dönem net kâr/zararı.

• Gelir Tablosu — Net satıştan dönem net kârına kâr/zarar şelalesi (satışların maliyeti, faaliyet, diğer, finansman) ve brüt/faaliyet/net marj. Dönem kârı bilançoyla birebir tutar.

• Nakit & Kârlılık — Faturalar muhasebeleştirilmeyi beklemeden, deponuzdan geçen mal ve bankadan geçen para üzerinden fiili brüt marj, nakit akışı ve işletme sermayesi; resmî gelir tablosuyla mutabakatı.

• Mukayese & Oranlar — Aylık satış, alış, brüt kâr ve nakit trendi; cari oran, asit-test ve borç/özkaynak yan yana. İsterseniz geçmiş yılların aynı dönemiyle mukayese.

• Tahmin & Projeksiyon — Geçmişten otomatik doldurulan ama elinizle değiştirebileceğiniz varsayımlarla (aylık ciro, büyüme, brüt marj, sabit gider) 36 aya kadar ciro, kâr ve kümülatif nakit projeksiyonu. Banka kredisi taksitleriniz gerçek vade takvimiyle hesaba katılır. Nakit eksiye düşüyorsa hangi ay düşeceğini söyler.

• Reel Değer — Vadeli satmak size neye mal oluyor, vadeli almak ne kazandırıyor? Açık alacak ve borçları vade yapısına göre bugünkü değerine çevirir. Muhasebe tutarlarını değiştirmez.

• Yapay Zekâ Yorumu — Dönemin raporlarından sade Türkçe bir yönetim yorumu: özet, iyi gidenler, riskler, bu ay yapılacaklar. Kendi API anahtarınızla çalışır (Anthropic, OpenAI, Google Gemini, DeepSeek, xAI ya da OpenAI uyumlu özel bir adres). Model seçmeniz gerekmez.

RAKAMIN ARKASI GÖRÜNÜR

Şüpheli rakam gösterilmez. Bir değer güvenilir biçimde hesaplanamıyorsa boş bırakılır ve sebebi rakamın yanında yazar — «hesaplanamadı» demek, yanlış rakam basmaktan iyidir. Aykırı kayıtlar (yanlış girilmiş tutarlar) rapor toplamlarından çıkarılır ve kaçının çıkarıldığı ekranda yazar. Ayrıca Veri Sağlığı penceresi Mikro kayıtlarınızdaki bozuk kayıtları hangi evrak, hangi tarih olduğuyla listeler.

VERİNİZ BİLGİSAYARINIZDAN ÇIKMAZ

MikRapor kapalı devre çalışır. Bağlantı doğrudan sizin Mikro sunucunuzladır; arada bize ait bir sunucu yoktur. Hesap açmanız istenmez, telemetri, analitik ve reklam yoktur. Mikro veritabanınıza yalnızca okuma için bağlanılır: hiçbir kayıt yazılmaz, değiştirilmez, silinmez.

Tek istisna «Yapay Zekâ Yorumu» sekmesidir. Orada da veri, ancak kendi API anahtarınızı girip paylaşım onayını işaretlediğinizde dışarı çıkar; ne gönderildiği ekranda yazar. Onayı kaldırdığınızda o yol tamamen kapanır.

ÜCRETSİZ NE VAR, EKLENTİ NE AÇIYOR

Uygulama ücretsiz kurulur ve sekiz raporun tamamı ücretsiz açılır: Alacak & Borç, Nakit Akış, Bilanço, Gelir Tablosu, Nakit & Kârlılık, Mukayese & Oranlar, Tahmin & Projeksiyon ve Reel Değer. Süre sınırı yoktur, rapor sayısı sınırı yoktur, veri kısıtlanmaz.

Tek seferlik eklenti iki şeyi açar: Yapay Zekâ Yorumu sekmesi ve raporların kurumsal PDF / Excel uyumlu CSV olarak dışa aktarımı. Abonelik değildir.

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

**Boş bırakılmaz.** Formun notu «ilk gönderimse boş bırakın» der; uygulama 1.4.0 olarak
çoktan yayında, yani bu ilk gönderim değil. Canlıda bu alan şu an boş.

```
1.4.0
• Tahmin & Projeksiyon: banka kredisi taksitleriniz gerçek vade takvimiyle projeksiyona girdi.
• Nakit & Kârlılık: rapor tek hikâye olacak şekilde yeniden düzenlendi.
• Mukayese & Oranlar: boş kalan bir oranın sebebi artık satırın kendisinde yazıyor.
• Reel Değer: vade maliyeti, vade avantajı ve net vade etkisi ayrı kartlarda.
• Yapay Zekâ Yorumu: kapsamlı rapor biçimine geçti.
• Mikro Ayarları: bağlantı alanları öne alındı, eksik alan uyarısı netleşti.
```

---

## Product features *(madde başına en fazla 200 karakter · en çok 20 madde)*

Her satır ayrı bir «Product features» kutusudur; «Add more» ile sırayla eklenir.

Son iki maddedeki **«(eklenti ile)»** şart: onsuz PDF/CSV ve Yapay Zekâ ücretsiz sanılır.

```
Anlık bilanço: seçtiğiniz tarih itibarıyla TDHP formatında AKTİF/PASİF, bölüm alt toplamları ve denge kontrolü
Gelir tablosu: net satıştan dönem net kârına kâr/zarar şelalesi, brüt/faaliyet/net marj
Alacak & Borç: vadeye göre yaşlandırma, tahsilat performansı (DSO/DPO) ve ileriye dönük net vade takvimi
Nakit Akış: bankadan fiilen geçen para; tahsilat, satıcı ödemesi, kredi, vergi ve SGK kırılımıyla
Kategoriye tıklayınca arkasındaki fişler açılır: tarih, yevmiye no, karşı hesap, tutar
Nakit & Kârlılık: depodan geçen mal ve bankadan geçen paradan fiili brüt marj, resmî tabloyla mutabakat
Mukayese & Oranlar: aylık satış/alış/nakit trendi, cari oran, asit-test, borç/özkaynak ve yıllar arası mukayese
Tahmin: geçmişten doldurulan varsayımlar ve gerçek kredi taksit takvimiyle 36 aya kadar nakit ve kâr projeksiyonu
Reel Değer: açık alacak ve borçların vade yapısını bugünkü değerine çevirir
Çalışan bir Mikro ERP kurulumuna bağlanır; veritabanınıza yalnız okuma erişimi ister
Veriniz kendi sunucunuzda kalır: telemetri yok, hesap açma yok, reklam yok
Yapay Zekâ Yorumu: kendi API anahtarınızla dönemin raporlarından sade Türkçe yönetim yorumu (eklenti ile)
Kurumsal PDF ve Excel uyumlu CSV dışa aktarım (eklenti ile)
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

Canlıdaki metin *«…PDF ya da CSV alın»* diyor; dışa aktarım artık eklentiye bağlı
olduğu için o cümle ücretsiz izlenimi veriyor. Düzeltilmiş hâli:

```
Mikro ERP verinizden bilanço, gelir tablosu, nakit akışı ve alacak yaşlandırmasını saniyeler içinde hazırlar. Ay sonunu beklemeyin: tarih aralığını seçin, bugünün rakamını görün. Veriniz kendi sunucunuzda kalır — arada bize ait bir sunucu yoktur.
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

## Ekran görüntüsü

Canlıda **4 kare zaten yüklü**. Yenilemek gerekirse Mikro sunucusu olmadan üretilir:

```
python -m demo.ekran_goruntusu ekran-goruntuleri
```

Sekiz kare, 1600 × 1000, kurgu firma `ÖRNEK SANAYİ VE TİCARET A.Ş.` — sıra satın alma
kararını veren sekmelerle başlar. Store kuralları: en az 1366 × 768, .png, 50 MB altı,
en çok 10 adet; cihaz ailesi başına en az 4 önerilir.

Uygulamanın kendi öntanımlı penceresi (1220 × 840) Store asgarisinin **altındadır**, o
yüzden elle çekerken pencereyi küçültmeyin. Elle gezmek için:

```
python -m demo.calistir                        # 1600×1000, premium kilitleri açık
MIKRAPOR_DEMO_BOYUT=1920x1080 python -m demo.calistir
```

Gerçek cari ünvanı ya da gerçek ciro mağaza sayfasına **konmaz**; defter tamamen
kurgudur (`demo/defter.py`).

---

## «We are unable to save listing» hatası

Canlıda görüldü: alanlar tek tek kaydedilmeye çalışıldığında da aynı hata döndü, yani
sorun METİNDE DEĞİL — hiçbir kaydetme isteği geçmiyordu. Sıraya göre bakılacak yerler:

1. **Gönderim düzenlenebilir değil.** *Application overview*'da durum «In certification»,
   «Publishing» ya da «Pre-processing» ise listeleme kilitlidir. Yarım kalmış taslak
   varsa **Delete submission** ile silip **Update** ile temiz gönderim başlatın.
2. **Hesap yetkisi.** *Account settings → User management*: rol görüntüleyiciyse form
   açılır ama kaydetme reddedilir.
3. **Oturum/çerez.** `partner.microsoft.com` çerezlerini temizleyip yeniden girin; tek
   sekme, gizli pencere.
4. **Microsoft tarafında geçici arıza.** Bu mesaj Partner Center'ın jenerik 5xx
   karşılığıdır; saatlerce sürebilir.

Alan sınırları eleme dışı: açıklama ~5.000/10.000, en uzun özellik maddesi 116/200,
anahtar kelimeler 19/21 kelime, telif satırı 155/200 karakter.

---

## Gönderimden önce gereken, bu formda OLMAYAN alanlar

- **Gizlilik politikası adresi** — `web/gizlilik-politikasi.html` yayında ve tanıtım
  sayfasından bağlı (`test_web` sınıyor).
- **Destek iletişimi** — `mikrapor@hidroteknik.com.tr` (`infra/surum.py: ILETISIM`).
- **Yaş derecelendirmesi** — canlıda tanımlı.
- **Premium eklentisi** — `mikrapor-premium` / Store ID `9PF68PSTZNTP`; canlıda bağlı
  (`HasAddOns: true`). Uygulamadaki «Premium'a geç» düğmesi doğrudan o ürünü açar.
- **Store logoları** — boş bırakılabilir; Store paketteki logoları kullanır
  (`assets/store/*`).

---

## Karara bağlanmış: telif satırı depoda AYNEN KALIYOR

`LICENSE` dosyası «Copyright (c) 2026 **Mercan Software**» diyor, `infra/surum.py: TELIF`
ve README ise «© 2026 **Hidroteknik A.Ş.**». Mağaza yayıncısı Hidroteknik olduğu için
listede Hidroteknik yazar.

**Kullanıcının kararı: `LICENSE` değişmeyecek.** Bu satır burada, bir daha açılmasın
diye duruyor — sonradan gelen biri «tutarsızlık var» deyip düzeltmeye kalkmasın.
