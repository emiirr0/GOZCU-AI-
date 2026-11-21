"""GÖZCÜ·AI — tek dosyalık HTML muayene raporu.

Görseller base64 gömülüdür; rapor.html tek başına taşınır,
tarayıcıda çift tıkla açılır. USTA·AI ile aynı görsel dil.
"""
from __future__ import annotations

import base64
from datetime import datetime
from typing import List

import cv2

from .pipeline import Counters, InspectionResult, KIND_LABELS

C = dict(bg="#0B0F12", panel="#131A20", border="#263039", amber="#F5A623",
         cyan="#35C4E0", green="#3FB950", red="#E5484D",
         hi="#E8EEF2", mid="#9DAAB4", lo="#5C6B75")


def _thumb_b64(img, width=280) -> str:
    h, w = img.shape[:2]
    s = width / w
    t = cv2.resize(img, (width, int(h * s)))
    ok, buf = cv2.imencode(".jpg", t, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return base64.b64encode(buf).decode() if ok else ""


def render(results: List[InspectionResult], counters: Counters,
           annotated: List, out_path: str, title_note: str = "") -> None:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    kinds = "".join(
        f'<span class="chip">{KIND_LABELS.get(k, k)}: <b>{v}</b></span>'
        for k, v in sorted(counters.by_kind.items()))
    cards = []
    for res, ann in zip(results, annotated):
        b64 = _thumb_b64(ann)
        cls = {"ok": "ok", "suspect": "sus", "reject": "bad"}[res.status]
        reasons = "".join(f"<li>{r}</li>" for r in res.reasons) or \
                  "<li>Kusur bulunamadı</li>"
        cards.append(f"""
      <div class="card {cls}">
        <img src="data:image/jpeg;base64,{b64}" alt="">
        <div class="body">
          <div class="row"><span class="name">{res.image_name}</span>
            <span class="verdict {cls}">{res.verdict} · %{res.score:.0f}</span></div>
          <ul>{reasons}</ul>
        </div>
      </div>""")

    html = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GÖZCÜ·AI — Muayene Raporu</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:{C['bg']};color:{C['hi']};font:14px 'Segoe UI',system-ui,sans-serif;padding:24px}}
.wrap{{max-width:1240px;margin:0 auto}}
h1{{font-size:20px;letter-spacing:1px}} h1 span{{color:{C['amber']}}}
.sub{{color:{C['lo']};font-size:12px;margin-top:4px}}
.stats{{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0;padding:14px 16px;
  background:{C['panel']};border:1px solid {C['border']};border-radius:10px}}
.stat b{{font-size:22px;font-family:Consolas,monospace}}
.stat .g{{color:{C['green']}}} .stat .r{{color:{C['red']}}} .stat .c{{color:{C['cyan']}}}
.stat div{{color:{C['lo']};font-size:11px;text-transform:uppercase;letter-spacing:1px}}
.chips{{margin:0 0 18px}} .chip{{display:inline-block;background:{C['panel']};
  border:1px solid {C['border']};border-radius:14px;padding:4px 12px;margin:0 6px 6px 0;
  color:{C['mid']};font-size:12px}} .chip b{{color:{C['hi']}}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}}
.card{{background:{C['panel']};border:1px solid {C['border']};border-radius:10px;overflow:hidden}}
.card.bad{{border-color:#5a2a28}} .card.sus{{border-color:#5c4210}} .card img{{width:100%;display:block}}
.card .body{{padding:10px 12px}}
.row{{display:flex;justify-content:space-between;align-items:center}}
.name{{font-size:12px;color:{C['mid']};font-family:Consolas,monospace}}
.verdict{{font-weight:700;font-size:12px;letter-spacing:1px;border-radius:5px;padding:2px 9px}}
.verdict.ok{{background:#12341C;color:{C['green']}}}
.verdict.bad{{background:#3A1516;color:{C['red']}}}
.verdict.sus{{background:#3a2b08;color:{C['amber']}}}
.card ul{{margin:8px 0 2px 16px;color:{C['mid']};font-size:12px;line-height:1.5}}
footer{{margin-top:22px;color:{C['lo']};font-size:11px}}
</style></head><body><div class="wrap">
<h1>◆ GÖZCÜ<span>·AI</span> — Muayene Raporu</h1>
<div class="sub">{now}{(' · ' + title_note) if title_note else ''}</div>
<div class="stats">
  <div class="stat"><b>{counters.total}</b><div>Toplam</div></div>
  <div class="stat"><b class="g">{counters.good}</b><div>Sağlam</div></div>
  <div class="stat"><b style="color:{C['amber']}">{counters.suspect}</b><div>Şüpheli</div></div>
  <div class="stat"><b class="r">{counters.scrap}</b><div>Fire</div></div>
  <div class="stat"><b class="c">%{counters.scrap_rate:.1f}</b><div>Fire Oranı</div></div>
</div>
<div class="chips">{kinds or '<span class="chip">Hata kaydı yok</span>'}</div>
<div class="grid">{''.join(cards)}</div>
<footer>GÖZCÜ·AI · sayaçlar kalıcıdır (sayaclar.json) · bu rapor tek dosyadır, paylaşabilirsiniz</footer>
</div></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
