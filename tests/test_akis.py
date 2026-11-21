"""Çalışma klasörü, komut satırı, sayaçlar, raporlar, kalibrasyon güvenliği, canlı tetikleyici."""
import json
import shutil

import cv2
import numpy as np
import pytest

from gozcu.calisma import Calisma, dosya_imzasi, gorselleri_listele
from gozcu.cli import ORNEKLER, main
from gozcu.config import InspectionConfig
from gozcu.io_utils import imread_tr, imwrite_tr
from gozcu.live import AutoTrigger
from gozcu.pipeline import Counters


@pytest.fixture
def klasor(tmp_path):
    k = tmp_path / "Masaüstü" / "GÖZCÜ çalışma"      # Türkçe + boşluklu yol
    k.mkdir(parents=True)
    return k


def _cal(k, *argv):
    return main(["--klasor", str(k), *argv])


def test_turkce_yolda_io(klasor):
    img = np.full((40, 40, 3), 128, np.uint8)
    yol = klasor / "ığüşöç İĞÜŞÖÇ.png"
    assert imwrite_tr(str(yol), img) and np.array_equal(imread_tr(str(yol)), img)
    assert imread_tr(str(klasor / "yok.png")) is None


def test_gorsel_listesi_buyuk_kucuk_harf(klasor):
    for ad in ("a.JPG", "b.jpeg", "c.PNG", "not.txt", ".gizli.jpg"):
        (klasor / ad).write_bytes(b"x")
    assert [p.name for p in gorselleri_listele(klasor)] == ["a.JPG", "b.jpeg", "c.PNG"]


def test_demo_ve_ornek_kullanici_klasorlerine_dokunmaz(klasor, capsys):
    assert _cal(klasor, "demo") == 0
    assert _cal(klasor, "ornek") == 0
    assert gorselleri_listele(klasor / "altin_numune") == []
    assert gorselleri_listele(klasor / "fotograflar") == []
    assert not (klasor / "ayarlar.json").exists() and not (klasor / "sayaclar.json").exists()
    assert (klasor / "cikti" / "ornek" / "cikti" / "rapor.html").is_file()
    assert "20/20" in capsys.readouterr().out


def _hazirla(klasor, kontrol=("foto_01_good.jpg", "foto_03_capak.jpg", "foto_04_kirik.jpg")):
    c = Calisma(klasor).hazirla()
    for f in (ORNEKLER / "altin").iterdir():
        shutil.copy2(f, c.altin / f.name)
    for ad in kontrol:
        shutil.copy2(ORNEKLER / "kontrol" / ad, c.fotolar / ad)
    return c


def test_kalibre_incele_tekrar_sayilmaz(klasor, capsys):
    c = _hazirla(klasor)
    assert _cal(klasor, "kalibre") == 0
    assert InspectionConfig.load(c.ayarlar).calibrated
    assert _cal(klasor, "incele") == 0
    assert _cal(klasor, "incele") == 0                            # aynı fotoğraflar ikinci kez
    shutil.copy2(c.fotolar / "foto_03_capak.jpg", c.fotolar / "kopya.jpg")   # yeniden adlandırılmış kopya
    assert _cal(klasor, "incele") == 0
    toplam, imzalar = c.sayac_oku()
    assert (toplam.total, toplam.good, toplam.scrap) == (3, 1, 2) and len(imzalar) == 3
    assert len(c.gecmis.read_text(encoding="utf-8").splitlines()) == 3
    assert "TEKRAR eklenmedi" in capsys.readouterr().out
    assert _cal(klasor, "rapor") == 0
    csv = (c.cikti / "fire_raporu.csv").read_text(encoding="utf-8-sig")
    assert csv.splitlines()[0].startswith("Zaman;Parça;Karar") and len(csv.splitlines()) == 4
    assert "Fire Raporu" in (c.cikti / "fire_raporu.html").read_text(encoding="utf-8")
    # cikti dosya adları ASCII (Windows'ta sorunsuz)
    assert {p.name for p in c.cikti.glob("*.png")} >= {"foto_03_capak__FIRE.png", "foto_01_good__SAGLAM.png"}


def test_sifirla_sayaclari_ve_imzalari_birlikte_siler(klasor):
    c = _hazirla(klasor, kontrol=("foto_01_good.jpg",))
    _cal(klasor, "kalibre")
    _cal(klasor, "incele")
    assert _cal(klasor, "sifirla") == 0 and c.gecmis.exists()
    _cal(klasor, "incele")
    assert c.sayac_oku()[0].total == 1                            # sıfırlamadan sonra yeniden sayıldı
    assert _cal(klasor, "sifirla", "gecmis") == 0 and not c.gecmis.exists()


