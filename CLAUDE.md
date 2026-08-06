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
- Mukayese tablosunun değişim sütunu, odak yılı **önceki yılların ORTALAMASINA**
  oranlar (`kiyas_tabani`); başlık bunu yazar: `2026 / önceki ort.`. Eskiden yalnız
  ilk yılla son yıl kıyaslanıyordu — başlık «2020→2026» derken aradaki beş yıl hiç
  hesaba girmiyordu. İki sütun varsa ortalama zaten tek yıldır, başlık `2025→2026`.

### Tek istisna: kullanıcının açıkça istemesi

Mukayese & Oranlar'daki **«Geçmiş yılların aynı dönemiyle mukayese et»** kutusu
işaretlenirse tablo, seçili dönemin bir yıl öncesini de getirir. Bu kuralı bozmaz:
program kendi kafasına göre dışarı çıkmıyor, kullanıcı istediği için çıkıyor ve **ne
geldiği sütun başlığında yazıyor** (`28.07.2024–28.07.2025`).

**Varsayılan kapalıdır ve her koşudan sonra kendini kapatır.** Her geçmiş yıl ~5 sorgu
demek; işaret bir kez konulup unutulunca kullanıcı istemediği hâlde her rapor
dakikalarca sürüyordu. Pahalı yol her seferinde açıkça seçilir.

Buna ihtiyaç var çünkü takvim yılına bölünmüş sütunlar farklı uzunlukta olabilir:
canlıda 2025 sütunu 5 ay, 2026 sütunu 7 aydı ve tablo «%+4 büyüme» gösteriyordu —
aylığa indirilince satış **%25 düşmüştü**. Eşit uzunlukta iki pencere olmadan akış
kalemleri (satış, kâr) kıyaslanamaz. Bakiye kalemleri etkilenmez.

İhlali engelleyen testler: `test_mukayese_fetch.TestSecilenAralikKutsal`,
`TestYardimciPencereKirpma`, `TestGecenYilAyniDonem`.

---

## 1b. HANGİ SEKME HANGİ KAYNAKTAN

**İlk iki sekme (Bilanço, Gelir Tablosu) RESMİ kayda dayanır; diğer hepsi
CANLI/REEL veriye.**

| Kaynak | Nereden | Hangi sekmeler |
|---|---|---|
| Resmi | mizan, GL 6xx | Bilanço, Gelir Tablosu |
| Canlı | STOK_HAREKETLERI, cari hareketler, GL nakit ve KDV hesapları | diğer hepsi |

Mukayese tablosu mizandan kurulduğu için, satışın maliyeti (62) işlenmemiş bir yılda
kârlılığın tamamı boşalıyordu — oysa Nakit & Kârlılık aynı dönemin kârlılığını depodan
geçen maldan zaten hesaplıyordu. Tabloya 62'ye hiç dokunmayan canlı satırlar eklendi:
**Fiili Satış · Fiili Alış · Fiili Al-Sat Farkı · Fiili Al-Sat Marjı.**

Stok *seviyesi* canlı veriden hesaplanamaz: geçmişteki bütün hareketlerin toplamıdır,
yani aralığın dışına çıkmayı gerektirir. Tek meşru kaynağı mizandır ve maliyet
işlenmemişse şişiktir → `—`.

### KDV bir gider değil, FİNANSMAN yüküdür

100 TL'lik satışın 20 TL KDV'si fatura kesilince doğar ve ertesi ay beyanla devlete
ödenir; o 100 TL ise müşteriden ortalama 90 günde tahsil edilir. Arada kalan sürede
KDV'yi firma kendi kesesinden finanse eder ve bu, nakit akışta hiçbir kalemin altında
görünmüyordu. Nakit Akış'taki **KDV NAKİT KÖPRÜSÜ** paneli bunu gösterir
(`domain/kdv.py`): hesaplanan (391) − indirilecek (191) = devlete kalan net, ölçülen
efektif oran, **tahsil edilmemiş alacağın içindeki KDV** ve kaç gün finanse edildiği.

Alacak KDV DÂHİL doğduğu için içindeki KDV `alacak × oran/(100+oran)`; tahsil süresinin
paydası da NET değil BRÜT satıştır.

---

## 2. Güvenilmez veri gösterilmez

Rakam şüpheliyse `—` yazılır ve **sebebi rakamın yanında** söylenir. Boş hücreyi
açıklamasız bırakmak da, şişik rakamı sessizce basmak da kabul edilmez.

Örnek: satışların maliyeti (62) muhasebeye işlenmemişse eksik `621/153` fişinin iki
ayağı vardır — kâr **ve** stok aynı tutarda şişer. O yılın kâr kalemleri, stoğu,
özkaynağı, aktif toplamı ve bunlardan türeyen oranları boş bırakılır. Asit-Test
etkilenmez: `(dönen − stok)` şişkinliği zaten götürür.

### BAKILAMAYAN, TEMİZ SAYILMAZ

«Bulgu yok» ile «bakamadım» aynı şey değildir. `VeriSagligi.temiz` yalnız
`bulgular`a bakıyordu; mizan ve stok ikisi de düştüğünde ekran ve **müşavire giden
PDF** kalın puntoyla «Veriniz sağlıklı» yazıyordu — sıfır kayıt taranmışken. PDF
kendi içinde çelişiyordu: on dört satır aşağıda «Bu alanlar «temiz» sayılmamalıdır».
Koruma yeşil kartta vardı (`temiz and not okunamayan`), başlıkta yoktu.

