import html
import json
from pathlib import Path
import shutil

root = Path(__file__).parent / 'results'
shutil.copyfile(Path(__file__).parents[2] / 'vlm_testing/click_groq/app_screenshot_raw.png', root / 'source.png')
parts = ['<!doctype html><meta charset="utf-8"><title>A40 detector benchmark</title><style>body{font:16px system-ui;max-width:1400px;margin:32px auto;padding:20px;background:#f4f5f7}section{background:white;padding:24px;margin:24px 0}svg{width:100%;height:auto}rect{fill:transparent;stroke:#ff5252;stroke-width:2}rect:hover{fill:#ff525244;stroke-width:5}td,th{text-align:left;padding:8px}table{border-collapse:collapse}</style><h1>A40 detector benchmark</h1><p>Same 2398 × 1830 screenshot. Detection only: no OCR, icon captions or full-screen semantics. Warm timings are medians of three repeated predictions, including preprocessing and postprocessing; exclude transfer and loading.</p>']
for folder, label in [('omniparser-detector-01','OmniParser V2 detector'),('screenparser-01','ScreenParser')]:
    d=json.loads((root/folder/'result.json').read_text())
    w,h=d['image_size']
    parts.append(f'<section><h2>{label}</h2><p>Warm median: <b>{d["warm_median_seconds"]*1000:.1f} ms</b> · First prediction: {d["first_prediction_seconds"]:.2f} s · {d["count"]} proposals</p><p>Hover over a box for its predicted class and score. These are unverified proposals.</p><svg viewBox="0 0 {w} {h}"><image href="source.png" width="{w}" height="{h}"/>')
    for i,e in enumerate(d['elements']):
        x,y,r,b=e['bbox']; title=html.escape(f'{i}: {e["label"]} ({e["confidence"]:.2f})')
        parts.append(f'<rect x="{x}" y="{y}" width="{r-x}" height="{b-y}"><title>{title}</title></rect>')
    parts.append('</svg></section>')
parts.append('<p>Manual findings: both detectors propose controls inside video content. ScreenParser provides useful classes but does not establish clickability or parent-child relations. Detection counts are not accuracy scores. Settings: image size 1280, confidence 0.10, NMS IoU 0.10; FP32, PyTorch 2.0.0+cu117. Full ScreenVLM and OmniParser OCR/caption stages have not been benchmarked.</p>')
(root/'comparison.html').write_text(''.join(parts))
