import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _ahsap(rng, h=620, w=620):
    """Ahşap masa dokusu: damarlar + renk dalgalanması."""
    taban = rng.normal(0, 1, (h, w)).astype(np.float32)
    damar = cv2.GaussianBlur(taban, (151, 7), 0) * 3
    lif = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (31, 3), 0)
    t = 1 + 0.12 * damar + 0.08 * lif
    return cv2.merge([np.clip(70 * t, 0, 255), np.clip(105 * t, 0, 255),
                      np.clip(150 * t, 0, 255)]).astype(np.uint8)


def _kapak(zemin, cx, cy, r, rng, renk=(205, 195, 180), kusur=None, delik=False):
    img = zemin.copy().astype(np.float32)
    yy, xx = np.mgrid[0:zemin.shape[0], 0:zemin.shape[1]]
    d = np.hypot(xx - cx, yy - cy)
    m = d < r
    golge = np.clip(1 - 0.10 * (d / r) ** 2, 0.88, 1.0)
    for i, c in enumerate(renk):
        kanal = img[..., i]
        kanal[m] = c * golge[m]
    img = np.clip(img + rng.normal(0, 2, img.shape), 0, 255).astype(np.uint8)
    if delik:
        cv2.circle(img, (cx, cy), int(r * 0.26), zemin[cy, cx].tolist(), -1)
    if kusur == "kirik":
        a = 1.1
        pts = np.array([(cx + (r + 8) * np.cos(a - 0.15), cy + (r + 8) * np.sin(a - 0.15)),
                        (cx + (r + 8) * np.cos(a + 0.15), cy + (r + 8) * np.sin(a + 0.15)),
                        (cx + (r - 22) * np.cos(a), cy + (r - 22) * np.sin(a))], np.int32)
        maske = np.zeros(zemin.shape[:2], np.uint8)
        cv2.fillPoly(maske, [pts], 255)
        img[maske > 0] = zemin[maske > 0]
    if kusur == "cizik":
        cv2.line(img, (cx - 55, cy - 8), (cx + 60, cy + 14), (150, 140, 128), 3, cv2.LINE_AA)
    return img


@pytest.fixture
def rng():
    return np.random.default_rng(9)


@pytest.fixture
def ahsap():
    return _ahsap


@pytest.fixture
def kapak():
    return _kapak