**Düşen kaynağı ÇAĞIRAN bildirmez, veri kendisi söyler.** `build_veri_sagligi`
`bilanco is None` / `stok_rows is None` görüyor; doğruluğu çağıranın
`okunamayan.append()` yazmayı hatırlamasına bağlamak aynı elemeyi iki yere yazmaktı
(bkz. `_bakiye_kosulu`, `kredi_banka_mi`). `stok_rows=[]` ile `stok_rows=None`
FARKLIDIR: «okundu, boştu» ve «okunamadı».

**DÜŞEN KAYNAK ile DARALAN KAPSAM ayrı tutulur** — ikisi tek listede durunca ters
yönde yanlış alarm çıkıyordu. `yil_client` katalog boşken bilerek seçili firmayla
devam ediyor, yani mizan ve stok BAŞARIYLA okunuyor, yalnız tek yıl taranıyor. Bu
`okunamayan`a yazılınca sonuç «kontrol tamamlanamadı» görünüyordu: kural 3b'nin
yasakladığı, hiçbir rakamı bozmayan uyarı. Artık `okunamayan` «temiz» demeyi
engeller, `kapsam_notu` engellemez — yalnız `kapsam_satiri()`nde yazar.

Kapsam cümlesi **silinmez, doğrusu yazılır** ve ekran ile PDF onu tek yerden alır
(`kapsam_satiri()`). «Bütün» kelimesi yalnız gerçekten bütünken geçer; kapsam notu
varken «bütün kayıtlar tarandı» demek hemen ardındaki cümleyle çelişiyordu.
Düşen kaynak SAYILMAZ, ADLANDIRILIR: «2 kaynak okunamadı» kullanıcıya hangisinin
düştüğünü söylemez, toplam kaç kaynak olduğunu bilmediği için hepsinin düştüğünü de
anlamaz.

İhlali engelleyen testler: `test_veri_sagligi.TestOkunamayanKaynak`,
`test_ui_smoke.test_katalog_okunamazsa_daralma_yazilir`.

### HATA SEBEBİ ATILMAZ

Bağlantı rozeti yalnız «Bağlanılamadı» deyip susuyordu; `_on_ping_hata` sebebi
parametre olarak alıyor ama kullanmıyordu (`_msg`). Kullanıcı şifre mi, TLS mi, ağ mı
bilemiyor. Rozetin balon mekanizması zaten vardı ve bağlıyken firma adı için
kullanılıyordu — sebep oraya yazılır. Bir hata mesajı elinizdeyse onu göstermemenin
gerekçesi olamaz.

## 3. Hesaplayabiliyorsak gizlemeyiz

Gizlemek çare değil. Bir rakam canlı veriden hesaplanabiliyorsa hesaplanır. Ama
hesaplanamıyorsa **tahmin edilmez** — ölçülmüş tek yönlü sınır varsa o yazılır
("en az X"), yoksa `—` kalır.

## 3b. Bir uyarı ancak İŞE YARIYORSA gösterilir

Bulgu/uyarı gösterme ölçütü ikisi BİRDEN doğru olacak:
  (a) ekranda görülen bir rakamı bozuyor,
  (b) kullanıcının yapabileceği bir şey var.

