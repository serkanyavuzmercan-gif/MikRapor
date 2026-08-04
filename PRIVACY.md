# MikRapor — Gizlilik Politikası

**Son güncelleme:** 4 Ağustos 2026

## Özet

MikRapor, kendi bilgisayarınızda çalışan bir masaüstü uygulamasıdır. Mali verileriniz
kendi Mikro ERP sisteminizden okunur ve bilgisayarınızda kalır. MikRapor'un bir sunucusu
yoktur; verilerinizi toplamıyor, saklamıyor, göremiyoruz.

Verinin bilgisayarınızdan çıktığı tek yer, sizin açıkça başlattığınız «Yapay Zekâ Yorumu»
işlemidir.

## 1. Topladığımız veriler

Hiçbiri. MikRapor:

- hesap açmanızı istemez, kayıt tutmaz;
- kullanım istatistiği, telemetri, çökme raporu ya da analitik göndermez;
- reklam ağı veya izleyici içermez.

## 2. Bilgisayarınızda saklananlar

Ayarlarınız yalnız kendi kullanıcı klasörünüzde tutulur:
`%APPDATA%\MikRapor\config.json`

İçinde Mikro sunucu adresi, firma kodu, kullanıcı kodu, rapor tercihleri ve — girdiyseniz —
yapay zekâ API anahtarınız bulunur.

Mikro şifreniz ve API anahtarınız düz metin olarak yazılmaz; Windows'un DPAPI şifrelemesiyle
korunur, yalnız aynı Windows kullanıcısı çözebilir. Dosyayı istediğiniz zaman silebilirsiniz;
uygulama bilgileri yeniden sorar.

Ürettiğiniz PDF ve CSV raporları yalnız sizin seçtiğiniz klasöre yazılır.

## 3. Mali verileriniz

MikRapor kendi ağınızdaki Mikro ERP sistemine bağlanır ve raporu bilgisayarınızda hesaplar.
Bu veri hiçbir aşamada bize ya da üçüncü bir tarafa iletilmez.

## 4. Yapay Zekâ Yorumu — tek dış çıkış

Bu sekme, seçtiğiniz dönemin rapor içeriğini bir yapay zekâ sağlayıcısına gönderip yorum
ister. **İki koşul birlikte sağlanmadan hiçbir ağ çağrısı yapılmaz:**

1. kendi API anahtarınızı girmiş olmanız,
2. ekrandaki onay kutusunu işaretlemeniz.

**Gönderilen veri**, ekranda gördüğünüz rapor içeriğidir — tutarlar, oranlar ve cari
ünvanları dâhil. Ekranda olmayan bir şey gönderilmez.

**Nereye gider:** sizin seçtiğiniz sağlayıcıya — Anthropic, OpenAI, Google, DeepSeek, xAI
ya da girdiğiniz özel adres. İstek doğrudan sizin bilgisayarınızdan o sağlayıcıya gider;
arada MikRapor'a ait bir sunucu yoktur. Verinin sağlayıcıda nasıl işlendiği o sağlayıcının
gizlilik politikasına tabidir ve anahtar sizin olduğu için sizin hesabınızın koşulları
geçerlidir.

Onay kutusunu kaldırdığınızda ya da anahtarı sildiğinizde bu yol tamamen kapanır;
uygulamanın geri kalanı etkilenmez.

## 5. Lisans doğrulaması

Premium eklentisine sahip olup olmadığınız, Windows'un kendi Microsoft Store servisine
sorularak öğrenilir. Bu sorguda hiçbir mali veriniz yer almaz, yalnız lisans bilgisi okunur.
Microsoft hesabınız ve satın alma işlemleriniz Microsoft'un gizlilik koşullarına tabidir.

## 6. Kişisel veriler (KVKK)

Mikro veritabanınızdaki cari kayıtlar kişisel veri içerebilir (örneğin şahıs firmaları).
Bu verilerin veri sorumlusu, veritabanının sahibi olan firmanızdır. MikRapor bu verileri
bize aktarmadığı için veri işleyen sıfatını taşımayız. Tek istisna 4. maddede tarif edilen
ve sizin başlattığınız gönderimdir; orada da alıcı, doğrudan sözleşme kurduğunuz yapay zekâ
sağlayıcısıdır.

## 7. Çocuklar

MikRapor bir işletme raporlama aracıdır; çocuklara yönelik değildir ve yaş verisi toplamaz.

## 8. Değişiklikler

Bu politika değişirse güncel metin uygulamanın Microsoft Store sayfasında yayımlanır ve
yukarıdaki tarih güncellenir.

## 9. İletişim

Hidroteknik
E-posta: mikrapor@hidroteknik.com.tr
