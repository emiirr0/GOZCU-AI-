"""GÖZCÜ·AI — Unicode-güvenli görüntü okuma/yazma.

OpenCV'nin imread/imwrite'ı Windows'ta Türkçe karakterli yollarda
(örn. C:\\Users\\...\\Masaüstü\\...) dosya AÇAMAZ. Çözüm: dosyayı
Python ile (Unicode-güvenli) okuyup OpenCV'ye bellekten vermek,
yazarken de belleğe kodlayıp Python ile yazmak.
"""
from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np


def imread_tr(path: str) -> Optional[np.ndarray]:
    """Türkçe/Unicode yollarda da çalışan görüntü okuma."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        if not data:
            return None
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except OSError:
        return None


def imwrite_tr(path: str, img: np.ndarray) -> bool:
    """Türkçe/Unicode yollarda da çalışan görüntü yazma."""
    ext = os.path.splitext(path)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    try:
        with open(path, "wb") as f:
            f.write(buf.tobytes())
        return True
    except OSError:
        return False
