"""Muayene motoru: doğruluk, zorlu sahneler, kalite kapıları, politikalar."""
import cv2
import numpy as np
import pytest

from gozcu.calibrate import calibrate
from gozcu.config import InspectionConfig
from gozcu.detectors import segment_part
from gozcu.pipeline import InspectionPipeline, annotate, ascii_metin
from gozcu.synth import CX, CY, IMG, R_HOLE, R_OUT, make_batch, make_sample

SPEC = [("good", 8), ("capak", 2), ("kirik", 2), ("cizik", 2),
        ("leke", 2), ("eksik_dolum", 2), ("karma", 2)]


@pytest.fixture(scope="module")
def pipe():
    return InspectionPipeline(InspectionConfig())


def test_sentetik_parti_karar_ve_tur(pipe):
    dogru = tur_dogru = tur_toplam = sahte = 0
    for ad, img, eklenen in make_batch(SPEC):
        r = pipe.inspect(img, ad)
        dogru += (len(eklenen) > 0) != r.ok
        bulunan = {d.kind for d in r.defects}
        tur_toplam += len(eklenen)
        tur_dogru += sum(k in bulunan for k in eklenen)
        sahte += bool(bulunan - set(eklenen))
    assert dogru == 20, "sağlam/fire kararı"
    assert tur_dogru == tur_toplam == 14, "kusur türü adlandırma"
    assert sahte == 0, "eklenmemiş tür tespiti"


def test_parti_tekrarlanabilir():
    a = make_batch([("capak", 2)])
    b = make_batch([("capak", 2)])
    assert all(np.array_equal(x[1], y[1]) for x, y in zip(a, b))


def test_bilinmeyen_tur_hata_verir():
    with pytest.raises(ValueError):
        make_sample("uzayli")


@pytest.mark.parametrize("olcek", [0.6, 1.0, 1.6])
def test_olcek_bagimsizligi(pipe, olcek):
    img, _ = make_sample("capak", np.random.default_rng(3))
    r = pipe.inspect(cv2.resize(img, None, fx=olcek, fy=olcek), "olcek")
    assert r.verdict == "FİRE" and "capak" in {d.kind for d in r.defects}


def test_acik_zemin(pipe):
    img, _ = make_sample("good", np.random.default_rng(4))
    assert pipe.inspect(255 - img, "ters").verdict == "SAĞLAM"


# ── zorlu sahneler ───────────────────────────────────────────────────
def test_ahsap_zemin_ve_isik_kaymasi(rng, ahsap, kapak):
    cfg = InspectionConfig()
    s = segment_part(kapak(ahsap(rng), 310, 305, 170, rng), cfg)
    assert s is not None and abs(s.radius - 170) < 12 and abs(s.center[0] - 310) < 5
    img = kapak(ahsap(rng), 300, 310, 165, rng).astype(np.float32)
    img *= np.tile(np.linspace(0.7, 1.25, 620, dtype=np.float32), (620, 1))[..., None]
    s = segment_part(np.clip(img, 0, 255).astype(np.uint8), cfg)
    assert s is not None and abs(s.radius - 165) < 12


def test_gri_benzer_renk_farkli_zemin(rng, kapak):
    zemin = np.dstack([np.full((620, 620), v, np.uint8) for v in (120, 170, 140)])
    s = segment_part(kapak(zemin, 315, 300, 168, rng, renk=(190, 140, 150)), InspectionConfig())
    assert s is not None and abs(s.radius - 168) < 12


def test_ahsapta_kalibrasyon_ve_kusur(tmp_path, rng, ahsap, kapak):
    for i in range(2):
        cv2.imwrite(str(tmp_path / f"a{i}.png"), kapak(ahsap(rng), 310, 306, 168, rng))
    cfg = InspectionConfig()
    ok, msg = calibrate(tmp_path, cfg, ayar_yolu=tmp_path / "ayar.json")
    assert ok and cfg.selftest_ok, msg
    p = InspectionPipeline(InspectionConfig.load(tmp_path / "ayar.json"))
    assert p.inspect(kapak(ahsap(rng), 308, 310, 168, rng), "s").verdict == "SAĞLAM"
    r = p.inspect(kapak(ahsap(rng), 308, 310, 168, rng, kusur="kirik"), "k")
    assert r.verdict == "FİRE" and "kirik" in {d.kind for d in r.defects}
    r = p.inspect(kapak(ahsap(rng), 308, 310, 168, rng, kusur="cizik"), "c")
    assert r.verdict == "FİRE" and "cizik" in {d.kind for d in r.defects}
    # eğim: %15 basık çekim düzeltilir; %40 basıkta karar verilmez
    duz = kapak(ahsap(rng), 310, 306, 168, rng)
    assert p.inspect(cv2.resize(duz, None, fx=1, fy=0.85), "e").verdict == "SAĞLAM"
    r = p.inspect(cv2.resize(duz, None, fx=1, fy=0.60), "e2")
    assert r.status == "suspect" and "yatık" in r.reasons[0]


