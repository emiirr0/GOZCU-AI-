"""GÖZCÜ·AI — altın numuneden kalibrasyon.

'altin_numune/' klasörüne konan SAĞLAM parça fotoğraf(lar)ından
referans geometriyi ve gürültüye uyarlanmış eşikleri öğrenir,
ayarlar.json'a yazar. Birden çok fotoğraf verilirse ortalaması alınır
(daha kararlı kalibrasyon).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .config import InspectionConfig
from .detectors import segment_part
from .io_utils import imread_tr

def _measure_one(path: str, cfg: InspectionConfig):
    img = imread_tr(path)
    if img is None:
        return None
    if max(img.shape[:2]) > 1600:
        s = 1600 / max(img.shape[:2])
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    seg = segment_part(img, cfg)
    if seg is None:
        return None
    pts = seg.outer_contour.reshape(-1, 2).astype(np.float64)
    d = np.hypot(pts[:, 0] - seg.center[0], pts[:, 1] - seg.center[1])
    r_out = float(np.median(d))
    roughness = float(np.std(d)) / r_out          # kenar pürüzlülüğü (göreli)
    # delik: merkez bölge malzeme mi boş mu
    cx, cy = int(seg.center[0]), int(seg.center[1])
    probe = max(4, int(r_out * 0.12))
    roi = seg.material_mask[cy - probe:cy + probe, cx - probe:cx + probe]
    hole = roi.size > 0 and float(np.count_nonzero(roi)) / roi.size < 0.5
    hole_r = 0.0
    if hole:
        # merkezden dışa tarayıp malzemenin başladığı yarıçapı bul
        for rr in range(probe, int(r_out)):
            ring = seg.material_mask[cy, min(cx + rr, seg.material_mask.shape[1] - 1)]
            if ring > 0:
                hole_r = float(rr)
                break
    # yüzey gürültüsü: medyan tabandan sapmanın std'si (iç bölge)
    inner = cv2.erode(seg.material_mask, np.ones((17, 17), np.uint8))
    base = cv2.medianBlur(gray, 51)
    diff = cv2.absdiff(gray, base).astype(np.float64)
    vals = diff[inner > 0]
    sigma = float(vals.std()) if vals.size else 3.0
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    da = cv2.absdiff(lab[..., 1], cv2.medianBlur(lab[..., 1], 51)).astype(np.float64)
    db = cv2.absdiff(lab[..., 2], cv2.medianBlur(lab[..., 2], 51)).astype(np.float64)
    dcv = np.sqrt(da * da + db * db)[inner > 0]
    sigma_c = float(dcv.std()) if dcv.size else 2.0
    area = float(np.count_nonzero(seg.material_mask))
    return dict(r_out=r_out, hole=hole, hole_oran=hole_r / r_out if hole else 0.0,
                roughness=roughness, sigma=sigma, sigma_c=sigma_c, area=area)


def calibrate(folder, cfg: Optional[InspectionConfig] = None,
              ayar_yolu=None) -> Tuple[bool, str]:
    """Klasördeki altın numunelerden öğren; (başarı, mesaj) döndür.
    ayar_yolu verilirse sonuç oraya kaydedilir."""
    from .calisma import gorselleri_listele
    cfg = cfg or InspectionConfig()
    files = [str(p) for p in gorselleri_listele(Path(folder))]
    if not files:
        return False, ("altin_numune/ klasöründe fotoğraf yok. "
                       "SAĞLAM bir parçanın 2-3 fotoğrafını koyup tekrar dene.")
    olcumler = [(f, _measure_one(f, cfg)) for f in files]
    atlanan = [os.path.basename(f) for f, m in olcumler if m is None]
    ms = [m for _, m in olcumler if m]
    if not ms:
        return False, ("Hiçbir fotoğrafta parça bulunamadı (zemin/parça kontrastını artır, "
                       "parçayı kadrajın ortasına koy).")

    # ── tutarlılık: klasöre farklı parçalar karışmış mı? ──
    tutarsiz = []
    if len(ms) >= 2:
        delikli = sum(m["hole"] for m in ms)
        if 0 < delikli < len(ms):
            tutarsiz.append(f"{delikli}/{len(ms)} fotoğrafta delik var, diğerlerinde yok")
        oranlar = [m["hole_oran"] for m in ms if m["hole"]]
        if len(oranlar) >= 2 and max(oranlar) - min(oranlar) > 0.08:
            tutarsiz.append("delik/çap oranları birbirinden çok farklı")
    if tutarsiz:
        return False, ("ALTIN NUMUNELER BİRBİRİNE BENZEMİYOR: " + "; ".join(tutarsiz) +
                       ".\n  altin_numune/ klasöründe YALNIZCA aynı tip SAĞLAM parçanın "
                       "fotoğrafları olmalı (başka parça ya da örnek dosya karışmış olabilir). "
                       "Kalibrasyon kaydedilmedi.")

    r_out = float(np.median([m["r_out"] for m in ms]))
    hole = sum(m["hole"] for m in ms) > len(ms) / 2
    hole_r = float(np.median([m["hole_oran"] for m in ms if m["hole"]])) * r_out if hole else 0.0
    rough = float(np.median([m["roughness"] for m in ms]))
    sigma = float(np.median([m["sigma"] for m in ms]))

    ref = cfg.reference
    ref.outer_radius = r_out
    ref.hole_expected = bool(hole)
    ref.hole_radius = hole_r if hole else 0.0
    # tolerans: altın kenar pürüzlülüğünün 4 katı, ama %2.5'ten az olmasın
    ref.radius_tolerance = max(0.025, min(0.08, 4.0 * rough))
    th = cfg.thresholds
    # yüzey eşikleri: altın yüzey gürültüsünün ~5-6 katı
    th.scratch_diff = int(max(10, min(40, round(5.5 * sigma))))
    th.stain_diff = int(max(12, min(45, round(6.0 * sigma))))
    sigma_c = float(np.median([m["sigma_c"] for m in ms]))
    th.color_diff = int(max(8, min(30, round(6.0 * sigma_c))))
    # uzunluk/alan eşikleri yarıçapa göre ölçeklensin
    th.scratch_min_len = int(max(20, round(r_out * 0.20)))
    th.stain_min_area = int(max(80, round((r_out * 0.07) ** 2 * 3.14)))
    cfg.calibrated = True

    tek_not = ("\n  Not: tek altın numune kullanıldı — kararlılık için "
               "en az 3 fotoğraf önerilir." if len(ms) == 1 else "")
    msg = (f"Kalibrasyon tamam: {len(ms)} numune · yarıçap {r_out:.0f}px · "
           f"delik {'VAR (%.0fpx)' % hole_r if hole else 'YOK'} · "
           f"kenar toleransı ±%{ref.radius_tolerance*100:.1f} · "
           f"yüzey gürültüsü σ={sigma:.1f} → çizik eşiği {th.scratch_diff}"
           + tek_not)
    if atlanan:
        msg += ("\n  Uyarı: şu fotoğraflarda parça bulunamadı, kalibrasyona katılmadı: "
                + ", ".join(atlanan))

    # ── öz-test: altın numuneler kendi kalibrasyonundan SAĞLAM çıkmalı ──
    from .pipeline import InspectionPipeline
    pipe = InspectionPipeline(cfg)
    fails = []
    for f in files:
        img = imread_tr(f)
        if img is None:
            continue
        r = pipe.inspect(img, os.path.basename(f))
        if r.status != "ok":
            fails.append(f"{os.path.basename(f)} → {r.verdict}"
                         + (f" ({r.reasons[0]})" if r.reasons else ""))
    cfg.selftest_ok = not fails
    if ayar_yolu:
        cfg.save(ayar_yolu)
    if fails:
        msg += ("\n⚠ ÖZ-TEST UYARISI: altın numune(ler) sağlam çıkmadı → "
                + " | ".join(fails)
                + "\n  Bu kalibrasyonla karar verme; fotoğraf/ışık koşullarını "
                  "düzeltip yeniden kalibre et.")
    else:
        msg += f"\n✓ Öz-test: {len(files)} altın numunenin tamamı SAĞLAM çıktı."
    return True, msg