«Satış satırlarının %11'inde maliyet yok» uyarısı bu yüzden kaldırıldı — kendi metni
bile «depodan geçen maldan hesaplanan marj bundan etkilenmez» diyordu, yani hiçbir
rakamı bozmuyordu. Tanımsız evrak tipi yalnız önemli tutarda gösteriliyor (canlıda
cironun %1'iydi).

**«Bize bildirin» YASAK.** Satılan bir üründe «biz» diye bir muhatap yok. Aynı şekilde
kullanıcıya terminal komutu (`stok_diag_cli.py …`) verilmez; tavsiye Mikro'da
yapılabilecek bir şey olmalı.

**Veri Sağlığı sekme DEĞİL**, Mikro Ayarları'ndan açılan bir penceredir: bütün rapor
sekmeleri seçili tarih aralığına bağlıyken o değil, kurulumun hâlini gösterir. Bu yüzden
**bütün geçmişi** tarar (kapsam katalogtan), son 12 ayı değil — bozuk kayıt mevsimsel
değil kalıcıdır. Canlıda 2023'teki 13 bozuk stok kaydı, pencere 12 ay olduğu için hiç
görünmüyordu; oysa o kayıtlar 2023'ü kapsayan HER raporu zehirliyor.

**Bir bulgu «düzeltin» diyorsa hangi kaydın düzeltileceğini de yazar** (`Bulgu.kayitlar`):
tarih, evrak no, stok kodu, miktar, tutar. 390 bin satır içinde 13 kaydı aratmak tavsiye
değildir.

## 3c. Rakamın arkası bir tık uzakta olmalı

Canlı bir demoda mali müşavir «müşteri tahsilatı 3M — bu yapıldı mı?» diye sordu.
Rakam DOĞRUYDU (muhasebe yevmiyesine işlenmiş yüzlerce fişin toplamı) ama gösterilecek
bir şey yoktu ve savunulamadı. Bir uzman rakamına itiraz ettiğinde elinde kanıt yoksa
tartışmayı kaybedersin.

- Nakit Akış'ta kategori satırına tıklayınca arkasındaki fişler açılır
  (`ui/nakit_detay_dialog.py`): tarih, yevmiye no, karşı hesap, tutar.
- **Detay ve özet AYNI SQL gövdesini paylaşır** (`_gl_nakit_kirilim`), sınıflama aynı
  fonksiyondan gelir (`kategori_etiketi`). Ayrı yazılmış iki sorgu er ya da geç ayrışır;
  «özet 3M diyor, döküm 2,8M» durumu hiç detay olmamasından KÖTÜDÜR.
- Pencere altta detay toplamı ile panel toplamını kıyaslar ve **tutmuyorsa söyler.**

Ayrıca «gerçekleşen» ile «öngörü» ekranda ayrışır: panel başlıkları `GERÇEKLEŞEN
GİRİŞLER · 01.01–29.07 · 412 hareket`, runway ise `PROJEKSİYON — HENÜZ GERÇEKLEŞMEDİ`.
Hareket sayısı, rakamın tek bir işlem değil dönem toplamı olduğunu sorulmadan söyler.

## 4. LESS IS MORE

Kısa ve öz. Etiket, uyarı ve not şişkinliği yok. Tablo altına altı paragraf uyarı
yazmak, hiç yazmamaktan kötüdür — kimse okumaz ve içlerinden biri eskiyip yanlış olur.
(Canlıda "Tutarlar TL'dir" notu, TL bölümü tablodan kaldırıldıktan sonra orada kalıp
dolar rakamlarını TL sandırıyordu.)

## 5. Aynı rapor, tek isim

Sekme adı = PDF başlığı = sayfa başlığı = dosya adı. Sekmeler arasında veri tekrarı yok.

Reel Değer'deki cari listesi bu yüzden **ERİMEYE göre sıralanır, bakiyeye göre değil**:
bakiye sırası Alacak & Borç'taki «en çok alacak»ın tekrarı olurdu. Erime = tutar ×
bekleme, o yüzden sıra gerçekten farklı çıkar — 1M'lik 15 günlük müşteri, 500K'lık
120 günlük müşteriden AZ eritir. Liste, «vade maliyeti 3,5M» rakamının arkasını
gösterir (kural 3c).

**«Kaç gün kendi kesenden finanse ediyorsun» sorusu YALNIZ Alacak & Borç'ta cevaplanır**
(`TahsilatAlacak.dso/.dpo` → «Nakit döngüsü: tahsilat Xg, ödeme Yg»). Reel Değer'e
eklenen ikinci bir «vade makası» paneli kaldırıldı: iki *vadeye kalan gün* ortalamasının
farkıydı, canlıda 17−18 = **1 gün** çıkıyordu ve işareti de o sekmenin tersiydi. İki
sekme aynı soruya çelişen cevap verince ikisine de güven gider.

**`AcikVadeParcasi.vade_gun` VADEYE KALAN gündür, tahsil süresi DEĞİL.** Vadesi geçmiş
kalem 0 sayılır, ayrıca FIFO en eski faturayı kapattığı için açık kalanlar en yeni
faturalardır — yani tahsilat iyileştikçe bu rakam DÜŞER. 90 gün vadeyle çalışan firmada
%70 tahsilatta 20 güne iniyordu. Bu yüzden başabaş vade farkı **ölçülen DSO'ya**
çapalanır; kalan güne çapalanınca canlıda %1,7 diyordu, doğrusu %9,6 — bir fiyat
tavsiyesinde **5,5 kat** sapma. Pencere DSO'yu ölçmeye yetmiyorsa (`dso > donem_gun`)
kural 3'ün tek yönlü sınırı yazılır: «en az X gün».

Alacağın vade maliyeti bir **ALT SINIRDIR** ve bu ekranda yazar: vadesi geçmiş tutar
«bugün tahsil edilir» sayıldığı için o paranın bekleyeceği süre hesaba girmez.
Her tabloda satır vurgusu (row hover) standarttır, ayrıca istenmesi gerekmez.

**Aynı şeye tek kelime: «MUKAYESE».** «Kıyaslama» ve «karşılaştırma» eş anlamlıydı ve
üçü birden kullanılıyordu; ekranda iki ayrı rapor varmış izlenimi veriyor. Sekmenin adı
`Mukayese & Oranlar`. (Yalnız modele giden yönerge metni serbesttir; oradaki sözcük
kullanıcıya doğrudan görünmez.)

**Ayarlar ekranının da tek adı var: «MİKRO AYARLARI»** (`ui/mikro_settings_dialog.py:
AYARLAR_ADI`). Üç ad birden kullanılıyordu — marka barında «Ayarlar», pencere
başlığında «Mikro Bağlantı Ayarları», hata metinlerinde «Mikro Ayarları». Kullanıcı
*«üstteki Mikro Ayarları'ndan doldurun»* yazısını okuyup o adda bir düğme arıyordu ve
bulamıyordu. Düğme metni, pencere başlığı ve metinlerdeki ad tek sabitten gelir.

**KALDIRILAN AYARA YÖNLENDİREN METİN BIRAKILMAZ.** Üç sekmenin «veri bulunamadı»
uyarısı *«Mikro Ayarları'ndaki **çalışma yılı** ile dönem tarihleri aynı olmalı»*
diyordu; oysa `calisma_yili` ayarı kaldırılmış, yıl seçili tarih aralığından türüyor.
Kullanıcı olmayan bir alanı arayıp programı bozuk sanır. Kural 4'teki «Tutarlar TL'dir»
notunun aynısı: kaldırılan şeye işaret etmeye devam eden bayat metin. Doğrusu
yazıldı — «o yılın veritabanı tanımlı değilse Mikro Ayarları → Yılları Tara».

Bekçi (`test_ui_smoke.TestAyarlarTekAd`) satır grep'lemez, **AST'den yalnız kullanıcıya
giden dizgileri** okur: yorum ve docstring'ler elenir, yoksa bir düzeltmeyi anlatan
yorum kendi bekçisini kırmızıya düşürüyordu.

**Sekme balonu `ACIKLAMA`'dan gelir, ayrıca yazılmaz.** Balon mekanizması (gecikme,
kart, «RAPOR» üst etiketi) yazılmıştı ama `setTabToolTip` hiç çağrılmadığı için metin
boş kalıyor, balon hiç açılmıyordu — üstelik `HeaderTabBar.event()` native tooltip'i
de bastırdığı için hover'da HİÇBİR ŞEY görünmüyordu. Metin boş ekrandakiyle aynı
kaynaktan (`cls.ACIKLAMA`) gelir; ikinci bir metin yazmak ikisinin ayrışması demektir.

