"""GÖZCÜ·AI — çok-stratejili dayanıklı segmentasyon.

Tek bir eşikleme yöntemi gerçek fabrika koşullarında (dokulu zemin,
gün içi ışık kayması, benzer parlaklıkta parça/zemin, gölge) kırılgandır.
Bu modül parçayı BEŞ bağımsız stratejiyle arar ve her adayı
"gerçekten parça olma" kalitesine göre puanlar; en iyi aday kazanır:

  A) Işık-düzeltmeli global eşik (Otsu, iki kutup)   — temiz sahneler
  B) Yerel uyarlanabilir eşik (iki kutup)            — düzensiz aydınlatma
  C) Kenar tabanlı (Canny + kapama + doldurma)       — renkten bağımsız
  D) Hough daire + yerel rafineri                    — dokulu zeminde daire
  E) Renk-uzayı ayrımı (Lab, zemin modeli kenardan)  — gri-benzer/renk-farklı

Puan: dairesellik + doluluk + sınır kontrastı + kenara-değmeme.
Hiçbir aday yeterince iyi değilse None döner (üst katman ŞÜPHELİ der;
sistem tahmin etmez).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

MIN_SCORE = 0.55          # bu puanın altındaki en iyi aday bile reddedilir
_KO = np.ones((5, 5), np.uint8)
_KC = np.ones((9, 9), np.uint8)


# ── yardımcılar ──────────────────────────────────────────────────────

def _flatfield(gray: np.ndarray) -> np.ndarray:
    """Yavaş değişen aydınlatmayı düzelt (arka plan 1/8 ölçekte — hızlı)."""
    small = cv2.resize(gray, None, fx=0.125, fy=0.125,
                       interpolation=cv2.INTER_AREA)
    bg_s = cv2.GaussianBlur(small, (0, 0), sigmaX=max(small.shape) / 8)
    bg = cv2.resize(bg_s, (gray.shape[1], gray.shape[0]),
                    interpolation=cv2.INTER_LINEAR)
    norm = gray.astype(np.float32) / np.maximum(bg.astype(np.float32), 1.0) * 128.0
    return np.clip(norm, 0, 255).astype(np.uint8)


def _clean(mask: np.ndarray) -> np.ndarray:
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _KO)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, _KC)


def _contours_of(mask: np.ndarray, max_n: int = 2) -> List[np.ndarray]:
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cs = sorted(cs, key=cv2.contourArea, reverse=True)
    return cs[:max_n]


def _sobel_mag(gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


# ── aday üreticiler ──────────────────────────────────────────────────

def _cand_otsu(ff: np.ndarray) -> List[np.ndarray]:
    out = []
    _, m = cv2.threshold(ff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    out += _contours_of(_clean(m))
    out += _contours_of(_clean(cv2.bitwise_not(m)))
    return out


def _cand_adaptive(ff: np.ndarray) -> List[np.ndarray]:
    out = []
    bs = max(51, (min(ff.shape) // 8) | 1)
    for inv in (cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV):
        m = cv2.adaptiveThreshold(ff, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  inv, bs, 5)
        out += _contours_of(_clean(m))
    return out


def _cand_edges(gray: np.ndarray) -> List[np.ndarray]:
    v = float(np.median(gray))
    e = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0),
                  max(10, 0.66 * v), max(30, 1.33 * v))
    e = cv2.dilate(e, np.ones((3, 3), np.uint8), iterations=2)
    e = cv2.morphologyEx(e, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    # dıştan taşırma-doldurma: kenar haritasında kapalı bölgeler nesne olur
    h, w = e.shape
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
    fill = e.copy()
    cv2.floodFill(fill, ff_mask, (0, 0), 255)
    inside = cv2.bitwise_not(fill) | e
    return _contours_of(_clean(inside))


def _cand_hough(gray: np.ndarray, ff: np.ndarray) -> List[np.ndarray]:
    """Hough daireyi KONUMLAYICI olarak kullan; gerçek sınırı, dairenin
    çevresindeki yerel istatistiklerle (iç=parça, dış=zemin) çıkar.
    Dokulu zeminlerde en güçlü strateji budur."""
    h, w = gray.shape
    small = cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    sm = cv2.medianBlur(small, 5)
    circles = cv2.HoughCircles(sm, cv2.HOUGH_GRADIENT, dp=1.2,
                               minDist=min(small.shape) / 2,
                               param1=120, param2=40,
                               minRadius=int(min(small.shape) * 0.10),
                               maxRadius=int(min(small.shape) * 0.48))
    out: List[np.ndarray] = []
    if circles is None:
        return out
    for cx, cy, r in circles[0][:2]:
        cx, cy, r = cx * 2, cy * 2, r * 2
        x0, y0 = int(max(cx - 1.35 * r, 0)), int(max(cy - 1.35 * r, 0))
        x1, y1 = int(min(cx + 1.35 * r, w)), int(min(cy + 1.35 * r, h))
        roi = ff[y0:y1, x0:x1]
        if roi.size == 0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.hypot(xx - cx, yy - cy)
        ic, oc = roi[d < r * 0.75], roi[(d > r * 1.12) & (d < r * 1.35)]
        if ic.size < 50 or oc.size < 50:
            continue
        mi, mo = float(np.median(ic)), float(np.median(oc))
        if abs(mi - mo) < 6:          # iç/dış ayrımı yoksa güvenme
            continue
        t = (mi + mo) / 2.0
        m = ((roi > t) if mi > mo else (roi < t)).astype(np.uint8) * 255
        m[d > r * 1.25] = 0           # daire dışına taşmayı engelle
        full = np.zeros_like(gray)
        full[y0:y1, x0:x1] = _clean(m)
        out += _contours_of(full, 1)
    return out


def _cand_color(bgr: np.ndarray) -> List[np.ndarray]:
    """Zemin rengini kenar şeridinden öğren; ondan uzak pikseller parça.
    Gri tonda benzeşen ama renkte farklı parça/zemin için (mavi kapak
    kahverengi ahşapta) kritik strateji."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    b = max(8, min(h, w) // 25)
    strip = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3),
                            lab[:, :b].reshape(-1, 3),
                            lab[:, -b:].reshape(-1, 3)])
    mu = strip.mean(axis=0)
    sd = strip.std(axis=0) + 1e-3
    dist = np.sqrt((((lab - mu) / sd) ** 2).sum(axis=2))
    thr = max(4.0, float(np.percentile(dist[:b], 99)) * 1.15)
    m = (dist > thr).astype(np.uint8) * 255
    return _contours_of(_clean(m))


