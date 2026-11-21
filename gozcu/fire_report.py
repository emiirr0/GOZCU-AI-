"""GÖZCÜ·AI — fire raporları.

Her muayene gecmis.jsonl'e eklenir (satır başına bir JSON kaydı —
bozulmaya dayanıklı, sonsuz büyüyebilen format). 'rapor' komutu bu
geçmişten günlük kırılımlı bir HTML raporu ve Excel için CSV üretir.
"""
from __future__ import annotations

import base64
import csv
import glob
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import cv2

from .pipeline import KIND_LABELS
from .io_utils import imread_tr

C = dict(bg="#0B0F12", panel="#131A20", border="#263039", amber="#F5A623",
         cyan="#35C4E0", green="#3FB950", red="#E5484D",
         hi="#E8EEF2", mid="#9DAAB4", lo="#5C6B75")


def append_history(path: str, result) -> None:
    """Tek muayeneyi geçmişe ekle (jsonl: her satır bağımsız kayıt)."""
    rec = {
        "zaman": datetime.now().isoformat(timespec="seconds"),
        "parca": result.image_name,
        "karar": result.verdict,
        "skor": round(float(result.score), 1),
        "turler": sorted({d.kind for d in result.defects}),
        "tolere": sorted({d.kind for d in result.tolerated}),
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_history(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # bozuk satırı atla, rapor çökmesin
    return out


def write_csv(records: List[dict], path: str) -> None:
    """Excel-uyumlu CSV (UTF-8 BOM + noktalı virgül — TR Excel varsayılanı)."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Zaman", "Parça", "Karar", "Uygunluk %",
                    "Hata Türleri", "Tolere Edilenler"])
        for r in records:
            w.writerow([r["zaman"], r["parca"], r["karar"], r["skor"],
                        ", ".join(KIND_LABELS.get(k, k) for k in r["turler"]),
                        ", ".join(KIND_LABELS.get(k, k) for k in r["tolere"])])


def _daily(records: List[dict]) -> List[dict]:
    g: Dict[str, dict] = defaultdict(lambda: {"toplam": 0, "saglam": 0,
                                              "supheli": 0, "fire": 0})
    for r in records:
        d = g[r["zaman"][:10]]
        d["toplam"] += 1
        k = r["karar"]
        d["saglam" if k == "SAĞLAM" else "supheli" if k == "ŞÜPHELİ"
          else "fire"] += 1
    return [dict(tarih=t, **v) for t, v in sorted(g.items(), reverse=True)]


def _thumb(path: str, width=240) -> str:
    img = imread_tr(path)
    if img is None:
        return ""
    h, w = img.shape[:2]
    t = cv2.resize(img, (width, int(h * width / w)))
    ok, buf = cv2.imencode(".jpg", t, [cv2.IMWRITE_JPEG_QUALITY, 78])
    return base64.b64encode(buf).decode() if ok else ""


def render_fire_report(records: List[dict], out_html: str,
                       cikti_dir: str, version: str = "") -> None:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    toplam = len(records)
    saglam = sum(r["karar"] == "SAĞLAM" for r in records)
    supheli = sum(r["karar"] == "ŞÜPHELİ" for r in records)
    fire = toplam - saglam - supheli
    oran = (fire / toplam * 100) if toplam else 0.0

    kind_tot: Dict[str, int] = defaultdict(int)
    tol_tot: Dict[str, int] = defaultdict(int)
    for r in records:
        for k in r["turler"]:
            kind_tot[k] += 1
        for k in r["tolere"]:
            tol_tot[k] += 1
    chips = "".join(f'<span class="chip">{KIND_LABELS.get(k,k)}: <b>{v}</b></span>'
                    for k, v in sorted(kind_tot.items(), key=lambda x: -x[1]))
    tchips = "".join(f'<span class="chip t">{KIND_LABELS.get(k,k)}: <b>{v}</b></span>'
                     for k, v in sorted(tol_tot.items(), key=lambda x: -x[1]))

    rows = "".join(
        f"<tr><td>{d['tarih']}</td><td>{d['toplam']}</td>"
        f"<td class='g'>{d['saglam']}</td><td class='a'>{d['supheli']}</td>"
        f"<td class='r'>{d['fire']}</td>"
        f"<td>%{(d['fire']/d['toplam']*100 if d['toplam'] else 0):.1f}</td></tr>"
        for d in _daily(records))

    # son fire görüntüleri (varsa)
    fire_imgs = sorted(glob.glob(os.path.join(cikti_dir, "*__FIRE.png")),
                       key=os.path.getmtime, reverse=True)[:8]
    gallery = "".join(
        f'<div class="fi"><img src="data:image/jpeg;base64,{_thumb(p)}">'
        f'<div>{os.path.basename(p).split("__")[0]}</div></div>'
        for p in fire_imgs if _thumb(p))

    son = "".join(
        f"<tr><td>{r['zaman'].replace('T',' ')}</td><td>{r['parca']}</td>"
        f"<td class='{ 'g' if r['karar']=='SAĞLAM' else 'a' if r['karar']=='ŞÜPHELİ' else 'r'}'>"
        f"{r['karar']}</td><td>%{r['skor']:.0f}</td>"
        f"<td>{', '.join(KIND_LABELS.get(k,k) for k in r['turler']) or '—'}</td></tr>"
        for r in list(reversed(records))[:30])

    html = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GÖZCÜ·AI — Fire Raporu</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:{C['bg']};color:{C['hi']};font:14px 'Segoe UI',system-ui,sans-serif;padding:24px}}
.wrap{{max-width:1100px;margin:0 auto}}
h1{{font-size:20px;letter-spacing:1px}} h1 span{{color:{C['amber']}}}
h2{{font-size:13px;letter-spacing:1.5px;color:{C['mid']};text-transform:uppercase;margin:26px 0 10px}}
.sub{{color:{C['lo']};font-size:12px;margin-top:4px}}
.stats{{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0;padding:14px 16px;
 background:{C['panel']};border:1px solid {C['border']};border-radius:10px}}
.stat b{{font-size:24px;font-family:Consolas,monospace}}
.g{{color:{C['green']}}} .a{{color:{C['amber']}}} .r{{color:{C['red']}}} .c{{color:{C['cyan']}}}
.stat div{{color:{C['lo']};font-size:11px;text-transform:uppercase;letter-spacing:1px}}
.chip{{display:inline-block;background:{C['panel']};border:1px solid {C['border']};
 border-radius:14px;padding:4px 12px;margin:0 6px 6px 0;color:{C['mid']};font-size:12px}}
.chip b{{color:{C['hi']}}} .chip.t{{opacity:.65}}
table{{width:100%;border-collapse:collapse;background:{C['panel']};
 border:1px solid {C['border']};border-radius:10px;overflow:hidden}}
th,td{{padding:8px 12px;text-align:left;font-size:13px;border-bottom:1px solid {C['border']}}}
th{{color:{C['lo']};font-size:11px;text-transform:uppercase;letter-spacing:1px}}
tr:last-child td{{border-bottom:none}}
.gal{{display:flex;gap:10px;flex-wrap:wrap}}
.fi{{background:{C['panel']};border:1px solid {C['border']};border-radius:8px;
 overflow:hidden;width:240px}} .fi img{{width:100%;display:block}}
.fi div{{padding:6px 10px;font-size:11px;color:{C['mid']};font-family:Consolas,monospace}}
footer{{margin-top:24px;color:{C['lo']};font-size:11px}}
</style></head><body><div class="wrap">
<h1>◆ GÖZCÜ<span>·AI</span> — Fire Raporu</h1>
<div class="sub">{now} · kayıtlı geçmişin tamamı</div>
<div class="stats">
 <div class="stat"><b>{toplam}</b><div>Toplam</div></div>
 <div class="stat"><b class="g">{saglam}</b><div>Sağlam</div></div>
 <div class="stat"><b class="a">{supheli}</b><div>Şüpheli</div></div>
 <div class="stat"><b class="r">{fire}</b><div>Fire</div></div>
 <div class="stat"><b class="c">%{oran:.1f}</b><div>Fire Oranı</div></div>
</div>
<h2>Hata türü kırılımı (fire olan parçalarda)</h2>
<div>{chips or '<span class="chip">kayıt yok</span>'}</div>
{f'<h2>Politikayla tolere edilenler (geçen ama kayıtlı)</h2><div>{tchips}</div>' if tol_tot else ''}
<h2>Günlük kırılım</h2>
<table><tr><th>Tarih</th><th>Toplam</th><th>Sağlam</th><th>Şüpheli</th>
<th>Fire</th><th>Fire %</th></tr>{rows or '<tr><td colspan=6>kayıt yok</td></tr>'}</table>
{f'<h2>Son fire görüntüleri</h2><div class="gal">{gallery}</div>' if gallery else ''}
<h2>Son 30 muayene</h2>
<table><tr><th>Zaman</th><th>Parça</th><th>Karar</th><th>Skor</th><th>Türler</th></tr>
{son or '<tr><td colspan=5>kayıt yok</td></tr>'}</table>
<footer>GÖZCÜ·AI v{version} · CSV dışa aktarım: fire_raporu.csv (Excel ile açılır) ·
geçmiş: gecmis.jsonl</footer>
</div></body></html>"""
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
