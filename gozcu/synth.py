"""GÖZCÜ·AI — sentetik parça görüntüsü üreteci (demo, simülasyon ve testler için).

Kamerayla çekilmiş gibi görünen yuvarlak enjeksiyon parçası üretir:
koyu zemin, açık gri parça, merkez delik, hafif doku ve gürültü.
Hatalar programatik enjekte edilir; böylece dedektörlerin gerçekten
çalıştığı kanıtlanabilir (yer bilgisi bizde, tespit motorda).
"""
from __future__ import annotations

import numpy as np
import cv2

IMG = 480
CX = CY = IMG // 2
R_OUT = 170
R_HOLE = 45
RNG = np.random.default_rng(42)


def _base_part(rng) -> np.ndarray:
    """Sağlam parça: zemin + gövde + delik + doku + gürültü + vinyet."""
    img = np.full((IMG, IMG), 38, np.uint8)                      # koyu zemin
    cv2.circle(img, (CX, CY), R_OUT, 168, -1)                    # gövde
    cv2.circle(img, (CX, CY), R_HOLE, 38, -1)                    # delik
    # hafif radyal aydınlatma (vinyet) — gerçek kamera hissi
    yy, xx = np.mgrid[0:IMG, 0:IMG]
    d = np.hypot(xx - CX, yy - CY) / R_OUT
    shade = np.clip(1.0 - 0.10 * d ** 2, 0.85, 1.0)
    img = np.clip(img.astype(np.float64) * shade, 0, 255)
    # ince yüzey dokusu + sensör gürültüsü
    img += rng.normal(0, 2.2, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def _inject_flash(img, rng):
    """Çapak: dış kenardan dışarı taşan düzensiz lob (gövdeye yapışık)."""
    ang = rng.uniform(0, 2 * np.pi)
    n_pts = 7
    pts = []
    for i in range(n_pts):
        a = ang + (i - n_pts // 2) * 0.055
        # taban noktaları parça İÇİNDEN başlar ki lob gövdeyle kaynaşsın
        rr = (R_OUT - 4) if i in (0, n_pts - 1) else R_OUT + rng.uniform(14, 26)
        pts.append((CX + rr * np.cos(a), CY + rr * np.sin(a)))
    cv2.fillPoly(img, [np.array(pts, np.int32)], 165)
    return "capak"


def _inject_chip(img, rng):
    """Kırık/çentik: kenardan zemin renginde kama."""
    ang = rng.uniform(0, 2 * np.pi)
    depth = rng.uniform(14, 24)
    width = 0.16
    pts = [(CX + (R_OUT + 8) * np.cos(ang - width),
            CY + (R_OUT + 8) * np.sin(ang - width)),
           (CX + (R_OUT + 8) * np.cos(ang + width),
            CY + (R_OUT + 8) * np.sin(ang + width)),
           (CX + (R_OUT - depth) * np.cos(ang),
            CY + (R_OUT - depth) * np.sin(ang))]
    cv2.fillPoly(img, [np.array(pts, np.int32)], 38)
    return "kirik"


def _inject_scratch(img, rng):
    """Çizik: yüzeyde ince koyu çizgi."""
    ang = rng.uniform(0, 2 * np.pi)
    r0 = rng.uniform(R_HOLE + 25, R_OUT - 70)
    length = rng.uniform(55, 100)
    a2 = ang + rng.uniform(-0.5, 0.5)
    p1 = (int(CX + r0 * np.cos(ang)), int(CY + r0 * np.sin(ang)))
    p2 = (int(p1[0] + length * np.cos(a2)), int(p1[1] + length * np.sin(a2)))
    cv2.line(img, p1, p2, 132, 2, cv2.LINE_AA)
    return "cizik"


def _inject_stain(img, rng):
    """Leke: yüzeyde koyu eliptik bölge."""
    ang = rng.uniform(0, 2 * np.pi)
    r0 = rng.uniform(R_HOLE + 35, R_OUT - 50)
    c = (int(CX + r0 * np.cos(ang)), int(CY + r0 * np.sin(ang)))
    axes = (int(rng.uniform(12, 20)), int(rng.uniform(9, 15)))
    cv2.ellipse(img, c, axes, rng.uniform(0, 180), 0, 360, 143, -1)
    return "leke"


def _inject_short(img, rng):
    """Eksik dolum: parçadan büyük bir dilim eksik."""
    ang = rng.uniform(0, 2 * np.pi)
    mask = np.zeros_like(img)
    cv2.ellipse(mask, (CX, CY), (R_OUT + 12, R_OUT + 12), 0,
                np.degrees(ang), np.degrees(ang) + 70, 255, -1)
    img[mask > 0] = 38
    return "eksik_dolum"


INJECTORS = [_inject_flash, _inject_chip, _inject_scratch,
             _inject_stain, _inject_short]


TURLER = {"capak": _inject_flash, "kirik": _inject_chip, "cizik": _inject_scratch,
          "leke": _inject_stain, "eksik_dolum": _inject_short}


def make_sample(kind: str = "good", rng=None):
    """Tek örnek üret: kind ∈ good|capak|kirik|cizik|leke|eksik_dolum|karma."""
    if rng is None:
        rng = RNG
    if kind not in TURLER and kind not in ("good", "karma"):
        raise ValueError(f"Bilinmeyen tür: {kind}")
    img = _base_part(rng)
    injected = []
    if kind == "karma":
        for f in rng.choice(INJECTORS, size=2, replace=False):
            injected.append(f(img, rng))
    elif kind in TURLER:
        injected.append(TURLER[kind](img, rng))
    # son gürültü katmanı (enjeksiyon izlerini yumuşat)
    img = np.clip(img.astype(np.float64) + rng.normal(0, 1.5, img.shape),
                  0, 255).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), injected


def make_batch(spec, tohum: int = 42):
    """spec: [(kind, adet), ...] → [(ad, bgr, gerçek_hatalar)].
    Her çağrı kendi tohumuyla başlar: aynı spec her zaman aynı partiyi üretir."""
    rng = np.random.default_rng(tohum)
    out = []
    idx = 1
    for kind, count in spec:
        for _ in range(count):
            img, injected = make_sample(kind, rng)
            out.append((f"parca_{idx:03d}_{kind}", img, injected))
            idx += 1
    return out
