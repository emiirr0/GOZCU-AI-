"""GÖZCÜ·AI — endüstriyel görüntü işleme ile kalite muayenesi.

Paket içe aktarılırken OpenCV yüklenmez; böylece eksik kurulumda
`python -m gozcu` anlaşılır bir mesaj verebilir. Bileşenler ilk
kullanımda yüklenir.
"""
VERSION = "2.0.0"

_DISA = {
    "InspectionConfig": "config", "ReferencePart": "config", "Thresholds": "config",
    "Defect": "detectors", "segment_part": "detectors",
    "Counters": "pipeline", "InspectionPipeline": "pipeline", "InspectionResult": "pipeline",
    "annotate": "pipeline", "write_batch_report": "pipeline",
}

__all__ = ["VERSION", *_DISA]


def __getattr__(ad):
    if ad in _DISA:
        import importlib
        return getattr(importlib.import_module(f".{_DISA[ad]}", __name__), ad)
    raise AttributeError(f"module 'gozcu' has no attribute {ad!r}")