def test_karisik_altin_numune_reddedilir(klasor, capsys):
    c = Calisma(klasor).hazirla()
    shutil.copy2(ORNEKLER / "altin" / "altin_1.jpg", c.altin / "altin_1.jpg")
    kapak = np.full((600, 600, 3), 40, np.uint8)
    cv2.circle(kapak, (300, 300), 150, (200, 200, 200), -1)
    cv2.imwrite(str(c.altin / "kapak.jpg"), kapak)
    assert _cal(klasor, "kalibre") == 1
    assert "BİRBİRİNE BENZEMİYOR" in capsys.readouterr().out
    assert not c.ayarlar.exists()                                 # bozuk kalibrasyon kaydedilmedi


def test_parca_bulunamayan_altin_bildirilir(klasor, capsys):
    c = _hazirla(klasor)
    cv2.imwrite(str(c.altin / "bos.jpg"), np.full((400, 400, 3), 40, np.uint8))
    _cal(klasor, "kalibre")
    cikti = capsys.readouterr().out
    assert "parça bulunamadı" in cikti and "bos.jpg" in cikti


def test_kalibrasyonsuz_bos_klasor(klasor):
    assert _cal(klasor, "kalibre") == 1
    assert _cal(klasor, "incele") == 1
    assert _cal(klasor, "rapor") == 1


def test_politika_kalici_ve_dogrulanir(klasor):
    assert _cal(klasor, "politika", "cizik", "yok_say") == 0
    assert _cal(klasor, "politika", "esik", "95") == 0
    assert _cal(klasor, "politika", "esik", "120") == 1
    assert _cal(klasor, "politika", "uzayli", "10") == 1
    cfg = InspectionConfig.load(klasor / "ayarlar.json")
    assert cfg.policies["cizik"] == 100 and cfg.min_score == 95


def test_bozuk_ayar_ve_sayac_dosyasi(klasor, capsys):
    (klasor / "ayarlar.json").write_text("{bozuk", encoding="utf-8")
    assert InspectionConfig.load(klasor / "ayarlar.json").calibrated is False
    (klasor / "ayarlar.json").write_text(json.dumps({"reference": {"bilinmeyen": 1}, "min_score": "x"}), encoding="utf-8")
    assert InspectionConfig.load(klasor / "ayarlar.json").min_score == 70
    c = Calisma(klasor)
    c.sayac_dosyasi.write_text("{bozuk", encoding="utf-8")
    t, i = c.sayac_oku()
    assert t.total == 0 and (klasor / "sayaclar.bozuk.json").exists()


def test_kontrol_komutu(klasor, capsys):
    assert _cal(klasor, "kontrol") == 0
    assert "Türkçe karakterli yolda" in capsys.readouterr().out


def test_simulasyon_sayaclara_dokunmaz(klasor):
    assert _cal(klasor, "simulasyon", "6", "--hizli", "--tohum", "1") == 0
    assert not (klasor / "sayaclar.json").exists() and not (klasor / "gecmis.jsonl").exists()
    assert (klasor / "cikti" / "simulasyon" / "rapor.html").is_file()


def test_dosya_imzasi_icerige_bagli(tmp_path):
    a, b = tmp_path / "a.bin", tmp_path / "b.bin"
    a.write_bytes(b"ayni")
    b.write_bytes(b"ayni")
    assert dosya_imzasi(a) == dosya_imzasi(b)
    b.write_bytes(b"farkli")
    assert dosya_imzasi(a) != dosya_imzasi(b)


def test_otomatik_tetik_her_parcada_bir_kez():
    rng = np.random.default_rng(1)

    def kare(x=None):
        f = np.full((480, 640, 3), 60, np.uint8)
        if x is not None:
            cv2.circle(f, (int(x), 240), 90, (200, 200, 200), -1)
        return np.clip(f + rng.normal(0, 1.5, f.shape), 0, 255).astype(np.uint8)

    t = AutoTrigger()
    assert t.update(kare()) == "bekle"            # boş sahne tanıtılmadan tetiklemez
    t.set_background(kare())
    dizi = [None] * 3 + list(range(80, 320, 40)) + [320] * 10 + [None] * 4 + list(range(100, 320, 40)) + [320] * 10
    olaylar = [t.update(kare(x)) for x in dizi]
    assert olaylar.count("tetikle") == 2


def test_sayac_turler_parca_basina():
    from gozcu.detectors import Defect
    from gozcu.pipeline import InspectionResult
    c = Counters()
    d = Defect("cizik", "Çizik", (0, 0, 1, 1), 0.5)
    c.add(InspectionResult(False, [d, d], [], None, status="reject"))
    assert c.by_kind == {"cizik": 1} and c.scrap == 1