# ── aday puanlama ───────────────────────────────────────────────────

def _score(cnt: np.ndarray, gray: np.ndarray,
           mag: np.ndarray) -> Tuple[float, dict]:
    h, w = gray.shape
    A = cv2.contourArea(cnt)
    if A < 1200 or A > 0.85 * h * w:
        return 0.0, {}
    P = cv2.arcLength(cnt, True)
    circ = min(1.0, 4 * np.pi * A / max(P * P, 1e-6))
    hull = cv2.convexHull(cnt)
    solidity = A / max(cv2.contourArea(hull), 1e-6)
    x, y, bw, bh = cv2.boundingRect(cnt)
    touches = x <= 2 or y <= 2 or x + bw >= w - 2 or y + bh >= h - 2
    pts = cnt.reshape(-1, 2)[::max(1, len(cnt) // 160)]
    pys = np.clip(pts[:, 1], 0, h - 1)
    pxs = np.clip(pts[:, 0], 0, w - 1)
    contrast = min(1.0, float(mag[pys, pxs].mean()) / 45.0)
    score = (0.42 * circ + 0.18 * solidity + 0.32 * contrast
             + (0.0 if touches else 0.08))
    return score, dict(circ=circ, sol=solidity, con=contrast, touch=touches)


def find_part(bgr: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray, float]]:
    """Parçanın dış konturunu bul.

    Döndürür: (kontur, seçilen_yöntemin_maskesi_için_kontur_dolgusu_ile
    uyumlu ikili maske, ikinci_nesne_oranı) — ya da None."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ff = _flatfield(gray)
    mag = _sobel_mag(cv2.GaussianBlur(gray, (5, 5), 0))

    # KADEMELİ arama: ucuz stratejiler önce; aday yeterince iyiyse
    # (temiz sahne — üretim hattının normali) pahalılar hiç çalışmaz.
    EARLY = 0.80
    stages = [lambda: _cand_otsu(ff),
              lambda: _cand_color(bgr),
              lambda: _cand_adaptive(ff),
              lambda: _cand_edges(gray),
              lambda: _cand_hough(gray, ff)]
    best, best_s = None, 0.0
    scored: List[Tuple[float, np.ndarray, dict]] = []
    for stage in stages:
        for c in stage():
            s, f = _score(c, gray, mag)
            if s > 0:
                scored.append((s, c, f))
            if s > best_s:
                best, best_s = c, s
        if best_s >= EARLY:
            break
    if best is None or best_s < MIN_SCORE:
        return None

    # ── kapsama kuralı: parça, EN DIŞTAKİ makul nesnedir ──
    # Bir aday, başka bir makul adayın içindeyse (örn. delik), o parça
    # değil parçanın bir özelliğidir; dıştaki tercih edilir. Bu, kenarı
    # kesik parçalarda deliğin "daha güzel daire" diye kazanmasını önler.
    plausible = [(s, c) for s, c, _f in scored if s >= MIN_SCORE - 0.05]
    def inside(inner, outer):
        m = cv2.moments(inner)
        if m["m00"] == 0:
            return False
        cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
        return (cv2.pointPolygonTest(outer, (cx, cy), False) > 0
                and cv2.contourArea(inner) < 0.5 * cv2.contourArea(outer))
    outermost = []
    for s, c in plausible:
        if not any(inside(c, o) for so, o in plausible if o is not c):
            outermost.append((s, c))
    if outermost:
        best_s, best = max(outermost, key=lambda t: t[0])

    # ikinci nesne oranı: kazananla örtüşmeyen en büyük diğer aday
    bx, by, bw_, bh_ = cv2.boundingRect(best)
    bA = cv2.contourArea(best)
    second = 0.0
    for s, c, f in scored:
        # "ikinci nesne" ancak KENDİSİ de parça-benzeriyse sayılır:
        # yüksek puan + yüksek dairesellik. El, gölge, zemin deseni gibi
        # düşük-dairesellikli lekeler kadraj uyarısı üretmez.
        if c is best or s < MIN_SCORE or f.get("circ", 0) < 0.60:
            continue
        x, y, ww, hh = cv2.boundingRect(c)
        ix = max(0, min(bx + bw_, x + ww) - max(bx, x))
        iy = max(0, min(by + bh_, y + hh) - max(by, y))
        overlap = (ix * iy) / max(min(bw_ * bh_, ww * hh), 1)
        if overlap < 0.25:
            second = max(second, cv2.contourArea(c) / max(bA, 1))
    return best, gray, min(second, 1.0)


# ── perspektif/eğim düzeltme ve el tespiti ──────────────────────────

def tilt_of(cnt: np.ndarray) -> Tuple[float, float, Tuple]:
    """Konturun eğimini ölç: (eksen oranı ma/MA, açı, elips).
    Elips, aykırılardan arınmış iç bant noktalarına uydurulur ki
    gerçek kusurlar (çentik/çapak) eğim ölçümünü bozmasın."""
    pts = cnt.reshape(-1, 2).astype(np.float32)
    if len(pts) < 20:
        return 1.0, 0.0, None
    c = pts.mean(axis=0)
    d = np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1])
    med = float(np.median(d))
    inl = pts[np.abs(d - med) < max(0.08 * med, 4.0)]
    if len(inl) < 20:
        inl = pts
    (ex, ey), (MA, ma), ang = cv2.fitEllipse(inl)
    if MA < ma:
        MA, ma = ma, MA
        ang += 90.0
    return float(ma / max(MA, 1e-6)), float(ang), ((ex, ey), (MA, ma), ang)


def rectify_tilt(bgr: np.ndarray, cnt: np.ndarray,
                 min_ratio: float = 0.80) -> Optional[np.ndarray]:
    """Hafif eğik çekilmiş görüntüyü dikleştir (elips → daire).

    Eksen oranı %98'in üstündeyse dokunulmaz; %80'in altındaysa
    (çok yatık açı) None döner — üst katman ŞÜPHELİ der."""
    ratio, ang, ell = tilt_of(cnt)
    if ell is None or ratio < min_ratio:
        return None if ratio < min_ratio else bgr
    if ratio > 0.985:
        return bgr
    (ex, ey) = ell[0]
    th = np.deg2rad(ang)
    c, s = np.cos(th), np.sin(th)
    R = np.array([[c, s], [-s, c]])
    S = np.array([[1.0, 0.0], [0.0, 1.0 / ratio]])   # kısa ekseni uzat
    A = R.T @ S @ R
    M = np.hstack([A, (np.array([ex, ey]) - A @ np.array([ex, ey])).reshape(2, 1)])
    return cv2.warpAffine(bgr, M, (bgr.shape[1], bgr.shape[0]),
                          flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

