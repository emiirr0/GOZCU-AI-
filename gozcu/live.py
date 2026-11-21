"""GÖZCÜ·AI — canlı mod otomatik tetikleyici.

Bant/masa üstü kullanımda SPACE'e basacak kimse yoktur. Tetikleyici:
1) 'b' ile BOŞ SAHNE referansı alınır (arka plan).
2) Sahnede arka plandan belirgin fark → PARÇA VAR.
3) Ardışık karelerde hareket durunca (sahne DURULDU) → BİR KEZ muayene.
4) Parça sahneden çıkana kadar tekrar tetiklenmez (soğuma).

Saf mantık sınıfı: kameradan bağımsız, sentetik karelerle test edilebilir.
"""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


class AutoTrigger:
    def __init__(self, presence_thresh: float = 0.03,
                 motion_thresh: float = 2.5, stable_frames: int = 6):
        self.presence_thresh = presence_thresh   # arka plandan farklı piksel oranı
        self.motion_thresh = motion_thresh       # kareler arası ort. fark (gri)
        self.stable_frames = stable_frames       # bu kadar kare sabit → tetik
        self.bg: Optional[np.ndarray] = None
        self.prev: Optional[np.ndarray] = None
        self._stable = 0
        self._fired = False

    @staticmethod
    def _small(gray: np.ndarray) -> np.ndarray:
        return cv2.resize(gray, (160, 120), interpolation=cv2.INTER_AREA)

    def set_background(self, frame_bgr: np.ndarray) -> None:
        """Boş sahneyi referans al ('b' tuşu)."""
        g = self._small(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY))
        self.bg = cv2.GaussianBlur(g, (5, 5), 0).astype(np.int16)
        self.prev = None
        self._stable = 0
        self._fired = False

    def update(self, frame_bgr: np.ndarray) -> str:
        """Her karede çağır. Dönüş: 'bekle' | 'tetikle' | 'bos'.
        'tetikle' parça yerleşince TAM BİR KEZ döner."""
        g = cv2.GaussianBlur(
            self._small(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)),
            (5, 5), 0).astype(np.int16)
        if self.bg is None:
            self.prev = g
            return "bekle"
        presence = float((np.abs(g - self.bg) > 18).mean())
        motion = (float(np.abs(g - self.prev).mean())
                  if self.prev is not None else 99.0)
        self.prev = g
        if presence < self.presence_thresh:
            self._stable = 0
            self._fired = False
            return "bos"
        if motion < self.motion_thresh:
            self._stable += 1
        else:
            self._stable = 0
        if self._stable >= self.stable_frames and not self._fired:
            self._fired = True
            return "tetikle"
        return "bekle"