**Geri bildirim etiketi kalıcı olmaz.** «Kopyalandı ✓» düğmede öylece kalıyordu;
düğmenin ne yaptığını gizliyor ve ikinci kez basmak isteyen kullanıcı arayacak bir şey
bulamıyor. Geri alma zamanlayıcısı **widget'a parent'lanır** — serbest
`QTimer.singleShot` pencere kapandıktan sonra ateşleyip silinmiş C++ nesnesine
`setText` çağırır. (PyQt6'da 3 argümanlı `singleShot(msec, context, slot)` YOKTUR;
o PySide imzasıdır.) Testi zamanlayıcının **başladığını** sınamalı; geri alma metodunu
doğrudan çağıran test, `start()` silinse bile yeşil kalıyordu.

**Uzun tablo başlığı sabit kalır.** Yıl sütunları QTreeWidget'ın gerçek header'ındadır,
normal satır değil; tablo ekrana sığmıyorsa kendi içinde kayar ki aşağı inerken hangi
rakamın hangi yıl olduğu görünsün. PDF karşılığı `repeatRows=1`.

**SIĞMAYAN SEKME KISALTILIR, GİZLENMEZ.** Sekme çubuğu dar pencerede font/dolgu
merdiveninden sığan en okunaklı basamağı seçer; **hiçbiri sığmazsa** sekmeler oranla
daraltılır ve etiket kısaltılır («Tahmin & Proj…»). Çirkin ama tıklanabilir, görünmezden
iyidir: `setUsesScrollButtons(False)` olduğu için taşan sekme büsbütün ekran dışında
kalıyor, o rapora hiç erişilemiyordu.

Merdiveni uzatmak bunu ÇÖZMEZ, çünkü sorun ölçekte değil platformda: Windows runner'ında
sistem fontu Linux'un **1,59 katı** genişlikte çiziyor, 960px pencerede dokuz sekme orada
hiçbir ölçekte sığmıyor (en dar aday 1206px istiyor, alan 932px). Altı kez körlemesine
tahmin edildi; ancak runner'a ölçüm koyunca görüldü. **İkinci başarısızlıkta tahmin
bırakılır, ölçüm konur.**

`setElideMode` TEK BAŞINA YETMEZ — Qt metni sekmenin kendi genişliğine göre kısaltır,
o genişlik de `tabSizeHint`ten gelir; tam istediğini alan sekmede kısaltacak bir şey
olmaz. Daraltma oranı `_daralt`ta hesaplanır, `tabSizeHint` uygular.

Bekçi `test_ui_smoke.test_sigmayan_sekme_daraltilir_kaybolmaz` geniş fontu **taklit
eder**: yalnız gerçek pencereye bakan test bu yolu Linux CI'da hiç koşturmaz, kod
bozulur ve yeşil kalır (bkz. «bakılamayan, temiz sayılmaz»).

## 6. Bu program yalnız bize göre yazılmaz

Hedef, Mikro ERP kullanan HER firmaya satmak. Bir kurulumun iş akışını varsayılan
yapmak, başka kurulumda sessizce yanlış rakam demektir — hem de küçük farkla değil:
aynı veride «Satış: İrsaliye + Fatura» 20.481.407 TL derken «Yalnız Fatura»
1.095.172 TL diyor. **On dokuz kat.**

Bu yüzden kurulum bağımlı her kural VARSAYILMAZ, ÖLÇÜLÜR (`domain/kurulum.py`;
Hesaplama Kuralları → «Kurulumdan otomatik algıla»). Ölçüm zayıfsa ayar
DEĞİŞTİRİLMEZ: yanlış bir otomatik ayar, elle seçilmişten daha zararlıdır çünkü
kullanıcı onu kendi seçmediği için sorgulamaz.

Ölçülen kurulum farkları: faturalaşma kopya satır yaratıyor mu, mal irsaliyeyle mi
faturayla mı giriyor, `evraktip 12` gerçek alış mı depo transferi mi.

**AYKIRI KAYIT EŞİĞİ DE VARSAYILMAZ.** «Satır başına 2 milyon TL'yi aşan kayıt bozuktur»
demek küçük firmada hiçbir şey yakalamaz, büyük firmada gerçek faturayı bozuk ilan eder.
Eşik dönemin KENDİ ortalama satırından ölçülür (`infra/mikro_fetch.py: AYKIRI_KAT`);
aykırı satırlar rapor toplamlarına girmez ama **elenen sessizce atılmaz** — kaç satır ve
ne kadar tutar çıkarıldığı rakamın yanında yazar. Canlıda 13 böyle satır vardı; biri
2 adet mala 3,3 TRİLYON TL yazıyordu ve 2023'ü içeren her raporu zehirliyordu.

**KDV oranı da varsayılmaz.** «%20'dir» demek yanlış olurdu: ürün karması %1/%10/%20
karışık olabilir, ihracat satışında KDV hiç doğmaz. Efektif oran dönemin kendi
rakamından ölçülür — hesaplanan KDV (391) ÷ net satış (60/61).

