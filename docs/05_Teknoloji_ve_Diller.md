# GÖZCÜ·AI — Teknoloji ve Diller

## 1 · Özet

| Katman | Teknoloji | Neden |
|---|---|---|
| Dil | Python 3.9+ | Görüntü işlemenin standart dili; Raspberry Pi'de de çalışır |
| Görüntü işleme | OpenCV (4.5.5+ ve 5.x) | Olgun, hızlı, her platformda paketli |
| Sayısal hesap | NumPy | OpenCV'nin veri yapısı |
| Raporlar | Tek dosyalık HTML (görseller gömülü) + CSV (UTF-8 BOM, `;`) | Tarayıcıda açılır, e-postayla gönderilir; Türkçe Excel CSV'yi doğru açar |
| Kalıcılık | JSON + JSON Lines | İnsan okuyabilir, bozulmaya dayanıklı, ek yazılım gerektirmez |
| Kurulum | Proje içi sanal ortam (`.venv`) | Bilgisayardaki diğer Python paketleriyle çakışmaz |
| Test | pytest | 38 test, sentetik ve zorlu sahne üreteçleriyle |
| Sürekli test | GitHub Actions | Windows/macOS/Linux × Python 3.9/3.11/3.13 |

## 2 · Neden klasik görüntü işleme (henüz derin öğrenme değil)?

- **Veri gerektirmez:** bir derin öğrenme modeli yüzlerce etiketli kusurlu parça ister; GÖZCÜ 2–3 sağlam parça fotoğrafıyla kalibre olur.
- **Açıklanabilir:** her karar ölçülebilir bir nedenle gelir ("kontur 29 piksel dışa taşmış, saat 12 yönü"). Kalite biriminin itirazına cevap verilebilir.
- **Hafif:** ekran kartı gerektirmez; Raspberry Pi'de çalışır.
- **Sınırı:** serbest biçimli parçalar ve çok ince dokusal kusurlar. Dedektör arayüzü (`Defect` nesnesi) derin öğrenme tabanlı bir anomali dedektörünün sonradan aynı hatta eklenmesine hazırdır.

## 3 · Kod düzeni

- `gozcu/` tek pakettir; `python -m gozcu` ile çalışır, `pip install .` ile `gozcu` komutu olarak da kurulabilir.
- Dosya yolları tek yerde (`calisma.py`) toplanır; tüm komutlar `--klasor` ile başka bir çalışma klasöründe çalışabilir.
- Modül adları ASCII, kullanıcıya görünen metinler Türkçe.

## 4 · Sürüm uyumluluğu

| Bileşen | Desteklenen |
|---|---|
| Python | 3.9 – 3.13 |
| OpenCV | 4.5.5+ ve 5.x (4.14 ve 5.0 ile doğrulandı) |
| NumPy | 1.21+ ve 2.x |
| İşletim sistemi | Windows 10/11, macOS, Linux, Raspberry Pi OS |
