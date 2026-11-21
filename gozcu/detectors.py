"""GÖZCÜ·AI — hata dedektörleri.

Her dedektör bağımsızdır ve Defect listesi döndürür. Yaklaşım klasik
görüntü işlemedir (kontur geometrisi + yüzey analizi); derin öğrenme
tabanlı anomali modeli, aynı Defect arayüzüyle sonradan eklenebilir.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .config import InspectionConfig


@dataclass
class Defect:
    kind: str                        # 'capak' | 'kirik' | 'cizik' | 'leke' | 'eksik_dolum' | 'delik'
    label: str                       # insan-okur Türkçe ad
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    severity: float                  # 0..1 arası şiddet
    detail: str = ""
    strong: bool = True              # eşiği net aşan bulgu mu (False → sınırda)


@dataclass
class Segmentation:
    material_mask: np.ndarray   # yalnız malzeme pikselleri (delik hariç)
    outer_contour: np.ndarray   # dış kontur
    center: Tuple[float, float]
    radius: float
    second_ratio: float = 0.0   # ikinci büyük nesnenin alan oranı (çoklu parça uyarısı)


# ── segmentasyon ─────────────────────────────────────────────────────

def _kasa_fit(pts: np.ndarray) -> Tuple[float, float, float]:
    """Kåsa cebirsel çember uydurması (doğrusal en küçük kareler).
    Kısmi yaylarda (örn. 270°) bile gerçek merkezi doğru bulur —
    nokta ortalaması gibi yaya doğru kaymaz."""
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0] / 2.0, sol[1] / 2.0
    r = float(np.sqrt(max(sol[2] + cx * cx + cy * cy, 1e-9)))
    return float(cx), float(cy), r


def _robust_circle(cnt: np.ndarray) -> Tuple[Tuple[float, float], float]:
    """Aykırıya dayanıklı çember uydurma.

    Sorunlu iki uç durum vardır: (1) minEnclosingCircle çapağa aldanır,
    (2) nokta-ortalamasıyla merkezleme, büyük bir dilim eksikken (eksik
    dolum) kalan yaya doğru kayar. Çözüm: Kåsa cebirsel uydurma +
    yinelemeli aykırı dışlama — kusurlu azınlık noktalar (çapak lobu,
    kesik kenarları) elenir, kalan yay gerçek çemberi tanımlar."""
    pts = cnt.reshape(-1, 2).astype(np.float64)
    cx, cy, _ = _kasa_fit(pts)
    for _ in range(4):
        d = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        med = float(np.median(d))
        # bandı uydurulan yarıçapa değil MEDYANA demirle: çoğunluk yayı
        # medyanı her zaman yakalar; kesik kenarları/çapak azınlıkta kalır
        inl = np.abs(d - med) < max(0.07 * med, 5.0)
        if inl.sum() < 16:
            break
        cx, cy, _ = _kasa_fit(pts[inl])
    d = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    med = float(np.median(d))
    band = np.abs(d - med) < max(0.07 * med, 5.0)
    r_final = float(np.median(d[band])) if band.sum() >= 16 else med
    return (cx, cy), r_final


def _material_from(gray: np.ndarray, cnt: np.ndarray,
                   outer_fill: np.ndarray) -> np.ndarray:
    """Malzeme maskesi: dış kontur içinden delikleri/boşlukları ayıkla.

    Delikler, parçanın arkasındaki ZEMİNİ gösterir. Zemin istatistiği
    kontur dışındaki halkadan alınır; iç bölge Otsu ile ikiye bölünür ve
    zemine benzeyen sınıf (belirgin fark varsa) delik sayılıp çıkarılır.
    Zeminden bağımsız çalışır (ahşap, renkli, açık/koyu fark etmez)."""
    inner = gray[outer_fill > 0]
    if inner.size < 400:
        return outer_fill.copy()
    ring = cv2.dilate(outer_fill, np.ones((25, 25), np.uint8)) & ~outer_fill
    bg_vals = gray[ring > 0]
    bg_med = float(np.median(bg_vals)) if bg_vals.size > 50 else None
    t, _ = cv2.threshold(inner, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    lo, hi = inner[inner <= t], inner[inner > t]
    if lo.size < 60 or hi.size < 60:
        return outer_fill.copy()
    m_lo, m_hi = float(np.median(lo)), float(np.median(hi))
    if abs(m_hi - m_lo) < 14 or bg_med is None:
        return outer_fill.copy()          # tek düze iç: delik yok
    # zemine benzeyen sınıf delik adayıdır
    hole_is_lo = abs(m_lo - bg_med) + 8 < abs(m_hi - bg_med)
    hole_is_hi = abs(m_hi - bg_med) + 8 < abs(m_lo - bg_med)
    if not (hole_is_lo or hole_is_hi):
        return outer_fill.copy()
    if hole_is_lo:
        mat = ((gray > t).astype(np.uint8) * 255) & outer_fill
    else:
        mat = ((gray <= t).astype(np.uint8) * 255) & outer_fill
    mat = cv2.morphologyEx(mat, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    # ayıklama aşırıya kaçtıysa (malzeme yarıdan aza indiyse) güvenli tarafta kal
    if np.count_nonzero(mat) < 0.45 * np.count_nonzero(outer_fill):
        return outer_fill.copy()
    return mat


def segment_part(image: np.ndarray, cfg: InspectionConfig) -> Optional[Segmentation]:
    """Parçayı zeminden ayır — çok-stratejili dayanıklı segmentasyon.

    'image' BGR ya da gri olabilir. Zemin kutupluluğu (açık/koyu) aday
    puanlamasıyla kendiliğinden çözülür; zemin rengi/dokusu ve ışıktan bağımsız."""
    from .segmentation import find_part
    bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    found = find_part(bgr)
    if found is None:
        return None
    cnt, gray, second_ratio = found
    (cx, cy), r = _robust_circle(cnt)
    outer_fill = np.zeros(gray.shape, np.uint8)
    cv2.drawContours(outer_fill, [cnt], -1, 255, -1)
    material = _material_from(gray, cnt, outer_fill)
    return Segmentation(material, cnt, (float(cx), float(cy)), float(r),
                        float(second_ratio))


# ── yardımcı: kontur üzerindeki bayraklı koşuları hataya çevir ───────

def _close_flags(flags: np.ndarray, gap: int = 9) -> np.ndarray:
    """Dairesel 1B kapama: bayrak dizisindeki ≤gap uzunluğundaki
    boşlukları doldurur — tek fiziksel kusurun gürültüyle parçalara
    bölünüp birden çok sayılmasını önler."""
    if not flags.any() or flags.all():
        return flags
    n = len(flags)
    ext = np.concatenate([flags, flags, flags]).astype(np.uint8)
    k = np.ones(gap, np.uint8)
    dil = np.convolve(ext, k, mode="same") > 0
    ero = np.convolve((~dil).astype(np.uint8), k, mode="same") == 0
    return ero[n:2 * n]


def _runs_to_defects(pts: np.ndarray, flags: np.ndarray, min_run: int,
                     kind: str, label: str, sev_scale: float,
                     dev: Optional[np.ndarray] = None,
                     min_depth: float = 0.0) -> List[Defect]:
    """dev verilirse her koşunun tepe sapması (px) ölçülür ve
    min_depth altındaki sığ koşular (tolerans bandı artefaktları) elenir."""
    flags = _close_flags(flags)
    n = len(flags)
    if n == 0 or not flags.any():
        return []
    if flags.all():
        start = 0
    else:
        start = int(np.where(~flags)[0][0])
    order = np.arange(start, start + n) % n
    f, p = flags[order], pts[order]
    dv = dev[order] if dev is not None else None
    defects: List[Defect] = []
    i = 0
    while i < n:
        if f[i]:
            j = i
            while j < n and f[j]:
                j += 1
            run = p[i:j]
            depth = float(np.abs(dv[i:j]).max()) if dv is not None else 0.0
            if len(run) >= min_run and depth >= min_depth:
                x, y, w, h = cv2.boundingRect(run.astype(np.int32))
                sev = min(1.0, len(run) / (min_run * sev_scale))
                detail = f"{len(run)} px kontur sapması"
                strong = True
                if dv is not None:
                    detail += f", derinlik {depth:.0f}px"
                    strong = depth >= min_depth * 1.4 and len(run) >= min_run * 1.5
                defects.append(Defect(kind, label, (x, y, w, h), sev, detail, strong))
            i = j
        else:
            i += 1
    return defects


# ── dedektörler ──────────────────────────────────────────────────────

def edge_measurability(gray: np.ndarray, seg: Segmentation,
                       probe: int = 5) -> np.ndarray:
    """Her kontur noktası için kenar ÖLÇÜLEBİLİR mi? (bool dizi)

    Parmak teması, gölge ya da yerel zemin-benzeşmesi olan yaylarda
    iç/dış parlaklık farkı kaybolur; o kenar fiziksel olarak ölçülemez.
    Ölçüm = |dış örnek − iç örnek| radyal yönde."""
    h, w = gray.shape
    pts = seg.outer_contour.reshape(-1, 2).astype(np.float64)
    c = np.array(seg.center)
    v = pts - c
    n = np.linalg.norm(v, axis=1, keepdims=True)
    u = v / np.maximum(n, 1e-6)
    po = np.clip(pts + u * probe, [0, 0], [w - 1, h - 1]).astype(int)
    pi = np.clip(pts - u * probe, [0, 0], [w - 1, h - 1]).astype(int)
    g = cv2.GaussianBlur(gray, (3, 3), 0).astype(np.int16)
    contrast = np.abs(g[po[:, 1], po[:, 0]] - g[pi[:, 1], pi[:, 0]])
    med = float(np.median(contrast))
    thr = max(8.0, 0.30 * med)
    return contrast.astype(np.float64) >= thr


def detect_contour_defects(seg: Segmentation, cfg: InspectionConfig,
                           gray: Optional[np.ndarray] = None) -> List[Defect]:
    """Çapak (dışa taşma) ve kırık/çentik (içe çöküntü).

    Not: kontur uzunluğunun %20'sinden büyük içe çöküntüler 'çentik'
    değil eksik dolumdur; onları alan dedektörüne bırakır, burada saymayız.
    """
    ref, th = cfg.reference, cfg.thresholds
    pts = seg.outer_contour.reshape(-1, 2).astype(np.float64)
    d = np.hypot(pts[:, 0] - seg.center[0], pts[:, 1] - seg.center[1])
    dev = d - ref.outer_radius            # +: dışa taşma, −: içe çöküntü
    measurable = (edge_measurability(gray, seg)
                  if gray is not None else np.ones(len(pts), bool))
    tol = ref.radius_tolerance
    min_depth = ref.outer_radius * tol + 2.0   # tolerans bandı + 2px pay
    out: List[Defect] = []
    out += _runs_to_defects(pts, (d > ref.outer_radius * (1 + tol)) & measurable,
                            th.protrusion_min_run, "capak", "Çapak (flash)",
                            6.0, dev=dev, min_depth=min_depth)
    notch_cap = max(int(len(pts) * 0.20), th.notch_min_run + 1)
    notches = _runs_to_defects(pts, (d < ref.outer_radius * (1 - tol)) & measurable,
                               th.notch_min_run, "kirik", "Kırık / çentik",
                               6.0, dev=dev, min_depth=min_depth)
    out += [n for n in notches
            if int(n.detail.split()[0]) <= notch_cap]
    return out


def detect_surface_defects(gray: np.ndarray, seg: Segmentation,
                           cfg: InspectionConfig,
                           bgr: Optional[np.ndarray] = None) -> List[Defect]:
    """Çizik (ince-uzun) ve leke (kompakt).

    İki kanal birlikte taranır:
    1) Parlaklık sapması (gri) — klasik çizik/leke.
    2) Lab KROMA sapması (renk) — parlaklığı aynı ama rengi farklı izler
       (mürekkep, yanık sarısı, yabancı malzeme). Gri analiz bunlara kördür."""
    th = cfg.thresholds
    inner = cv2.erode(seg.material_mask, np.ones((17, 17), np.uint8))
    base = cv2.medianBlur(gray, 51)
    diff = cv2.absdiff(gray, base)
    diff[inner == 0] = 0
    _, dm = cv2.threshold(diff, th.scratch_diff, 255, cv2.THRESH_BINARY)
    if bgr is not None:
        # kroma analizi YARI çözünürlükte: leke ölçeğinde hassasiyet korunur,
        # medyan filtre maliyeti 4'te 1'e iner (Pi için önemli)
        lab = cv2.cvtColor(cv2.resize(bgr, None, fx=0.5, fy=0.5,
                                      interpolation=cv2.INTER_AREA),
                           cv2.COLOR_BGR2LAB)
        a, b = lab[..., 1], lab[..., 2]
        da = cv2.absdiff(a, cv2.medianBlur(a, 25)).astype(np.float32)
        db = cv2.absdiff(b, cv2.medianBlur(b, 25)).astype(np.float32)
        dc = cv2.resize(cv2.sqrt(da * da + db * db),
                        (gray.shape[1], gray.shape[0]),
                        interpolation=cv2.INTER_LINEAR)
        dc[inner == 0] = 0
        cm = (dc > float(getattr(th, "color_diff", 14))).astype(np.uint8) * 255
        dm = cv2.bitwise_or(dm, cm)
        diff = np.maximum(diff, dc.astype(diff.dtype))  # şiddet ölçümü için
    dm = cv2.morphologyEx(dm, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dm)
    out: List[Defect] = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 40:
            continue
        length = int(np.hypot(w, h))            # yönden bağımsız uzunluk
        thickness = area / max(length, 1)       # ortalama kalınlık
        if thickness <= th.scratch_max_thickness and length >= th.scratch_min_len:
            sev = min(1.0, length / (th.scratch_min_len * 4))
            strong = length >= th.scratch_min_len * 1.4
            out.append(Defect("cizik", "Çizik", (x, y, w, h), sev,
                              f"uzunluk {length}px, kalınlık ~{thickness:.1f}px",
                              strong))
        elif area >= th.stain_min_area and thickness > th.scratch_max_thickness:
            comp = np.uint8(labels == i) * 255
            mean_dev = float(cv2.mean(diff, mask=comp)[0])
            if mean_dev >= th.stain_diff * 0.6:
                sev = min(1.0, area / (th.stain_min_area * 5))
                strong = (area >= th.stain_min_area * 1.6
                          or mean_dev >= th.stain_diff * 1.15)
                out.append(Defect("leke", "Leke / renk kusuru", (x, y, w, h), sev,
                                  f"alan {area}px², sapma {mean_dev:.0f}", strong))
    return out


def detect_fill_and_hole(seg: Segmentation, cfg: InspectionConfig) -> List[Defect]:
    """Eksik dolum (malzeme alanı) ve merkez delik kontrolü."""
    ref, th = cfg.reference, cfg.thresholds
    out: List[Defect] = []
    hole_r = ref.hole_radius if ref.hole_expected else 0.0
    expected = np.pi * (ref.outer_radius ** 2 - hole_r ** 2)
    actual = float(np.count_nonzero(seg.material_mask))
    ratio = actual / expected
    if ratio < th.short_shot_area_ratio:
        x, y, w, h = cv2.boundingRect(seg.outer_contour)
        out.append(Defect("eksik_dolum", "Eksik dolum (short shot)",
                          (x, y, w, h), min(1.0, (1 - ratio) * 4),
                          f"dolum oranı %{ratio * 100:.1f}"))
    if ref.hole_expected:
        cx, cy = int(seg.center[0]), int(seg.center[1])
        r = int(ref.hole_radius * 0.6)
        roi = seg.material_mask[max(cy - r, 0):cy + r, max(cx - r, 0):cx + r]
        if roi.size and float(np.count_nonzero(roi)) / roi.size > 0.5:
            out.append(Defect("delik", "Merkez delik kapalı/eksik",
                              (cx - r, cy - r, 2 * r, 2 * r), 0.9,
                              "delik bölgesi dolu görünüyor"))
        else:
            # delik VAR — geometrisi doğru mu? (maça kayması = kaçık delik,
            # aşınmış maça = ölçü-dışı delik; enjeksiyonun klasik hataları)
            outer_fill = np.zeros_like(seg.material_mask)
            cv2.drawContours(outer_fill, [seg.outer_contour], -1, 255, -1)
            voids = cv2.bitwise_and(outer_fill,
                                    cv2.bitwise_not(seg.material_mask))
            n, lab, stats, cents = cv2.connectedComponentsWithStats(voids)
            # beklenen deliğin çeyreğinden küçük boşluklar (kenar kırıntısı vb.) delik adayı değildir
            asgari = 0.25 * np.pi * ref.hole_radius ** 2
            if n > 1 and stats[1:, 4].max() >= asgari:
                big = 1 + int(np.argmax(stats[1:, 4]))
                area = float(stats[big, 4])
                hx, hy = cents[big]
                r_eq = float(np.sqrt(area / np.pi))
                off = float(np.hypot(hx - seg.center[0], hy - seg.center[1]))
                x, y, w, h = [int(v) for v in stats[big, :4]]
                off_tol = max(0.30 * ref.hole_radius, 6.0)
                if off > off_tol:
                    out.append(Defect("delik", "Delik kaçık (merkezden sapmış)",
                                      (x, y, w, h),
                                      min(1.0, off / (2 * off_tol)),
                                      f"sapma {off:.0f}px (izin {off_tol:.0f}px)"))
                if ref.hole_radius > 0 and                         abs(r_eq - ref.hole_radius) / ref.hole_radius > 0.25:
                    out.append(Defect("delik", "Delik ölçü dışı",
                                      (x, y, w, h),
                                      min(1.0, abs(r_eq - ref.hole_radius)
                                          / ref.hole_radius),
                                      f"yarıçap {r_eq:.0f}px "
                                      f"(beklenen {ref.hole_radius:.0f}px)"))
    return out
