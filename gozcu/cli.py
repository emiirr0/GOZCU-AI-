"""GÖZCÜ·AI komut satırı.

  python -m gozcu demo              sentetik partide motoru kanıtla
  python -m gozcu ornek             hazır örnek fotoğraflarla tam akışı dene (klasörlerine dokunmaz)
  python -m gozcu kalibre           altin_numune/ içindeki SAĞLAM parçadan öğren
  python -m gozcu incele            fotograflar/ içindeki fotoğrafları muayene et
  python -m gozcu canli [N] [otomatik]   kamera ile canlı muayene (N = kamera numarası)
  python -m gozcu simulasyon [adet] sanal bant demosu (donanımsız)
  python -m gozcu rapor             geçmişten fire raporu (HTML + Excel CSV)
  python -m gozcu politika ...      kusur toleransları ve uygunluk eşiği
  python -m gozcu sifirla [gecmis]  kalıcı sayaçları (ve istenirse geçmişi) sıfırla
  python -m gozcu kontrol           kurulum tanılaması — sorun yaşarsan önce bunu çalıştır

Tüm komutlar --klasor <yol> ile başka bir çalışma klasöründe çalışabilir.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import List

from . import VERSION, fire_report, report_html
from .calibrate import calibrate
from .calisma import Calisma, dosya_imzasi, gorselleri_listele
from .config import DEFAULT_POLICIES, POLICY_PRESETS, InspectionConfig
from .io_utils import imread_tr, imwrite_tr
from .pipeline import (KIND_LABELS, Counters, InspectionPipeline, annotate,
                       ascii_metin, write_batch_report)

ORNEKLER = Path(__file__).resolve().parent / "ornekler"
ASGARI_PY = (3, 9)


def _dosya_adi(ad: str, karar: str) -> str:
    return f"{ad}__{ascii_metin(karar)}.png"


def _konsol_utf8() -> None:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ── komutlar ─────────────────────────────────────────────────────────
def cmd_demo(c: Calisma, a) -> int:
    """Sentetik partide uçtan uca kanıt: kusurlar bilinerek eklenir, motor bilmez."""
    from .synth import make_batch
    out = c.cikti / "demo"
    out.mkdir(parents=True, exist_ok=True)
    spec = [("good", 8), ("capak", 2), ("kirik", 2), ("cizik", 2),
            ("leke", 2), ("eksik_dolum", 2), ("karma", 2)]
    pipe = InspectionPipeline(InspectionConfig())   # demo hep varsayılan referansla
    sayac, sonuclar, isaretli, dogru = Counters(), [], [], 0
    parti = make_batch(spec)
    for ad, img, eklenen in parti:
        r = pipe.inspect(img, ad)
        sayac.add(r)
        sonuclar.append(r)
        ann = annotate(r.normalized_image, r)
        isaretli.append(ann)
        imwrite_tr(str(out / _dosya_adi(ad, r.verdict)), ann)
        dogru += (len(eklenen) > 0) != r.ok
    write_batch_report(sonuclar, sayac, str(out / "parti_raporu.json"), str(out / "parti_raporu.txt"))
    report_html.render(sonuclar, sayac, isaretli, str(out / "rapor.html"), "sentetik doğrulama partisi")
    print(sayac.summary_tr())
    print(f"Doğruluk: {dogru}/{len(parti)} (%{dogru / len(parti) * 100:.0f})")
    print(f"Rapor: {out / 'rapor.html'}")
    return 0 if dogru == len(parti) else 1


def cmd_kalibre(c: Calisma, a) -> int:
    c.hazirla()
    mevcut = InspectionConfig.load(c.ayarlar)
    cfg = InspectionConfig(policies=dict(mevcut.policies), min_score=mevcut.min_score)
    ok, msg = calibrate(c.altin, cfg, ayar_yolu=c.ayarlar)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok and cfg.selftest_ok else 1


def _incele(c: Calisma, dosyalar: List[Path], cfg: InspectionConfig, kalici: bool) -> Counters:
    pipe = InspectionPipeline(cfg)
    parti = Counters()
    toplam, imzalar = c.sayac_oku() if kalici else (Counters(), set())
    sonuclar, isaretli, tekrar = [], [], 0
    for f in dosyalar:
        img = imread_tr(str(f))
        if img is None:
            print(f"  atlandı (okunamadı): {f.name} — dosya bozuk olabilir ya da OneDrive "
                  "henüz indirmemiş (sağ tık → 'Her zaman bu cihazda tut')")
            continue
        r = pipe.inspect(img, f.stem)
        parti.add(r)
        if kalici:
            imza = dosya_imzasi(f)
            if imza in imzalar:
                tekrar += 1
            else:
                imzalar.add(imza)
                toplam.add(r)
                fire_report.append_history(str(c.gecmis), r)
        sonuclar.append(r)
        ann = annotate(r.normalized_image, r)
        isaretli.append(ann)
        imwrite_tr(str(c.cikti / _dosya_adi(f.stem, r.verdict)), ann)
        print(f"  [{f.name}] {r.verdict} · %{r.score:.0f}"
              + ("" if not r.reasons else "  <- " + "; ".join(r.reasons)))
    if kalici:
        c.sayac_yaz(toplam, imzalar)
    write_batch_report(sonuclar, parti, str(c.cikti / "parti_raporu.json"), str(c.cikti / "parti_raporu.txt"))
    not_ = ("kalibre edilmiş" if cfg.calibrated else "varsayılan ayarlar")
    if kalici:
        not_ += f" · kalıcı toplam: {toplam.total} parça, fire %{toplam.scrap_rate:.1f}"
    report_html.render(sonuclar, parti, isaretli, str(c.cikti / "rapor.html"), not_)
    print()
    if parti.total and parti.suspect / parti.total > 0.5:
        print("⚠ Parçaların yarısından fazlası ŞÜPHELİ — bu genelde parça değil KURULUM sorunudur:")
        print("  ışık/odak/kadraj/zemin kontrol et, altın numuneyi aynı düzende çekip yeniden kalibre et.")
    if tekrar:
        print(f"ℹ {tekrar} fotoğraf daha önce sayılmıştı; kalıcı toplamlara TEKRAR eklenmedi.")
    print("Bu koşu      →", parti.summary_tr().splitlines()[0])
    if kalici:
        print("Kalıcı toplam →", toplam.summary_tr().splitlines()[0])
    print(f"Rapor: {c.cikti / 'rapor.html'}  (çift tıkla, tarayıcıda açılır)")
    return parti


def cmd_incele(c: Calisma, a) -> int:
    c.hazirla()
    dosyalar = gorselleri_listele(c.fotolar)
    if not dosyalar:
        print(f"{c.fotolar} klasörü boş. Kontrol edilecek parça fotoğraflarını oraya koyup "
              "tekrar çalıştır.")
        return 1
    cfg = InspectionConfig.load(c.ayarlar)
    if not cfg.calibrated:
        print("Uyarı: kalibrasyon yapılmamış — demo referansı kullanılıyor ve büyük olasılıkla "
              "SENİN parçana uymaz. Önce: python -m gozcu kalibre\n")
    elif not cfg.selftest_ok:
        print("Uyarı: son kalibrasyonun öz-testi geçmedi — hiçbir parça SAĞLAM onayı almayacak.\n")
    _incele(c, dosyalar, cfg, kalici=True)
    return 0


def cmd_ornek(c: Calisma, a) -> int:
    """Hazır örneklerle tam akış — senin altin_numune/ ve fotograflar/ klasörlerine,
    ayarlarına ve sayaçlarına DOKUNMAZ."""
    hedef = Calisma(c.cikti / "ornek")
    if hedef.kok.exists():
        shutil.rmtree(hedef.kok)
    hedef.hazirla()
    for kaynak, klasor in ((ORNEKLER / "altin", hedef.altin), (ORNEKLER / "kontrol", hedef.fotolar)):
        for f in gorselleri_listele(kaynak):
            shutil.copy2(f, klasor / f.name)
    print("1) Kalibrasyon (örnek altın numuneler):")
    cfg = InspectionConfig()
    ok, msg = calibrate(hedef.altin, cfg, ayar_yolu=hedef.ayarlar)
    print(("   ✓ " if ok else "   ✗ ") + msg.replace("\n", "\n   "))
    if not ok:
        return 1
    print("\n2) Muayene (örnek kontrol fotoğrafları):")
    _incele(hedef, gorselleri_listele(hedef.fotolar), cfg, kalici=False)
    print("\nKendi parçan için: örnekleri değil, KENDİ sağlam parçanın fotoğraflarını "
          f"{c.altin} klasörüne koy.")
    return 0


def _pencere_acik(ad: str) -> bool:
    import cv2
    try:
        return cv2.getWindowProperty(ad, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False


def _kamera_ac(no: int):
    import cv2
    denemeler = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if platform.system() == "Windows" else [cv2.CAP_ANY]
    for arka in denemeler:
        cap = cv2.VideoCapture(no, arka)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                return cap
        cap.release()
    return None


def cmd_canli(c: Calisma, a) -> int:
    import cv2
    from .live import AutoTrigger
    try:
        cv2.namedWindow("GOZCU-AI canli", cv2.WINDOW_NORMAL)
    except cv2.error:
        print("Görüntü penceresi açılamıyor (ekransız sistem ya da 'opencv-python-headless' kurulu).\n"
              "Çözüm: pip uninstall -y opencv-python-headless && pip install opencv-python\n"
              "Ekransız kurulumda 'incele' akışını kullan.")
        return 1
    cap = _kamera_ac(a.kamera)
    if cap is None:
        cv2.destroyAllWindows()
        print(f"Kamera {a.kamera} açılamadı. Kamerayı başka bir program kullanıyor olabilir "
              "(Zoom, Teams, Kamera uygulaması) — kapatıp tekrar dene; ya da başka numara dene: "
              "python -m gozcu canli 1")
        return 1
    c.hazirla()
    cfg = InspectionConfig.load(c.ayarlar)
    if not cfg.calibrated:
        print("Uyarı: kalibrasyon yok — önce altın numuneyle 'kalibre' önerilir.")
    pipe = InspectionPipeline(cfg)
    toplam, imzalar = c.sayac_oku()
    trig, idx = AutoTrigger(), 1
    print("Canlı mod: SPACE = incele · B = boş sahneyi referans al · Q = çık"
          + ("  [OTOMATİK: parça yerleşince kendiliğinden incelenir]" if a.otomatik else ""))
    try:
        while True:
            ok, kare = cap.read()
            if not ok:
                print("Kameradan kare alınamadı, çıkılıyor.")
                break
            durum = trig.update(kare) if a.otomatik else ""
            ust = "SPACE: incele  B: bos sahne  Q: cik"
            if a.otomatik:
                ust += "   [OTO: " + ("once B ile bos sahneyi tanit" if trig.bg is None else durum) + "]"
            gorunum = kare.copy()
            cv2.putText(gorunum, ust, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            cv2.imshow("GOZCU-AI canli", gorunum)
            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), ord("Q"), 27) or not _pencere_acik("GOZCU-AI canli"):
                break
            if k in (ord("b"), ord("B")):
                trig.set_background(kare)
                print("  boş sahne referansı alındı — parçayı koyabilirsin")
                continue
            if k == 32 or (a.otomatik and durum == "tetikle"):
                ad = f"canli_{time.strftime('%Y%m%d_%H%M%S')}_{idx:03d}"
                idx += 1
                r = pipe.inspect(kare, ad)
                toplam.add(r)
                fire_report.append_history(str(c.gecmis), r)
                ann = annotate(r.normalized_image, r)
                imwrite_tr(str(c.cikti / _dosya_adi(ad, r.verdict)), ann)
                print(f"  [{ad}] {r.verdict} · %{r.score:.0f}"
                      + ("" if r.ok else "  <- " + "; ".join(r.reasons)))
                olcek = min(1.0, 700 / ann.shape[1])
                cv2.imshow("GOZCU-AI sonuc", cv2.resize(ann, None, fx=olcek, fy=olcek))
                cv2.waitKey(1500)
                try:
                    cv2.destroyWindow("GOZCU-AI sonuc")
                except cv2.error:
                    pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        c.sayac_yaz(toplam, imzalar)
    print("Kalıcı toplam →", toplam.summary_tr().splitlines()[0])
    return 0


def cmd_simulasyon(c: Calisma, a) -> int:
    """Sanal bant: üretim sayaçlarına ve geçmişe DOKUNMAZ."""
    import numpy as np
    from .synth import make_sample
    adet = max(1, min(500, a.adet))
    out = c.cikti / "simulasyon"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.tohum)
    turler = ["good"] * 6 + ["capak", "kirik", "cizik", "leke", "eksik_dolum"]
    pipe = InspectionPipeline(InspectionConfig())
    sayac, sonuclar, isaretli = Counters(), [], []
    print(f"◆ Sanal bant başladı — {adet} parça akıyor…\n")
    t0 = time.perf_counter()
    for i in range(1, adet + 1):
        img, _ = make_sample(str(rng.choice(turler)), rng)
        ad = f"bant_{i:03d}"
        r = pipe.inspect(img, ad)
        sayac.add(r)
        sonuclar.append(r)
        ann = annotate(r.normalized_image, r)
        isaretli.append(ann)
        imwrite_tr(str(out / _dosya_adi(ad, r.verdict)), ann)
        isaret = {"ok": "[+]", "suspect": "[?]", "reject": "[X]"}[r.status]
        print(f"  {isaret} {ad} {r.verdict:8s} %{r.score:3.0f}"
              + ("" if r.ok else "  " + "; ".join(r.reasons)[:58]))
        if a.bekle:
            time.sleep(0.12)
    sure = time.perf_counter() - t0
    write_batch_report(sonuclar, sayac, str(out / "parti_raporu.json"), str(out / "parti_raporu.txt"))
    report_html.render(sonuclar, sayac, isaretli, str(out / "rapor.html"),
                       f"sanal bant simülasyonu · {adet} parça · {sure:.0f} sn")
    print("\n" + sayac.summary_tr())
    print(f"Rapor: {out / 'rapor.html'}")
    print("Not: simülasyon verisi kalıcı sayaçlara ve geçmişe yazılmaz.")
    return 0


def cmd_rapor(c: Calisma, a) -> int:
    kayitlar = fire_report.load_history(str(c.gecmis))
    if not kayitlar:
        print("Henüz geçmiş kaydı yok. Önce 'incele' ya da 'canli' ile muayene yap; "
              "her muayene otomatik kaydedilir.")
        return 1
    c.cikti.mkdir(parents=True, exist_ok=True)
    html_p, csv_p = c.cikti / "fire_raporu.html", c.cikti / "fire_raporu.csv"
    fire_report.render_fire_report(kayitlar, str(html_p), str(c.cikti), VERSION)
    fire_report.write_csv(kayitlar, str(csv_p))
    print(f"✓ {len(kayitlar)} kayıttan rapor üretildi:\n  HTML: {html_p}\n  CSV : {csv_p}  (Excel ile açılır)")
    return 0


def cmd_politika(c: Calisma, a) -> int:
    cfg = InspectionConfig.load(c.ayarlar)
    if not a.hedef:
        print("Kusur politikaları (izin seviyesi 0-100 · 0 = sıfır tolerans, 100 = yok say):")
        for k in DEFAULT_POLICIES:
            v = cfg.policies.get(k, 0)
            etiket = "yok sayılıyor" if v >= 100 else "sıfır tolerans" if v == 0 else f"şiddet ≤ {v} tolere"
            print(f"  {KIND_LABELS.get(k, k):14s} {v:3d}  ({etiket})")
        print(f"\nUygunluk eşiği: %{cfg.min_score}  (skor bu değerin altında → FİRE)")
        print("Değiştirmek için: python -m gozcu politika <tür|hepsi|esik> <değer>")
        print("  değer: sifir | hafif | yok_say | 0-100   ·   türler: " + ", ".join(DEFAULT_POLICIES))
        return 0
    if a.deger is None:
        print("Eksik değer. Örnek: python -m gozcu politika cizik yok_say")
        return 1
    hedef, deger = a.hedef.lower(), a.deger.lower()
    try:
        v = POLICY_PRESETS[deger] if deger in POLICY_PRESETS else int(deger)
        if not 0 <= v <= 100:
            raise ValueError
    except ValueError:
        print("Değer: sifir | hafif | yok_say | 0-100 arası tam sayı")
        return 1
    if hedef == "esik":
        cfg.min_score = v
        print(f"✓ Uygunluk eşiği: %{v} (skor bu değerin altında → FİRE)")
    elif hedef == "hepsi":
        cfg.policies = {k: v for k in DEFAULT_POLICIES}
        print(f"✓ Tüm türler için izin seviyesi: {v}")
    elif hedef in DEFAULT_POLICIES:
        cfg.policies[hedef] = v
        print(f"✓ {KIND_LABELS.get(hedef, hedef)} izin seviyesi: {v}")
    else:
        print("Tür: " + " | ".join(DEFAULT_POLICIES) + " | hepsi | esik")
        return 1
    c.kok.mkdir(parents=True, exist_ok=True)
    cfg.save(c.ayarlar)
    return 0


def cmd_sifirla(c: Calisma, a) -> int:
    if c.sayac_dosyasi.exists():
        c.sayac_dosyasi.unlink()
    print("Kalıcı sayaçlar sıfırlandı (aynı fotoğraflar yeniden sayılabilir).")
    if a.gecmis:
        if c.gecmis.exists():
            c.gecmis.unlink()
        print("Geçmiş arşivi de silindi (gecmis.jsonl).")
    else:
        print("Not: geçmiş arşivi korunur; onu da silmek için: python -m gozcu sifirla gecmis")
    return 0


def cmd_kontrol(c: Calisma, a) -> int:
    tamam = True

    def satir(ok: bool, metin: str) -> None:
        nonlocal tamam
        tamam &= ok
        print(("  [ OK ] " if ok else "  [HATA] ") + metin)

    print(f"GÖZCÜ·AI {VERSION} — kurulum kontrolü\n")
    satir(sys.version_info >= ASGARI_PY, f"Python {platform.python_version()} (gereken ≥ 3.9)")
    try:
        import cv2
        import numpy as np
        satir(True, f"OpenCV {cv2.__version__} · NumPy {np.__version__}")
        import re
        gui = not re.search(r"GUI:\s+NONE", cv2.getBuildInformation())
        print("  [BİLGİ] Canlı kamera penceresi: " + ("destekleniyor" if gui else
              "YOK (headless OpenCV) — canlı mod çalışmaz, diğer her şey çalışır"))
    except ImportError as e:
        satir(False, f"OpenCV/NumPy kurulu değil ({e}). Çözüm: 1_KURULUM.bat ya da "
                     "pip install -r requirements.txt")
        return 1
    satir(True, f"Çalışma klasörü: {c.kok}")
    try:
        with tempfile.TemporaryDirectory(prefix="gözcü_çğış_") as t:
            from .synth import make_sample
            img, _ = make_sample("capak")
            yol = Path(t) / "Türkçe ÇĞİŞ yol.png"
            satir(imwrite_tr(str(yol), img) and imread_tr(str(yol)) is not None,
                  "Türkçe karakterli yolda görüntü okuma/yazma")
            r = InspectionPipeline(InspectionConfig()).inspect(img, "test")
            satir(r.verdict == "FİRE" and any(d.kind == "capak" for d in r.defects),
                  "Muayene motoru (çapaklı test parçası FİRE çıktı)")
    except OSError as e:
        satir(False, f"Geçici dosya yazılamadı: {e}")
    c.hazirla()
    test = c.kok / ".yazma_testi"
    try:
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        satir(True, "Çalışma klasörü yazılabilir")
    except OSError as e:
        satir(False, f"Çalışma klasörüne yazılamıyor: {e}")
    cfg = InspectionConfig.load(c.ayarlar)
    durum = ("kalibre edilmiş, öz-test geçti" if cfg.calibrated and cfg.selftest_ok else
             "kalibre edilmiş AMA öz-test geçmedi — yeniden kalibre et" if cfg.calibrated else
             "henüz kalibre edilmedi (kendi parçan için: kalibre)")
    print(f"  [BİLGİ] Kalibrasyon: {durum}")
    print(f"  [BİLGİ] altin_numune/: {len(gorselleri_listele(c.altin))} fotoğraf · "
          f"fotograflar/: {len(gorselleri_listele(c.fotolar))} fotoğraf")
    print("\n" + ("Her şey hazır." if tamam else "Yukarıdaki [HATA] satırlarını düzeltip tekrar dene."))
    return 0 if tamam else 1


def main(argv=None) -> int:
    _konsol_utf8()
    if sys.version_info < ASGARI_PY:
        print(f"GÖZCÜ·AI için Python 3.9 ya da üstü gerekli (sende {platform.python_version()}).")
        return 1
    ap = argparse.ArgumentParser(prog="gozcu", description="GÖZCÜ·AI görüntü işleme kalite kontrol",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--klasor", help="çalışma klasörü (varsayılan: bulunulan klasör)")
    ap.add_argument("--surum", action="version", version=f"GÖZCÜ·AI {VERSION}")
    alt = ap.add_subparsers(dest="komut")
    for ad in ("demo", "ornek", "kalibre", "incele", "rapor", "kontrol"):
        alt.add_parser(ad)
    p = alt.add_parser("canli")
    p.add_argument("kamera", nargs="?", type=int, default=0)
    p.add_argument("mod", nargs="?", choices=["otomatik"])
    p = alt.add_parser("simulasyon")
    p.add_argument("adet", nargs="?", type=int, default=25)
    p.add_argument("--tohum", type=int, default=None)
    p.add_argument("--hizli", dest="bekle", action="store_false", help="parçalar arasında beklemeden")
    p = alt.add_parser("politika")
    p.add_argument("hedef", nargs="?")
    p.add_argument("deger", nargs="?")
    p = alt.add_parser("sifirla")
    p.add_argument("gecmis", nargs="?", choices=["gecmis"])
    a = ap.parse_args(argv)
    if not a.komut:
        print(__doc__)
        return 0
    if a.komut == "canli":
        a.otomatik = a.mod == "otomatik"
    if a.komut == "sifirla":
        a.gecmis = a.gecmis == "gecmis"
    c = Calisma(a.klasor)
    tablo = {"demo": cmd_demo, "ornek": cmd_ornek, "kalibre": cmd_kalibre, "incele": cmd_incele,
             "canli": cmd_canli, "simulasyon": cmd_simulasyon, "rapor": cmd_rapor,
             "politika": cmd_politika, "sifirla": cmd_sifirla, "kontrol": cmd_kontrol}
    return tablo[a.komut](c, a)
