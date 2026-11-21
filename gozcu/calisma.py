"""Çalışma klasörü — GÖZCÜ'nün okuduğu ve yazdığı her şeyin yeri.

Varsayılan: komutun çalıştırıldığı klasör (başlatıcılar proje klasörüne
geçer). Başka bir yer için GOZCU_CALISMA ortam değişkeni ya da
`--klasor` seçeneği kullanılır.

    altin_numune/   SAĞLAM parça fotoğrafları (kalibrasyon)
    fotograflar/    kontrol edilecek fotoğraflar
    cikti/          işaretli görüntüler + raporlar
    ayarlar.json    kalibrasyon + politikalar
    sayaclar.json   kalıcı sayaçlar (+ sayılmış fotoğrafların imzaları)
    gecmis.jsonl    her muayenenin arşivi (fire raporu buradan)
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional, Set

from .pipeline import Counters

UZANTILAR = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
AZAMI_IMZA = 50_000


def gorselleri_listele(klasor: Path) -> List[Path]:
    """Klasördeki görüntü dosyaları (büyük/küçük harf duyarsız, tekrarsız, sıralı)."""
    if not klasor.is_dir():
        return []
    return sorted((p for p in klasor.iterdir()
                   if p.is_file() and p.suffix.lower() in UZANTILAR
                   and not p.name.startswith(".")), key=lambda p: p.name.lower())


def dosya_imzasi(yol: Path) -> str:
    """İçerik imzası: aynı fotoğraf yeniden adlandırılsa da tanınır."""
    h = hashlib.sha1()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()[:20]


class Calisma:
    def __init__(self, kok: Optional[os.PathLike] = None):
        self.kok = Path(kok or os.environ.get("GOZCU_CALISMA") or Path.cwd()).resolve()
        self.altin = self.kok / "altin_numune"
        self.fotolar = self.kok / "fotograflar"
        self.cikti = self.kok / "cikti"
        self.ayarlar = self.kok / "ayarlar.json"
        self.sayac_dosyasi = self.kok / "sayaclar.json"
        self.gecmis = self.kok / "gecmis.jsonl"

    def hazirla(self) -> "Calisma":
        for k in (self.altin, self.fotolar, self.cikti):
            k.mkdir(parents=True, exist_ok=True)
        return self

    # ── kalıcı sayaçlar ──────────────────────────────────────────────
    def sayac_oku(self) -> "tuple[Counters, Set[str]]":
        c, imzalar = Counters(), set()
        if self.sayac_dosyasi.is_file():
            try:
                d = json.loads(self.sayac_dosyasi.read_text(encoding="utf-8"))
                c.total, c.good, c.scrap = int(d["total"]), int(d["good"]), int(d["scrap"])
                c.suspect = int(d.get("suspect", 0))
                c.by_kind = {str(k): int(v) for k, v in (d.get("by_kind") or {}).items()}
                imzalar = set(d.get("imzalar") or [])
            except (ValueError, KeyError, TypeError, OSError):
                print("Uyarı: sayaclar.json bozuk — sayaçlar sıfırdan başlıyor "
                      "(eski dosya sayaclar.bozuk.json olarak saklandı).")
                try:
                    self.sayac_dosyasi.replace(self.sayac_dosyasi.with_name("sayaclar.bozuk.json"))
                except OSError:
                    pass
        return c, imzalar

    def sayac_yaz(self, c: Counters, imzalar: Set[str]) -> None:
        veri = {"total": c.total, "good": c.good, "scrap": c.scrap, "suspect": c.suspect,
                "by_kind": c.by_kind, "imzalar": sorted(imzalar)[-AZAMI_IMZA:]}
        gecici = self.sayac_dosyasi.with_suffix(".tmp")
        gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
        gecici.replace(self.sayac_dosyasi)        # yarım yazılmış dosya kalmasın