# ── kalite kapıları: tahmin etme, ŞÜPHELİ de ──────────────────────────
def _kapilar():
    rng = np.random.default_rng(3)
    g, _ = make_sample("good", rng)
    g13 = cv2.resize(g, None, fx=1.3, fy=1.3)
    kesik = np.full_like(g13, 38)
    kesik[:, :g13.shape[1] - 180] = g13[:, 180:]
    a, _ = make_sample("good", rng)
    b, _ = make_sample("good", rng)
    iki = np.full((int(IMG * 1.3), int(IMG * 2.4), 3), 38, np.uint8)
    a2, b2 = cv2.resize(a, None, fx=1.2, fy=1.2), cv2.resize(b, None, fx=1.1, fy=1.1)
    iki[20:20 + a2.shape[0], 10:10 + a2.shape[1]] = a2
    iki[30:30 + b2.shape[0], 620:620 + b2.shape[1]] = b2
    bos = np.clip(np.full((600, 600, 3), 38.0) + rng.normal(0, 2, (600, 600, 3)), 0, 255).astype(np.uint8)
    sinir = g.copy()
    pts = [(CX + ((R_OUT - 4) if i in (0, 8) else R_OUT + 7) * np.cos(0.7 + (i - 4) * 0.05),
            CY + ((R_OUT - 4) if i in (0, 8) else R_OUT + 7) * np.sin(0.7 + (i - 4) * 0.05)) for i in range(9)]
    cv2.fillPoly(sinir, [np.array(pts, np.int32)], 165)
    return [("bulanık", cv2.GaussianBlur(g13, (31, 31), 8), "bulanık"),
            ("karanlık", cv2.convertScaleAbs(g13, alpha=0.16), "karanlık"),
            ("kesik", kesik, "kadrajda"),
            ("çoklu", iki, "birden çok"),
            ("boş", bos, "bulunamadı"),
            ("sınırda", cv2.resize(sinir, None, fx=1.3, fy=1.3), "sınırda")]


@pytest.mark.parametrize("ad,img,parca", _kapilar(), ids=[k[0] for k in _kapilar()])
def test_kalite_kapilari(pipe, ad, img, parca):
    r = pipe.inspect(img, ad)
    assert r.status == "suspect", (ad, r.verdict, r.reasons)
    assert any(parca in x for x in r.reasons), r.reasons


# ── ek dedektörler ───────────────────────────────────────────────────
def test_es_parlaklikta_renkli_leke(pipe):
    img, _ = make_sample("good", np.random.default_rng(2))
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    cv2.ellipse(lab, (300, 220), (16, 12), 30, 0, 360, (168, 146, 108), -1)
    r = pipe.inspect(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), "renk")
    assert r.verdict == "FİRE" and "leke" in {d.kind for d in r.defects}


def test_kacik_delik_ve_saat_yonu(pipe):
    img, _ = make_sample("good", np.random.default_rng(6))
    cv2.circle(img, (CX, CY), R_HOLE + 2, (168, 168, 168), -1)
    cv2.circle(img, (CX + 28, CY - 10), R_HOLE, (38, 38, 38), -1)
    r = pipe.inspect(img, "kacik")
    d = next(d for d in r.defects if "kaçık" in d.label)
    assert r.verdict == "FİRE" and "saat" in d.detail


# ── politikalar ve eşik ──────────────────────────────────────────────
def test_politika_tolere_eder_ama_raporlar():
    img, _ = make_sample("cizik", np.random.default_rng(11))
    img = cv2.resize(img, None, fx=1.3, fy=1.3)
    cfg = InspectionConfig()
    assert InspectionPipeline(cfg).inspect(img).verdict == "FİRE"
    cfg.policies["cizik"] = 100
    r = InspectionPipeline(cfg).inspect(img)
    assert r.verdict == "SAĞLAM" and r.score == 100 and [d.kind for d in r.tolerated] == ["cizik"]
    assert any("tolere" in x for x in r.reasons)


def test_esik_95_kucuk_lekeyi_fire_yapar():
    img, _ = make_sample("leke", np.random.default_rng(11))
    cfg = InspectionConfig(min_score=95)
    r = InspectionPipeline(cfg).inspect(img)
    assert r.verdict == "FİRE" and r.score < 95


def test_ozdes_iki_kusur_dogru_kovaya_duser():
    """Değer-eşitliği hatası regresyonu: aynı iki bulgu ayrı kovalara bölünmemeli."""
    from gozcu.detectors import Defect
    cfg = InspectionConfig()
    cfg.policies["cizik"] = 50
    p = InspectionPipeline(cfg)
    d1 = Defect("cizik", "Çizik", (10, 10, 5, 5), 0.3, "x")
    d2 = Defect("cizik", "Çizik", (10, 10, 5, 5), 0.3, "x")
    aktif = [d for d in (d1, d2) if d.severity * 100 > cfg.policies.get(d.kind, 0)]
    assert aktif == [] and p is not None


# ── görüntü üstü metin ───────────────────────────────────────────────
def test_goruntu_metni_ascii():
    assert ascii_metin("FİRE · ŞÜPHELİ — Çapak, ığüşöç") == "FIRE - SUPHELI - Capak, igusoc"


def test_annotate_bozulmadan_calisir(pipe):
    img, _ = make_sample("capak", np.random.default_rng(5))
    r = pipe.inspect(img)
    out = annotate(r.normalized_image, r)
    assert out.shape == r.normalized_image.shape and out[5, 5, 2] > 150   # kırmızı FİRE bandı