**CARİ ÜNVANI VE STOK KODU DA VARSAYILMAZ** — muhasebeci elle giriyor, temiz olduğu
kabul edilemez. İki gerçek arıza çıktı:

- **CSV:** ünvanın içindeki `;` sütun ayracıdır. Başlık 3 sütunken ünvanlı satır
  4 sütuna çıkıyor, tutar Excel'de yanlış kolona düşüyordu. `domain/ortak.py:
  csv_metin` bunun için yazılmıştı ama 12 üreticiden **1'inde** kullanılıyordu.
- **PDF:** reportlab `Paragraph` içeriğini mini-HTML gibi ayrıştırır. Firma adında ya
  da ünvanda tek bir `<`, belgeyi `paraparser: syntax error: parse ended with 2
  unclosed tags` ile düşürüyordu — kullanıcıya hiçbir şey söylemeyen bir hatayla.
  `&` affediliyordu, `<` affedilmiyordu.

Kaçışlama **çağıranlara bırakılmaz, kapının kendisinde yapılır**: firma adı dokuz
PDF'in hepsine `ui/pdf_ortak.py: letterhead_sade` üzerinden giriyor, `pdf_metin`
orada uygulanır. Kasıtlı markup kuran satırlar (`<b>Etkisi:</b> …`) muaftır — kaçışlama
yalnız DIŞARIDAN gelene. Bekçi test üreticileri tek tek değil topluca koşturur
(`test_pdf_smoke.TestSerbestMetinKacisi`), CSV tarafında sütun sayısı başlıkla
kıyaslanır (`TestCsvSutunKaymasi`).

**Arayüz %100 Türkçe, hesap planı TDHP.** İngilizce sürüm planı yok.

**Sekme sırası sahibe göre**, muhasebeciye göre değil: Alacak & Borç → Nakit Akış →
… → *ayraç* → Bilanço, Gelir Tablosu → *ayraç* → Yapay Zekâ. Program Bilanço ile
açılıyordu; demo, şirket sahibini en az ilgilendiren tablodan başlayınca ürün «bir
muhasebe programı daha» gibi duruyor. Kural 1b'deki resmî/canlı ayrımı korunuyor,
yalnız sıralama tersine döndü.

## 7. Veri dışarı çıkmaz

MikRapor'un dışarıya veri gönderdiği **tek** yer Yapay Zekâ Yorumu sekmesidir; API
anahtarı **ve** açık onay kutusu birlikte olmadan hiçbir ağ çağrısı yapılmaz.

Store lisans kontrolü (`infra/store_lisans.py`) bu kuralın istisnası DEĞİLDİR: Windows'un
kendi Store servisiyle konuşur, MikRapor'un okuduğu hiçbir mali veri o yoldan geçmez.

## 8. Premium: ÇIKTI ücretli, EKRAN değil

Uygulama ücretsiz kurulur ve **dokuz raporun tamamı ekranda eksiksiz çalışır.** Premium
olan iki şey vardır: **PDF/CSV dışa aktarma** ve **Yapay Zekâ Yorumu.**

Önce beş sekme kilitleniyordu (Nakit & Kârlılık, Mukayese, Tahmin, Reel Değer, YZ).
Sekme çubuğunda beş amber nokta belirince ürün «yarısı kilitli» göründü ve kullanıcının
ilk tepkisi bu oldu. Değer anı raporu OKUMAK değil, onu müşavire göndermek ya da
saklamak: ödeme isteği oraya konunca kimseden bir şey alınmıyor ve kural tek cümleyle
anlatılıyor — **«ekranda her şey ücretsiz, dışarı almak premium»**.

**VERİLMİŞ SEKME GERİ ALINMAZ.** Yeni bir sekmeyi premium doğurtmak sorunsuzdur; bugün
ücretsiz kurup Nakit Akış'ı kullanan müşteriden yarın onu geri almak, hiç vermemekten
kötü karşılanır. Liste bu yüzden dar başlar.

**Veri Sağlığı çıktısı ücretsizdir** (`disa_aktarim_kilitli` docstring'i): bozuk kaydı
düzeltmeyi sağlayan raporu kilitlemek, programın doğru çalışmasını parayla şarta
bağlamak olurdu.

**KİLİT TEK KAPIDA.** `_on_pdf` alt sınıflarda eziliyor; kilidi oraya koymak dokuz
sekmede dokuz kez yazmak demekti ve biri unutulunca sessizce bedava dağıtılırdı. Kapı
`RaporTab.disa_aktar`; `ui/app.py` `_on_pdf`/`_on_csv`'yi DOĞRUDAN çağırmaz ve bunu
`test_lisans.TestCiktiKilidi` AST'den sınar.

**`_on_getir` MÜHÜRLÜDÜR, alt sınıf ezmez** — ön koşulunu `_getir_on_kosul`a yazar.
Yapay Zekâ sekmesi eziyor ve kendi kontrollerini `super()`den ÖNCE koşturuyordu:
kilitli kullanıcı «Raporu Getir»e basınca premium penceresi değil «yapay zekâ ayarları
eksik» uyarısı alıyordu, yani tek premium sekmenin kilidi büsbütün baypas oluyordu.
Bekçi: `test_lisans.TestGetirKapisiMuhurlu`.

**SEKME ÇUBUĞUNDA PREMIUM İŞARETİ YOK.** Önce metne « ✦» eklendi, 960px'te çubuğu
taşırdı. Sonra nokta çizildi — genişlik eklemiyordu ama ekranı «yarısı kilitli»
gösteriyordu. Bir işaret ancak kullanıcının yapabileceği bir şeye işaret ediyorsa değer
taşır (kural 3b); kilit zaten sekmenin İÇİNDE anlatılıyor.

**KİLİT KENDİLİĞİNDEN GERİ GELMEZ.** `Store hayır dedi` ile `Store cevap veremedi`
pratikte ayrılamıyor: Microsoft hesabına giriş yapmamış ya da lisansı henüz
senkronlanmamış kullanıcıda da olumsuz cevap dönüyor. İkisini karıştırıp otomatik
kilitlemek, ödemiş müşteriyi kalıcı olarak dışarıda bırakır. Önbellek yalnız POZİTİF
doğrulamayla açılır (`infra/config.py: premium_onbellek_yaz`) ve bir daha kapanmaz.
Kabul edilen bedel: config kopyalanabilir — B2B'de korsanlık teşviki, kilitlenen
müşterinin bedelinden küçüktür.

**SATIN ALMA UYGULAMA İÇİNDE — bu karar ÖLÇÜMLE TERSİNE ÇEVRİLDİ.**

Önce «uygulama içi ödeme penceresi yok» deniyordu: `RequestPurchaseAsync` HWND
bağlaması ister, Python'dan kırılgan görünüyordu, satın alma Store ürün sayfasında
tamamlanacaktı. **O sayfa yok.** Eklenti yayına alındıktan ve eksiksiz yapılandırıldıktan
sonra (Public, tüm pazarlar, Forever, listeleme tam) ölçüldü:

| adres | cevap |
|---|---|
| `apps.microsoft.com/detail/9NB421K1Z0GB` (uygulama) | 200, «In-App Purchases» etiketi var |
| `apps.microsoft.com/detail/9PF68PSTZNTP` (eklenti) | **404 / ProductNotFound** |

Add-on'ların web ürün sayfası yoktur; bu yayın durumundan bağımsız ve kalıcıdır.
Kullanıcıyı oraya göndermek onu kırık bir sayfaya göndermekti. `satin_alma_url()` ve
`eklenti_tanimli()` **silindi** — ölü bırakılsalardı biri «hazır duruyor» deyip 404'e
geri dönerdi.

Kırılganlık korkusu da ölçüldü, tahmin edilmedi (geçici teşhis, Windows runner):
`winsdk._winrt.initialize_with_window` **var**, COM apartmanı QApplication sonrası
**MAINSTA** — yani `IInitializeWithWindow`'un istediği durum. Pencere bağlanamazsa
satın alma **hiç denenmez** (`_pencereye_bagla` → `False`): bağlanmamış çağrı sessizce
başarısız olur ya da arayüzü dondurur.

**DÖNÜŞ İSTİSNA DEĞİL, ENUM.** `StorePurchaseStatus` başarısızlığı durum koduyla
bildirir; yalnız `try/except` koymak «ağ hatası»nı «başarılı» sanmaktı. Her dal
`domain/lisans.py: SatinAlmaSonucu`ya eşlenir ve ayrı mesaj alır. `NotPurchased`
mesajı SEBEP UYDURMAZ — aynı kod hem vazgeçmede hem ödemenin reddinde döner, bu
yüzden «iptal ettiniz» denmez, «satın alma tamamlanmadı» denir.

**SATIN ALMA CEVABI LİSANS OKUMASINDAN GÜÇLÜDÜR.** `ALINDI`/`ZATEN_VAR` gelince
premium DOĞRUDAN açılır ve önbelleğe yazılır (`ui/premium.py: premium_ac`); lisans
yeniden okunmaz. Satın almadan hemen sonra lisans dağıtımı oturmamış olabilir ve o
aralıkta «yok» cevabı gelirse kullanıcı ödediği hâlde kilitli kalırdı. Ayrıca satın
alma uygulama içinde bittiği için **pencere odağı değişmez** — eski
`changeEvent`/`satin_alma_bekleniyor` yolu tetiklenmez, o artık yalnız yedektir.

Bekçiler: `test_lisans.TestStoreKoprusu` (tersine çevrildi, silinmedi),
`TestSatinAlmaSonucu` (enum dallarının tamamı, Store olmadan), `TestAcilisYolu`.

**SON METRE OTOMATİK DOĞRULANAMAZ.** CI'da Store yok; gerçek ödeme denenemez.
Store'dan kurulan sürümde, gerçek Microsoft hesabıyla elle duman testi yapılmadan
«premium çalışıyor» denmez. Bu bir teslim koşuludur.

**LİSANS AÇILIŞ YOLUNDA OKUNMAZ.** `kilitli()` → `_bos_ekran()` → `_build()` zinciri
dokuz sekmenin kurulumunda UI thread'inde koşuyor; oraya senkron WinRT çağrısı koymak
Store yavaşladığında uygulamayı **açılışta** dondurur. `premium_durumu()` yalnız yerel
önbelleği okur; gerçek durum pencere açıldıktan sonra ayrı thread'de öğrenilir
(`ui/app.py: _lisansi_arkaplanda_oku`). Bütün WinRT çağrıları `asyncio.wait_for` ile
üst sınıra bağlıdır.

**BAĞIMLILIK PAKETLENMELİ.** `winsdk` ne `requirements.txt`'te ne spec'in
`hiddenimports`'undaydı: import hata veriyor, `BILINMIYOR` dönüyor, premium ÖDEYEN
müşteride bile sessizce açılmıyordu. Mevcut bekçiler bunu görmedi çünkü hepsi «şunu
ÇAĞIRMIYORUZ» diye bakıyordu — hiçbiri «şu gerçekten çalışıyor mu» diye sormuyordu.
Bekçi: `test_paketleme.TestStoreKoprusuPaketleniyor`.

**KİLİTLİ SEKME AÇILIR, İÇİ UYDURULMAZ.** Kullanıcı ne kaçırdığını görsün diye sekme
girilebilir ve kendi `ACIKLAMA`'sını gösterir; bulanık ya da sahte rakam GÖSTERİLMEZ
(kural 2). Kilit **iki kapıda** tutulur: boş ekranın CTA'sı ve `_on_getir`.

Sekmenin premium olup olmadığı tek yerde (`domain/lisans.py`); dokuz BASLIK'ın her biri
ya ücretsiz ya premium listesinde olmak zorunda ve bunu `test_lisans.TestBolunme`
sınıyor — listeye yazılmayan yeni bir sekme sessizce bedava dağıtılırdı.

Tanıtım sayfası da aynı kaynaktan sınanır (`test_web`): ücretsiz bir sekme premium
kutusunda görünürse test kırmızıya döner.

---

## Teknik notlar

- **Veritabanını firma kodu seçer**, `CalismaYili` değil. Bir firma DB'si birden çok
  yıl tutabilir (canlıda 20 → 2020-2025, 26 → 2026+). Yıl → firma eşlemesi
  `infra/veritabani.py` kataloğundan gelir; sekmeler `yil_client(cfg, yil)` kullanır,
  `MikroClient(cfg)` kurmaz.
- **Kapanış/açılış fişleri**: 31 Aralık kapanış fişi bütün bakiyeleri sıfırlar,
  1 Ocak açılış fişi geri yükler. Kümülatif bakiye okuyan **her** sorgu ortak
  `_bakiye_kosulu`yu kullanır (mizan, nakit/alacak/borç özeti, GL nakit bakiyesi) —
  aynı eleme üç yere ayrı yazılınca ikisinde vardı birinde yoktu.
- **GL nakit iki AYRI kümedir, karıştırılmaz.** *Bakiye* sorusu («ne kadar nakdim var»)
  `domain/nakit_akis.py: GL_NAKIT_BAKIYE_ANA` → 100/101/102/**103**/108, Bilanço «Nakit
  ve Benzerleri» ile birebir olsun diye 103 dâhil. *Akış* sorusu («hangi fiş nakit
  hareketidir») `infra/mikro_fetch.py: _NAKIT_AKIS_ONEK` → 103 **hariç**, çünkü çek
  yazma anı nakit çıkışı değil; takas edilince 102'den çıkıyor, içeri alınsa aynı ödeme
  iki kez sayılırdı. Bakiye sorusunu akış kümesiyle cevaplamak, Nakit Akış'ın kapanış
  nakdi ile Tahmin'in başlangıç nakdini aynı tarihte ayrıştırıyordu.
- **«Bu banka hesabı kredi mi» TEK kuraldır: `domain/ortak.py: kredi_banka_mi`**
  (`ban_hesap_tip = 1` **veya** 300 öneki **veya** 320 satıcı sınıfı). Niyet
  `gercek_durum_ayarlar.py`de yazılıydı ama üç yerde üç farklı tamlıkta uygulanmıştı.
  Canlıda kredi hesaplarının `ban_hesap_tip`i **1 DEĞİL** — 300.02.* hesapları mevduat
  gibi görünüyor. Tek teste güvenmenin iki bedeli vardı: `nakit_bakiye` 7 kredi
  hesabının net −3.744.328'ini nakde katıyordu (Tahmin krediyi ayrıca taksit taksit
  modellediği için borç İKİ KEZ sayılıyordu), ve **cari akış yolunda** kredi hesabı
  «nakit» sayıldığı için 102→300 kredi ödemesi nakit↔nakit **iç transferi olup tamamen
  eleniyordu** — Nakit Akış'ta kredi ödemesi hiç görünmüyordu. `kredi_odeme_gl` yedeği
  zaten bu belirti için yazılmıştı. SQL karşılığı `infra: _kredi_banka_sql`; GL akış
  yolu etkilenmiyor (karşı hesabı `fis_hesap_kod`'dan alıyor, krediyi 300 önekiyle
  zaten görüyor). `ban_muh_kod` kullanıcı tarafından atandığı için tek test yetmez.
- **Cari nakit ile GL nakit büyük ölçüde çelişebilir ve hangisinin doğru olduğunu
  program BİLMİYOR — ama artık bunu SÖYLÜYOR.** Canlıda cari 25.982.795 ⟷ GL 514.859
  (50 kat), ama aynı veride 120 ve 320 yalnız %5-7 sapıyor. Kod tabanında bir zamanlar
  bunun sebebi «döviz kuru» diye yazılmıştı; o «47 kat» tam bu farkın kendisiydi, yani
  gözlem sebep sanılıp olgu gibi kaydedilmişti. Kur olsaydı alacak/borç da şişerdi.
  `domain/nakit_akis.py: BaslangicNakit.celiski` — kaynak (GL) kullanılmaya devam eder,
  DEĞİŞMEZ; ama iki kaynak bir büyüklük mertebesi (`NAKIT_CELISKI_KAT = 10×`) ayrıştıysa
  Tahmin'de amber not (`celiski_notu`) iki ölçülen rakamı yan yana yazar ve doğrulamayı
  Mikro'daki Banka Hesap Durumu'na yönlendirir — **hangisinin doğru olduğunu iddia
  etmez.** Eşik bakiyenin yüzdesi DEĞİL mertebe farkı: `mutabakat_farki`deki %1 aynı
  verinin iki görünümünü kıyaslayan bir muhasebe kimliğidir, iki BAĞIMSIZ defteri
  kıyaslarken kopyalanamaz — sağlıklı kurulumda normal muhasebeleşme gecikmesi bile
  bakiyenin %1'ini rahat aşar.
  **`--banka` teşhisinde banka ADI güvenilmez** — muhasebeci elle girer: canlıda
  gerçekte Ziraat olan bir hesap «Katılım» diye kaydedilmişti. Ada bakıp hesap türü
  (vadeli/DBS/POS) çıkarmak yasak; tek güvenilir ayrım hesabın hangi TDHP koduna
  bağlandığıdır (`kredi_banka_mi`).
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
/plan-elestirmen <plan>                                 # planı koda+kurallara karşı parçala
```

