# GÖZCÜ·AI — Güvenlik ve Kalite Güvencesi

Kalite sorumlusu ve işletmeci için: GÖZCÜ'nün kararına ne zaman güvenilir, yanlış karar riski nasıl yönetilir.

> **Tek cümle:** GÖZCÜ emin olamadığı parçaya SAĞLAM demez; ya FİRE der ya da ŞÜPHELİ deyip insana bırakır.

## 1 · İki tür hata ve öncelik

| Hata | Sonuç | GÖZCÜ'nün tutumu |
|---|---|---|
| **Kaçak** — kusurlu parçaya SAĞLAM | Müşteriye kusurlu ürün gider | En ciddi hata kabul edilir; her tasarım kararı bunu azaltmaya yöneliktir |
| **Yanlış red** — sağlam parçaya FİRE | Malzeme ve zaman kaybı | Politikalar ve ŞÜPHELİ ile yönetilir |

## 2 · Kaçağa karşı katmanlar

1. **Kalite kapıları:** bulanık, karanlık, parlamalı, kesik, çok yatık, çok nesneli ya da kenarı ölçülemeyen görüntüye karar verilmez.
2. **Sınırda bulgu:** eşiği kılpayı aşan zayıf bulgu ve eşiğe tehlikeli yakın ölçümler ŞÜPHELİ olur — sessizce SAĞLAM sayılmaz.
3. **Bağlayıcı öz-test:** kalibrasyon kendi altın numunelerini SAĞLAM bulamazsa hiçbir parça SAĞLAM onayı alamaz.
4. **Tutarlılık denetimi:** farklı parçalar altın numuneye karışırsa kalibrasyon reddedilir ve kaydedilmez.
5. **Uygunluk eşiği:** küçük kusurlar toplamda skoru eşiğin altına düşürürse parça FİRE olur.

## 3 · Politikaların sorumlu kullanımı

- Politika ile tolere edilen kusur **kaybolmaz**: görüntüde gri kutu, raporda "politika: tolere edildi" notu, geçmişte kayıt.
- Politika değişikliği bir **kalite kararıdır**; müşteri şartnamesine göre kalite sorumlusu tarafından verilmeli ve tarihlenmelidir.
- Eksik dolum ve delik gibi işlev kusurlarını tolere etmek önerilmez.

## 4 · Veri bütünlüğü

- Aynı fotoğraf (adı değişse bile) kalıcı sayaçlara ve geçmişe **bir kez** girer.
- Ayar ve sayaç dosyaları atomik yazılır; elektrik kesintisinde yarım dosya kalmaz. Bozuk dosya tespit edilirse yedeklenir ve kullanıcı uyarılır.
- Simülasyon ve örnek çalıştırmaları üretim sayaçlarına ve geçmişe **yazılmaz**.

## 5 · Sahaya çıkış öncesi doğrulama

1. **Kalibrasyon:** en az 3 altın numune; öz-test geçmeli.
2. **Kör test:** kalite biriminin önceden sınıflandırdığı en az 200 parça (bilinen kusurlularla birlikte) incelenir. Kaçak sayısı **sıfır** olmalı; yanlış red ve ŞÜPHELİ oranları kaydedilir.
3. **Eşik kararı:** politika ve uygunluk eşiği kör test sonucuna göre kalite sorumlusunca belirlenir.
4. **Periyodik kontrol:** her vardiya başında altın numune bir kez incelenir; SAĞLAM çıkmazsa (ışık, kamera kaydı) üretimde kullanılmaz.
5. **ŞÜPHELİ akışı:** ŞÜPHELİ parçaların insan kontrolüne gideceği fiziksel bir yer ve sorumlu kişi belirlenir.

## 6 · İş güvenliği

- GÖZCÜ bu sürümde hiçbir makineyi, ayırıcıyı ya da aktüatörü **sürmez**; yalnız görüntü inceler ve rapor üretir.
- Hat üstü otomatik ayırma (yol haritası) eklendiğinde ret sinyali **PLC üzerinden** verilmeli, makine emniyet devrelerine dokunulmamalı ve devreye almadan önce makine emniyeti değerlendirmesi yapılmalıdır.
- Canlı kamera modunda parçayı yerleştiren operatörün eli makine hareket alanında olmamalıdır.

## 7 · Sorumluluk sınırı

GÖZCÜ bir **karar destek** aracıdır. Son kalite kararından ve müşteriye giden ürünün uygunluğundan işletmenin kalite sistemi sorumludur. GÖZCÜ'nün kararları, belirlenen örnekleme ve doğrulama prosedürleriyle birlikte kullanılmalıdır.
