"""
Demo defteri — MAĞAZA PAKETİNE GİRMEZ.

Bu paket yalnız geliştirici makinesinde, mağaza ekran görüntüsü almak ve arayüzü
Mikro sunucusu olmadan gezmek için vardır. Kurgu bir firmanın defterini üretir ve
uygulamanın veri çekme fonksiyonlarını çalışma anında onunla değiştirir.

NEDEN UYGULAMA KODUNDA KANCA YOK: `ui/app.py` içine «ortam değişkeni varsa demoyu
yükle» satırı koymak denenebilirdi. Konmadı, çünkü PyInstaller koşullu import'u da
statik olarak izler — o satır `demo/` paketini mağazaya giden pakete SOKARDI ve
kurgu rakamların son kullanıcıya ulaşmamasını `excludes` listesinin doğru yazılmış
olmasına bağlardık. Bunun yerine demo KENDİ giriş noktasından açılır
(`python -m demo.calistir`); uygulama kodunda demoya ait tek satır yoktur, dolayısıyla
paketleme tarafında unutulacak bir şey de yoktur.

KURGU RAKAM GERÇEK SANILMAZ: defterdeki firma adı «ÖRNEK SANAYİ VE TİCARET A.Ş.»dir
ve her ekranın başlığında, her PDF'in antetinde görünür. Ekran görüntüsü kendini
kurgu ilan eder.

RAKAMLARI DEMO HESAPLAMAZ: burası yalnız HAM SATIR üretir (mizan satırı, stok
hareketi, cari açık kalem, GL fişi). Bilanço dengesi, gelir tablosu mutabakatı,
açılış + giriş − çıkış = kapanış ilişkilerini gerçek `domain/` motorları hesaplar.
Böylece ekranda tutarsız bir tablo çıkarsa o gerçek bir kusurdur, demonun süsü değil.
"""
