# GÖZCÜ·AI — Donanım ve Gereksinimler

Görüntü işleme kalite kontrolünü masaüstünde denemekten üretim hattına kurmaya kadar gereken donanım.

> **Fiyatlar yaklaşıktır** ve 2026'daki bellek kaynaklı fiyat artışlarından etkilenmiştir. Satın almadan önce güncel teklif alın.

## 1 · Görüntü işlemede asıl donanım: ışık ve sabitlik

GÖZCÜ'nün doğruluğunu bilgisayarın gücünden çok **görüntünün kalitesi** belirler. Üç kural:

1. **Kamera sabit** ve parçaya **tam tepeden, dik** bakmalı.
2. **Işık sabit ve eşit** olmalı: gün ışığına, tavan lambasına bağımlı olmamalı; parlama yapmamalı.
3. **Zemin sade ve parçayla kontrastlı** olmalı (açık parçaya koyu, koyu parçaya açık zemin).

Bu üçü sağlanmazsa sistem karar uydurmaz; görüntüyü ŞÜPHELİ işaretleyip nedenini söyler.

## 2 · Kademe 0 — Bilgisayarda deneme (maliyet: 0)

| Gereksinim | Asgari |
|---|---|
| İşletim sistemi | Windows 10/11, macOS 12+, güncel Linux |
| Python | 3.9 veya üstü |
| Bellek | 4 GB |
| Kamera | Gerekmez (fotoğrafla çalışır); canlı mod için dizüstü kamerası ya da USB kamera |
| İnternet | Yalnız ilk kurulumda (OpenCV ve NumPy indirilir) |

Telefonla çekilmiş fotoğraflar `fotograflar/` klasörüne atılarak tüm akış denenebilir.

## 3 · Kademe A — Pilot istasyon (masa üstü)

| Bileşen | Önerilen | Yaklaşık fiyat |
|---|---|---|
| Bilgisayar | Mevcut bir PC ya da Raspberry Pi 5 (4 GB) | 0 / 105 USD |
| Pi aksesuarı | Kasa + fan, 27 W adaptör, microSD | 40–70 USD |
| Kamera | 1080p USB kamera (manuel odak tercih) ya da Raspberry Pi Camera Module 3 | 25–70 USD |
| Sehpa | Kamerayı tepeden dik tutan kopya sehpası / masa kolu | 15–40 USD |
| Aydınlatma | Halka LED ya da iki yandan difüzörlü LED panel | 15–50 USD |
| Zemin | Mat siyah ve mat beyaz karton / plaka | 5 USD |

**Pilot toplam: mevcut PC ile ~60–170 USD; Raspberry Pi ile ~200–340 USD.**

Ölçülen hız: bir parça masaüstü bilgisayarda ~60–90 ms'de incelenir; Raspberry Pi 5'te birkaç yüz milisaniye beklenir (çoğu enjeksiyon çevrimi için yeterli). Zorlu sahnelerde (dokulu zemin) ek stratejiler devreye girdiğinden süre uzar.

## 4 · Kademe B — Hat üstü endüstriyel istasyon

| Bileşen | Önerilen / eşdeğer | Yaklaşık fiyat |
|---|---|---|
| Endüstriyel bilgisayar | Fansız IPC ya da endüstriyel mini PC | 300–700 USD |
| Endüstriyel kamera | GigE / USB3 makine görüş kamerası (global shutter) + sabit odaklı lens | 300–900 USD |
| Aydınlatma | Kubbe (dome) ya da arka aydınlatma, kameraya senkron | 150–600 USD |
| Mekanik | Kamera braketi, ışık muhafazası, parçanın oturacağı sabit yuva | değişken |
| Tetik | Parça varlık sensörü ya da PLC sinyali (isteğe bağlı) | 30–150 USD |

**Endüstriyel toplam: istasyon başına yaklaşık 900–2.500 USD.**

Global shutter kamera, banttaki hareketli parçada bulanıklığı önler; kubbe aydınlatma parlak plastik yüzeylerdeki yansımayı bastırır.

## 5 · Parça kapsamı

| Parça | Uygunluk |
|---|---|
| Dairesel (kapak, pul, dişli gövdesi, konnektör tabanı) | Tasarlandığı alan |
| Merkez delikli / deliksiz | Her ikisi (kalibrasyon kendisi bulur) |
| Yarı saydam | Altına mat zıt renkli zemin ile |
| Serbest biçimli parçalar | Bu sürümde değil — derin öğrenme anomali modeli gerekir |

## 6 · Dürüst notlar

- Motor sentetik verilerde, örnek fotoğraflarda ve zorlu sahne simülasyonlarında (ahşap zemin, ışık kayması, eğik çekim) otomatik testlerle doğrulanmıştır. **Gerçek bir üretim hattında henüz çalıştırılmamıştır.** İlk sahada eşiklerin (politika ve uygunluk eşiği) gerçek parçalarla ayarlanması beklenmelidir.
- Canlı kamera modu kod ve tetikleyici mantığı olarak test edilmiştir; farklı kamera modelleriyle sahada denenmelidir.

## Kaynaklar

- Raspberry Pi fiyat artışları (2 Şubat 2026): https://raspberrypi.com/news/more-memory-driven-price-rises
- Raspberry Pi 5 güncel fiyat listesi (Nisan 2026): https://www.notebookcheck.net/Raspberry-Pi-confirms-new-pricing-for-popular-single-board-computers.1264226.0.html
