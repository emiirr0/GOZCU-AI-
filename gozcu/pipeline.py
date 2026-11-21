"""GÖZCÜ·AI — sınıflandırıcı, sayaçlar, ana hat ve raporlama."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import cv2
import numpy as np

from .config import InspectionConfig
from .detectors import (Defect, Segmentation, detect_contour_defects,
                        detect_fill_and_hole, detect_surface_defects,
                        edge_measurability, segment_part)
from .segmentation import rectify_tilt, tilt_of

KIND_COLORS = {
    "capak": (0, 165, 255),      # turuncu
    "kirik": (0, 0, 230),        # kırmızı
    "cizik": (0, 255, 255),      # sarı
    "leke": (255, 0, 200),       # mor
    "eksik_dolum": (0, 0, 160),  # koyu kırmızı
    "delik": (255, 128, 0),      # mavi
}
# uygunluk skoru taban cezaları (şiddetle ölçeklenir)
PENALTY = {"eksik_dolum": 50, "delik": 45, "kirik": 28,
           "capak": 22, "leke": 16, "cizik": 12}

KIND_LABELS = {
    "capak": "Çapak", "kirik": "Kırık", "cizik": "Çizik",
    "leke": "Leke", "eksik_dolum": "Eksik dolum", "delik": "Delik",
}


@dataclass
class InspectionResult:
    ok: bool                      # yalnız SAĞLAM ise True
    defects: List[Defect]
    reasons: List[str]
    segmentation: Optional[Segmentation]
    image_name: str = ""
    normalized_image: Optional[np.ndarray] = None  # işaretleme bu ölçekte yapılır
    status: str = "ok"            # "ok" | "suspect" | "reject"
    score: float = 100.0          # uygunluk skoru (%0-100)
    tolerated: List[Defect] = field(default_factory=list)  # politikayla yok sayılanlar

    @property
    def verdict(self) -> str:
        return {"ok": "SAĞLAM", "suspect": "ŞÜPHELİ",
                "reject": "FİRE"}[self.status]


@dataclass
class Counters:
    """Üretim sayaçları: toplam, sağlam, şüpheli, fire ve tür kırılımı.

    ŞÜPHELİ ayrı sayılır: ne sağlamdır ne fire — insan kontrolü bekler.
    Güvenli taraf ilkesi: emin olunmayan parça asla 'sağlam' sayılmaz."""
    total: int = 0
    good: int = 0
    scrap: int = 0
    suspect: int = 0
    by_kind: Dict[str, int] = field(default_factory=dict)

    def add(self, result: InspectionResult) -> None:
        self.total += 1
        if result.status == "ok":
            self.good += 1
        elif result.status == "suspect":
            self.suspect += 1
        else:
            self.scrap += 1
            for kind in sorted({d.kind for d in result.defects}):
                self.by_kind[kind] = self.by_kind.get(kind, 0) + 1

    @property
    def scrap_rate(self) -> float:
        return (self.scrap / self.total * 100) if self.total else 0.0

    def summary_tr(self) -> str:
        lines = [f"Toplam: {self.total}  ·  Sağlam: {self.good}  ·  "
                 f"Şüpheli: {self.suspect}  ·  Fire: {self.scrap}  ·  "
                 f"Fire oranı: %{self.scrap_rate:.1f}"]
        if self.by_kind:
            parts = [f"{KIND_LABELS.get(k, k)}: {v}"
                     for k, v in sorted(self.by_kind.items())]
            lines.append("Hata kırılımı → " + "  |  ".join(parts))
        return "\n".join(lines)


class InspectionPipeline:
    """Tek görüntüyü uçtan uca muayene eder.

    Gerçek fotoğraflar için: zemin kutupluluğu otomatik bulunur ve
    parça, referans ölçeğe normalize edilir (telefon fotoğrafı hangi
    çözünürlükte olursa olsun aynı hassas eşikler geçerli kalır)."""

    MAX_SIDE = 1600  # çok büyük fotoğrafları önce makul boyuta indir

    def __init__(self, config: Optional[InspectionConfig] = None):
        self.cfg = config or InspectionConfig.load()

    def _prepare(self, image_bgr: np.ndarray):
        """Boyut sınırla → zemini çöz → parçayı bul → referans ölçeğe getir."""
        h, w = image_bgr.shape[:2]
        if max(h, w) > self.MAX_SIDE:
            s = self.MAX_SIDE / max(h, w)
            image_bgr = cv2.resize(image_bgr, None, fx=s, fy=s,
                                   interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        # çok-stratejili segmentasyon zemin/kutup/ışık koşulunu kendisi çözer
        seg0 = segment_part(image_bgr, self.cfg)
        if seg0 is None:
            return image_bgr, None, None
        # netlik ÇEKİM ölçeğinde ölçülür (normalizasyon büyütmesi görüntüyü
        # yumuşatır; küçük ama net fotoğraf haksız yere "bulanık" sayılmasın)
        lap0 = cv2.Laplacian(gray, cv2.CV_64F)
        m0 = seg0.material_mask > 0
        sharp0 = float(lap0[m0].var()) if m0.any() else 0.0
        # hafif eğim düzeltme: elips → daire (dik olmayan masa çekimleri)
        tilt0, _, _ = tilt_of(seg0.outer_contour)
        rect = rectify_tilt(image_bgr, seg0.outer_contour)
        if rect is None:
            return image_bgr, seg0, dict(sharp=sharp0,
                                         tilt=tilt0, too_tilted=True)
        if rect is not image_bgr:
            image_bgr = rect
            seg0 = segment_part(image_bgr, self.cfg)
            if seg0 is None:
                return image_bgr, None, None
        scale = self.cfg.reference.outer_radius / max(seg0.radius, 1.0)
        if 0.2 < scale < 5.0 and abs(scale - 1.0) > 0.02:
            image_bgr = cv2.resize(image_bgr, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA
                                   if scale < 1 else cv2.INTER_CUBIC)
            seg0 = segment_part(image_bgr, self.cfg)
        return image_bgr, seg0, dict(sharp=sharp0,
                                     tilt=tilt0, too_tilted=False)

    # ── görüntü kalite kapıları ─────────────────────────────────
    # İlke: karar veremeyecek kadar kötü görüntüde TAHMİN ETME.
    # Böyle parçalar ŞÜPHELİ'dir — ne sağlam sayılır ne fire; insana gider.

    def _quality_gates(self, gray: np.ndarray, seg: Segmentation,
                       sharp0=None) -> List[str]:
        issues: List[str] = []
        h, w = gray.shape
        ref = self.cfg.reference
        hole_r = ref.hole_radius if ref.hole_expected else 0.0
        expected = np.pi * (ref.outer_radius ** 2 - hole_r ** 2)
        if float(np.count_nonzero(seg.material_mask)) < 0.15 * expected:
            return ["Parça bulunamadı ya da çok küçük — kadraj/kontrast kontrol et"]
        x, y, bw, bh = cv2.boundingRect(seg.outer_contour)
        if x <= 2 or y <= 2 or x + bw >= w - 2 or y + bh >= h - 2:
            issues.append("Parça kadrajda kesilmiş — kamerayı/konumu ayarla")
        if seg.second_ratio > 0.25:
            issues.append("Kadrajda birden çok nesne var — tek parça olmalı")
        part = gray[seg.material_mask > 0]
        if part.size:
            m = float(part.mean())
            if m < 35:
                issues.append(f"Görüntü çok karanlık (ort. {m:.0f}) — ışığı artır")
            elif m > 235:
                issues.append(f"Görüntü aşırı pozlanmış (ort. {m:.0f}) — ışığı azalt")
            clipped = float((part >= 250).mean())
            if clipped > 0.08:
                issues.append("Parlama/patlamış bölge var (%%%.0f) — açıyı değiştir"
                              % (clipped * 100))
        if sharp0 is not None:
            sharp = float(sharp0)
        else:
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            sharp = float(lap[seg.material_mask > 0].var()) if part.size else 0.0
        if sharp < 6.0:
            issues.append(f"Görüntü bulanık (netlik {sharp:.1f}) — odağı düzelt")
        return issues

    def _margin_suspects(self, seg: Segmentation) -> List[str]:
        """Kusur bulunmadı ama ölçümler eşiğe tehlikeli yakınsa şüphelen."""
        ref, th = self.cfg.reference, self.cfg.thresholds
        issues: List[str] = []
        hole_r = ref.hole_radius if ref.hole_expected else 0.0
        expected = np.pi * (ref.outer_radius ** 2 - hole_r ** 2)
        ratio = float(np.count_nonzero(seg.material_mask)) / expected
        if th.short_shot_area_ratio <= ratio < th.short_shot_area_ratio + 0.02:
            issues.append(f"Dolum sınırda (%{ratio*100:.1f}) — insan kontrolü önerilir")
        pts = seg.outer_contour.reshape(-1, 2).astype(np.float64)
        d = np.hypot(pts[:, 0] - seg.center[0], pts[:, 1] - seg.center[1])
        min_depth = ref.outer_radius * ref.radius_tolerance + 2.0
        max_dev = float(np.abs(d - ref.outer_radius).max())
        if 0.8 * min_depth <= max_dev < min_depth:
            issues.append(f"Kenar sapması sınırda ({max_dev:.0f}px) — insan kontrolü önerilir")
        return issues

    def inspect(self, image_bgr: np.ndarray, name: str = "") -> InspectionResult:
        image_bgr, seg, meta = self._prepare(image_bgr)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        if seg is None:
            # parça yoksa FİRE DEĞİL, ŞÜPHELİ: görüntü/kurulum sorunu olabilir
            return InspectionResult(False, [],
                                    ["Parça bulunamadı — kontrast/kadraj kontrol et"],
                                    None, name, image_bgr, status="suspect")
        meta = meta or {}
        pre_issues: List[str] = []
        if meta.get("too_tilted"):
            pre_issues.append("Parçaya çok yatık açıyla bakılıyor — kamerayı "
                              "tam tepeden, dik konumlandır")
        if pre_issues:
            return InspectionResult(False, [], pre_issues, seg, name,
                                    image_bgr, status="suspect")
        meas = edge_measurability(gray, seg)
        unmeas = 1.0 - float(meas.mean())
        if unmeas > 0.35:
            return InspectionResult(False, [],
                [f"Kenarın %{unmeas*100:.0f}'i ölçülemiyor (temas/gölge/"
                 "zemin benzeşmesi) — parçayı serbest ve kontrastlı bir "
                 "zemine koyup tekrar çek"],
                seg, name, image_bgr, status="suspect")
        gate_issues = self._quality_gates(gray, seg, meta.get("sharp"))
        if gate_issues:
            return InspectionResult(False, [], gate_issues, seg, name,
                                    image_bgr, status="suspect")
        found: List[Defect] = []
        found += detect_fill_and_hole(seg, self.cfg)
        found += detect_contour_defects(seg, self.cfg, gray)
        found += detect_surface_defects(gray, seg, self.cfg, image_bgr)
        found = self._post_process(found)
        # operatör dili: kusur konumunu "saat yönü + bölge" olarak ekle
        if seg is not None:
            R = max(self.cfg.reference.outer_radius, 1.0)
            for d in found:
                if d.kind == "eksik_dolum":
                    continue
                x, y, w, h = d.bbox
                dx = (x + w / 2) - seg.center[0]
                dy = (y + h / 2) - seg.center[1]
                hour = int(round((np.degrees(np.arctan2(dx, -dy)) % 360) / 30)) or 12
                rr = float(np.hypot(dx, dy)) / R
                bolge = "kenarda" if rr > 0.75 else ("merkezde" if rr < 0.35 else "yüzeyde")
                d.detail += f" · saat {hour} yönü, {bolge}"

        # ── kusur politikaları: tür bazında izin seviyesi (0-100) ──
        # izin ≥ şiddet×100 olan bulgular karara GİRMEZ ama raporda görünür.
        pol = self.cfg.policies
        def is_aktif(d):
            return d.severity * 100 > pol.get(d.kind, 0)
        aktif = [d for d in found if is_aktif(d)]
        tolere = [d for d in found if not is_aktif(d)]

        # ── uygunluk skoru: yalnız AKTİF bulgular düşürür ──
        score = 100.0
        for d in aktif:
            score -= PENALTY.get(d.kind, 15) * (0.5 + 0.5 * d.severity)
        score = max(0.0, round(score, 1))
        esik = float(self.cfg.min_score)

        tol_notes = [f"{d.label} — {d.detail} (politika: tolere edildi)"
                     for d in tolere]

        if aktif:
            if any(d.strong for d in aktif):
                status = "reject"
                reasons = [f"{d.label} — {d.detail}" for d in aktif]
            elif score < esik:
                status = "reject"
                reasons = [f"Uygunluk %{score:.0f} < eşik %{esik:.0f}"] +                           [f"{d.label} — {d.detail}" for d in aktif]
            else:
                status = "suspect"
                reasons = [f"{d.label} — {d.detail} (sınırda)" for d in aktif]
            return InspectionResult(False, aktif, reasons + tol_notes, seg,
                                    name, image_bgr, status=status,
                                    score=score, tolerated=tolere)

        margin = self._margin_suspects(seg)
        if margin:
            return InspectionResult(False, [], margin + tol_notes, seg, name,
                                    image_bgr, status="suspect",
                                    score=score, tolerated=tolere)
        # GÜVENLİK: öz-testi geçmemiş kalibrasyonla SAĞLAM onayı VERİLMEZ.
        # ("Bu kalibrasyonla karar verme" uyarısı bağlayıcıdır.)
        if self.cfg.calibrated and not self.cfg.selftest_ok:
            return InspectionResult(False, [],
                ["Kalibrasyon öz-testi geçmedi — SAĞLAM onayı verilemez; "
                 "altın numune fotoğrafını düzeltip yeniden kalibre et"]
                + tol_notes, seg, name, image_bgr, status="suspect",
                score=score, tolerated=tolere)
        return InspectionResult(True, [], tol_notes, seg, name, image_bgr,
                                status="ok", score=score, tolerated=tolere)

    @staticmethod
    def _post_process(defects: List[Defect]) -> List[Defect]:
        """Fiziksel olarak aynı olgunun çift sayılmasını önler:
        eksik dolum varsa daire varsayımı geçersizdir → kontur tabanlı
        çapak/kırık tespitleri bastırılır (ana hata bellidir)."""
        if any(d.kind == "eksik_dolum" for d in defects):
            # eksik dolumda daire ve kapalı-delik varsayımları geçersizdir: kontur ve delik
            # geometrisi bulguları aynı olgunun yan etkisidir (delik KAPALI bulgusu hariç)
            defects = [d for d in defects if d.kind not in ("kirik", "capak")
                       and not (d.kind == "delik" and "kapalı" not in d.label)]
        return defects


_ASCII = str.maketrans({"ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
                        "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
                        "·": "-", "—": "-", "–": "-", "→": "->", "%": "%", "°": "",
                        "≤": "<=", "≥": ">=", "…": "..."})


def ascii_metin(s: str) -> str:
    """OpenCV'nin yerleşik yazı tipi yalnız ASCII çizer (Türkçe harf '??' olur).
    Görüntü üstü metin bu yüzden Türkçe→ASCII çevrilir; raporlar Türkçe kalır."""
    return s.translate(_ASCII).encode("ascii", "replace").decode("ascii")


def _yaz(img, metin: str, xy, olcek: float, renk, kalinlik: int, azami_gen: int) -> None:
    metin = ascii_metin(metin)
    (w, _), _ = cv2.getTextSize(metin, cv2.FONT_HERSHEY_SIMPLEX, olcek, kalinlik)
    if w > azami_gen > 0:
        olcek = max(0.32, olcek * azami_gen / w)
    cv2.putText(img, metin, xy, cv2.FONT_HERSHEY_SIMPLEX, olcek, renk, kalinlik, cv2.LINE_AA)


def annotate(image_bgr: np.ndarray, result: InspectionResult) -> np.ndarray:
    """Sonucu görüntü üzerine işaretler: hatalar kutulu, karar bantlı."""
    out = image_bgr.copy()
    h_img, w_img = out.shape[:2]
    if result.segmentation is not None:
        cv2.drawContours(out, [result.segmentation.outer_contour], -1,
                         (90, 200, 90), 1)
    for d in result.defects:
        x, y, w, h = d.bbox
        color = KIND_COLORS.get(d.kind, (255, 255, 255))
        cv2.rectangle(out, (x - 4, y - 4), (x + w + 4, y + h + 4), color, 2)
        _yaz(out, KIND_LABELS.get(d.kind, d.kind), (x - 4, max(y - 8, 44)), 0.45, color, 1,
             w_img - max(x - 4, 0))
    for d in getattr(result, "tolerated", []):
        x, y, w, h = d.bbox
        cv2.rectangle(out, (x - 4, y - 4), (x + w + 4, y + h + 4),
                      (120, 120, 120), 1)
        _yaz(out, KIND_LABELS.get(d.kind, d.kind) + " (tolere)", (x - 4, max(y - 8, 44)),
             0.4, (150, 150, 150), 1, w_img - max(x - 4, 0))
    # karar bandı: yeşil / amber / kırmızı
    band_color = {"ok": (60, 160, 60), "suspect": (20, 130, 210),
                  "reject": (40, 40, 200)}[result.status]
    cv2.rectangle(out, (0, 0), (w_img, 30), band_color, -1)
    text = f"{result.verdict} · Uygunluk %{result.score:.0f}"
    if result.defects:
        kinds = sorted({KIND_LABELS.get(d.kind, d.kind) for d in result.defects})
        text += "  —  " + ", ".join(kinds)
    elif result.status == "suspect" and result.reasons:
        text += "  —  " + result.reasons[0][:60]
    _yaz(out, text, (10, 21), 0.6, (255, 255, 255), 2, w_img - 16)
    return out


def write_batch_report(results: List[InspectionResult], counters: Counters,
                       json_path: str, txt_path: str) -> None:
    """Parti raporu: JSON (makine-okur) + TXT (insan-okur)."""
    payload = {
        "olusturma": datetime.now().isoformat(timespec="seconds"),
        "toplam": counters.total, "saglam": counters.good,
        "supheli": counters.suspect, "fire": counters.scrap, "fire_orani_yuzde": round(counters.scrap_rate, 2),
        "hata_kirilimi": counters.by_kind,
        "parcalar": [{
            "goruntu": r.image_name, "karar": r.verdict,
            "uygunluk_yuzde": round(float(r.score), 1),
            "tolere_edilen": [{"tur": d.kind, "ad": d.label, "detay": d.detail}
                              for d in r.tolerated],
            "hatalar": [{"tur": d.kind, "ad": d.label, "siddet": round(float(d.severity), 2),
                         "detay": d.detail, "bbox": [int(v) for v in d.bbox]}
                        for d in r.defects],
        } for r in results],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    lines = ["GÖZCÜ·AI — Parti Muayene Raporu",
             f"Tarih: {payload['olusturma']}", "",
             counters.summary_tr(), "", "Parça detayı:"]
    for r in results:
        lines.append(f"  [{r.verdict:6}] {r.image_name}"
                     + ("" if r.ok else "  →  " + "; ".join(r.reasons)))
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