**Kayda değer bir plan koda dönmeden önce `/plan-elestirmen`'e verilir — kullanıcıya
sorulmadan, otomatik.** (`.claude/skills/plan-elestirmen/`) Eleştirmen kuralların
kopyasını taşımaz, bu dosyayı okur — iki kural kopyası ayrışır ve yanlış olan sessizce
yönlendirmeye devam eder.

Kullanıcının kararı: *«bana sorma artık, her yaptığın önemli şeyi sor eleştirmene.»*
Gerekçesi ölçülü: eleştirmen ilk üç koşuşunda üç gerçek kusur buldu — biri canlıda
177.753 TL'lik yükü 1.089 TL gösteren bir hesap, biri ekranda kendi altındaki rakamla
çelişen bir uyarı, biri ölçülmemiş kazanç için sezgisele bağımlılık.

Teşhis araçları: `stok_diag_cli.py` (`--kolonlar`, `--maliyet`, `--fatura`),
`bilanco_cli.py --teshis`, `cari_diag_cli.py`.

## Paketleme (MSIX / Microsoft Store)

**KURULUM DİZİNİNE ÇALIŞMA ANINDA YAZILMAZ.** MSIX'te uygulama
`C:\Program Files\WindowsApps\…` altına kurulur ve orası yönetici için bile
salt-okunurdur. Bu hata geliştirmede ve tek-dosya .exe'de **hiç görünmez**: PyInstaller
onefile'da `__file__` geçici çıkarma klasörünü gösterir, orası yazılabilir. Yalnız
mağaza paketinde ortaya çıkar. Açılır kutu oku (`chevron-down-teal.png`) yoksa uygulama
kendi çiziyordu; MSIX'te `QPixmap.save()` **istisna atmadan `False` döner**, QSS var
olmayan dosyaya işaret eder ve ok büsbütün kaybolurdu. Statik asset'ler derleme anında
üretilir (`assets/generate_icons.py`), uygulama yalnız okur. Yazılabilir tek yer
`%APPDATA%` — `infra/config.py: config_dir()`.
Bekçi: `test_paketleme.TestKurulumDiziniSaltOkunur` — `Path(__file__)`'dan türeyen
isimlere yazan çağrıları AST'den bulur.

