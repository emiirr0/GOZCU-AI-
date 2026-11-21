"""GÖZCÜ·AI — yapılandırma (ayarlar.json ile kalıcı).

Referans geometri ve eşikler artık sabit değil: 'kalibre' komutu
altın numuneden öğrenir ve ayarlar.json'a yazar. Dosya yoksa
demo varsayılanları kullanılır.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict

@dataclass
class ReferencePart:
    outer_radius: float = 170.0
    hole_radius: float = 45.0
    hole_expected: bool = True
    radius_tolerance: float = 0.035


@dataclass
class Thresholds:
    protrusion_min_run: int = 8
    notch_min_run: int = 8
    scratch_min_len: int = 34
    scratch_max_thickness: int = 7
    scratch_diff: int = 14
    stain_min_area: int = 140
    stain_diff: int = 16
    color_diff: int = 14          # Lab kroma sapması (renkli leke/iz için)
    short_shot_area_ratio: float = 0.90


DEFAULT_POLICIES: Dict[str, int] = {
    "capak": 0, "kirik": 0, "cizik": 0, "leke": 0,
    "eksik_dolum": 0, "delik": 0,
}
POLICY_PRESETS = {"sifir": 0, "hafif": 35, "yok_say": 100}


@dataclass
class InspectionConfig:
    reference: ReferencePart = field(default_factory=ReferencePart)
    thresholds: Thresholds = field(default_factory=Thresholds)
    calibrated: bool = False
    selftest_ok: bool = True   # öz-test geçmediyse SAĞLAM onayı verilemez
    # kusur politikaları: tür → izin seviyesi 0-100
    #   0 = sıfır tolerans (her bulgu sayılır)
    #   35 = hafif bulgular tolere edilir
    #   100 = bu tür tamamen yok sayılır (yine raporlanır ama karara girmez)
    policies: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_POLICIES))
    # uygunluk eşiği: parça skoru bu yüzdenin altındaysa FİRE
    min_score: int = 70

    # ── kalıcılık ────────────────────────────────────────────────
    def save(self, path) -> None:
        data = {"reference": asdict(self.reference),
                "thresholds": asdict(self.thresholds),
                "calibrated": self.calibrated,
                "selftest_ok": self.selftest_ok,
                "policies": self.policies,
                "min_score": self.min_score}
        gecici = f"{path}.tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(gecici, path)          # yarım yazılmış ayar dosyası kalmasın

    @classmethod
    def load(cls, path) -> "InspectionConfig":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            print("Uyarı: ayarlar.json okunamadı/bozuk — varsayılanlara dönüldü. "
                  "Yeniden kalibre etmen önerilir.")
            return cls()
        try:
            pol = dict(DEFAULT_POLICIES)
            pol.update({k: int(v) for k, v in (d.get("policies") or {}).items() if k in DEFAULT_POLICIES})
            bilinen_r = ReferencePart.__dataclass_fields__
            bilinen_t = Thresholds.__dataclass_fields__
            return cls(reference=ReferencePart(**{k: v for k, v in (d.get("reference") or {}).items() if k in bilinen_r}),
                       thresholds=Thresholds(**{k: v for k, v in (d.get("thresholds") or {}).items() if k in bilinen_t}),
                       calibrated=bool(d.get("calibrated", False)),
                       selftest_ok=bool(d.get("selftest_ok", True)),
                       policies=pol,
                       min_score=max(0, min(100, int(d.get("min_score", 70)))))
        except (TypeError, ValueError, AttributeError):
            print("Uyarı: ayarlar.json beklenmeyen biçimde — varsayılanlara dönüldü.")
            return cls()
