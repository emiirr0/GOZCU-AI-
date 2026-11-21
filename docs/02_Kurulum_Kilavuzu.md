# GÖZCÜ·AI — Kurulum ve Kullanım Kılavuzu

Kurulumdan kendi parçanla ilk muayeneye, oradan canlı kameraya kadar adım adım.

## 1 · Kurulum (Windows)

1. https://www.python.org/downloads/ adresinden Python 3.9 veya üstünü kurun. **İlk ekranda "Add Python to PATH" kutusunu işaretleyin.**
2. Depoyu indirip (GitHub: **Code → Download ZIP**) bir klasöre çıkarın.
3. **`1_KURULUM.bat`** — klasörün içine ayrı bir Python ortamı (`.venv`) kurar ve OpenCV ile NumPy'yi indirir. Sonunda kurulum kontrolünü kendisi çalıştırır; tüm satırlar `[ OK ]` olmalı.

Bilgisayardaki diğer Python programlarıyla çakışma olmaz; silmek için klasörü silmek yeter.

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./baslat.sh kontrol
```

### Raspberry Pi

```bash
sudo apt update && sudo apt install -y python3-opencv python3-numpy git
git clone <depo-adresi> ~/gozcu-ai && cd ~/gozcu-ai
python3 -m gozcu kontrol
```

## 2 · Önce örneklerle dene

**`0_ORNEK_DENE.bat`** — depodaki örnek altın numune ve kontrol fotoğraflarıyla kalibrasyonu ve muayeneyi çalıştırır, raporu tarayıcıda açar. **Senin klasörlerine, ayarlarına ve sayaçlarına dokunmaz** (her şey `cikti/ornek/` altında olur).

**`2_DEMO.bat`** — 20 sentetik parçada motorun doğruluğunu gösterir (beklenen: 20/20).

## 3 · Kendi parçanla — adım adım

### 3.1 · Altın numune

`altin_numune/` klasörüne **yalnız kendi sağlam parçanın** 2–3 fotoğrafını koy.

- Parça **elde değil, zeminde**; kadrajın ortasında, tek başına.
- **Tam tepeden**, dik açıyla.
- Sade, kontrastlı zemin; **flaşsız**, eşit ışık.
- Yarı saydam parçanın altına mat, zıt renkli bir karton.
- **Farklı parçaları karıştırma.** Karışırsa kalibrasyon "ALTIN NUMUNELER BİRBİRİNE BENZEMİYOR" der ve kaydetmez.

### 3.2 · Kalibrasyon

**`3_KALIBRE.bat`**. Sistem çapı, deliği, kenar pürüzlülüğünü ve yüzey gürültüsünü ölçüp eşikleri öğrenir, sonra altın numuneleri kendi kalibrasyonuyla inceler (**öz-test**).

> **"Öz-test: … tamamı SAĞLAM çıktı" yazısını görmeden devam etme.** Öz-test geçmezse sistem hiçbir parçaya SAĞLAM onayı vermez; fotoğrafları/ışığı düzeltip yeniden kalibre et.

### 3.3 · Muayene

Kontrol edilecek fotoğrafları **altın numuneyle aynı düzende** çekip `fotograflar/` klasörüne at, **`4_FOTO_INCELE.bat`** çalıştır. Rapor tarayıcıda açılır; işaretli görüntüler `cikti/` altındadır.

Aynı fotoğrafı tekrar incelemek kalıcı sayaçları **şişirmez**: daha önce sayılan fotoğraflar (adı değişmiş olsa bile, içerik imzasından tanınır) toplamlara yeniden eklenmez.

### 3.4 · Fire raporu

**`5_FIRE_RAPORU.bat`** — tüm geçmişten günlük kırılımlı HTML rapor ve Excel'de açılan CSV üretir.

## 4 · Kararları okumak

| Karar | Anlamı | Ne yapılır |
|---|---|---|
| SAĞLAM | Tüm kontroller net geçti | — |
| FİRE | Eşiği net aşan kusur ya da uygunluk eşiğinin altında skor | Parçayı ayır; tür ve yer raporda |
| ŞÜPHELİ | Karar verilemedi: görüntü kötü ya da bulgu sınırda | Raporda yazan nedeni düzelt ya da parçayı insan kontrol etsin |

Parçaların yarısından fazlası ŞÜPHELİ çıkıyorsa sorun genelde parçada değil **kurulumdadır** (ışık, odak, kadraj, zemin); program bunu ayrıca uyarır.

## 5 · Politikalar ve eşik

```bash
python -m gozcu politika                  # mevcut ayarları göster
python -m gozcu politika cizik yok_say    # çizikleri karara katma (raporda gri görünür)
python -m gozcu politika cizik hafif      # yalnız hafif çizikleri tolere et
python -m gozcu politika capak 40         # 0–100 ince ayar
python -m gozcu politika esik 95          # skor %95 altıysa FİRE
python -m gozcu politika hepsi sifir      # hepsini sıfır toleransa döndür
```

Windows'ta bu komutları proje klasöründe açılan komut isteminde `.venv\Scripts\python -m gozcu ...` olarak çalıştırın.

## 6 · Canlı kamera

**`7_KAMERA_OTOMATIK.bat`** (ya da `python -m gozcu canli 0 otomatik`):

1. Kamera penceresi açılınca sahnede parça yokken **B** tuşuna bas (boş sahne tanıtılır).
2. Parçayı koy, elini çek. Görüntü durulunca sistem **bir kez** inceler ve sonucu gösterir.
3. Parçayı al, yenisini koy. **Q** ile çık.

Elle mod: `python -m gozcu canli` — **SPACE** ile incele. Başka kamera: `canli 1`.

Kamera açılmazsa kamerayı kullanan programı (Zoom, Teams, Kamera uygulaması) kapat. Windows'ta sistem birden çok kamera arka ucunu kendisi dener.

## 7 · Sıfırlama

```bash
python -m gozcu sifirla           # kalıcı sayaçlar (geçmiş arşivi korunur)
python -m gozcu sifirla gecmis    # geçmiş arşivi de silinir
```

## 8 · USTA·AI ile birleştirme

USTA'nın `veri/ayarlar.json` dosyasına GÖZCÜ klasörünü yaz: `"gozcu": {"klasor": "C:\\...\\gozcu-ai"}`. USTA dosyaları yalnız okur.

## 9 · Sorun giderme

| Belirti | Çözüm |
|---|---|
| "Gerekli kütüphane eksik" | `1_KURULUM.bat` |
| Fotoğraf "okunamadı" | OneDrive: klasöre sağ tık → "Her zaman bu cihazda tut" |
| Kalibrasyon "parça bulunamadı" | Kontrast: açık parçaya koyu zemin; parça ortada ve tamamen kadrajda |
| "Birbirine benzemiyor" | `altin_numune/` içinde yalnız aynı tip sağlam parça bırak |
| Hep ŞÜPHELİ | Rapordaki nedene bak (bulanık, karanlık, parlama, kesik, yatık açı) |
| Kamera penceresi açılmıyor | `pip uninstall opencv-python-headless`, sonra `pip install opencv-python` |
| Genel tanılama | `KONTROL.bat` |