**MAĞAZA KİMLİĞİ PARTNER CENTER'DAN GELİR, UYDURULMAZ.** `Name` / `Publisher` birebir
eşleşmezse yükleme reddedilir ve sebebi manifest'te **tek karakterlik** bir farktır
(`Mikrapor` ≠ `MikRapor`). Değerler gizli değildir (PFN ve Store ID zaten açık),
repoda dururlar ama bekçiyle sabitlenir.

**MANİFEST ÜÇÜNCÜ SÜRÜM KAYNAĞI OLMAZ.** `pyproject.toml` ↔ `infra/surum.py` ikilisini
`test_surum.py` koruyor. Manifest'teki `Version="0.0.0.0"` bilerek geçersiz bir yer
tutucudur; gerçek sürüm derlemede `infra/surum.py`'den yazılır. MSIX sürümü dört
parçalıdır ve son parçayı Store kendine ayırdığı için 0 kalır.

**TEK SPEC, İKİ BİÇİM.** `MIKRAPOR_ONEDIR=1` → MSIX gövdesi (onedir), yoksa doğrudan
indirilen tek dosya (onefile). MSIX'e onefile koymak her açılışta paketi geçici klasöre
açtırır. İkinci bir spec dosyası açmak asset listesinin sessizce ayrışması demekti —
tam da `test_paketleme`'nin var olma sebebi.

**İKİ ARTEFAKT, İKİ AMAÇ — KARIŞTIRILMAZ.**

| dosya | imza | kim kurar |
|---|---|---|
| `…-store.msix` | **yok** — Microsoft imzalar | Partner Center'a yüklenir |
| `…-yanyukleme.msix` | kendinden imzalı | sertifika Trusted Root'a eklenmeden **kurulmaz** |

Tek dosya üretip ikisine birden koşmak, indiren kullanıcının «yayıncıya güvenilmiyor»
duvarına çarpması demekti.

**WACK ÖNDEN KOŞAR.** Store zaten `appcert.exe` koşturuyor; önden koşmazsak geri
bildirim günler sonra Partner Center üzerinden gelir. 600+ testi olan bir kod tabanında
paketin kendisini test etmemek açıklanamaz.

**Etiket en sona.** Workflow önce `workflow_dispatch` ile elle koşturulur, çıktı
doğrulanır, sonra `v*` etiketi kesilir. Etiketi bozuk artefakta bağlamak geri alınamaz.

## Dal ve deploy

Geliştirme `claude/microproject-code-review-b4g4jy` dalında. Kullanıcı **"deploy"**
dediğinde: push → PR (base `master`) → merge. Başka dala push yok.
