"""Render saved semantic benchmark output without calling a model."""
import html
import json
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).parent/'results'
d=json.loads((root/'omni-semantics-batch64-01/result.json').read_text())
im=Image.open(root/'source.png').convert('RGB');w,h=im.size
els=d['runs'][-1]['elements']
parts=['<!doctype html><meta charset="utf-8"><title>A40 semantic perception</title><style>body{font:16px system-ui;background:#f4f5f7;max-width:1450px;margin:32px auto;padding:16px}section{background:white;padding:24px;margin:20px 0}svg{width:100%;height:auto}rect{fill:transparent;stroke:#ff5252;stroke-width:2}rect:hover{fill:#ff525244;stroke-width:5}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}td{max-width:700px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}.caption{color:#9b3500}.note{background:#fff4db;padding:16px}</style><h1>Text + icon semantics on the A40</h1><p class="note">Predictions, not verified click targets. Elements inside video content can be misclassified as interactive. Captions can invent function names. Full screen relationships and changes over time are not inferred by this parser.</p><section><h2>Measured latency</h2><p>OmniParser V2 detector + EasyOCR GPU + Florence captions, 2398 × 1830 input. Batch-64 OCR: <b>1.980 s warm median</b>; default OCR batching: <b>2.533 s</b>. Three warm repetitions each; sequential stages. Excludes image transfer, disk reading and model loading.</p><p>97 OCR regions; 20 captioned crops; 80 merged elements. Batched OCR preserved the geometry set but changed four text fields and changed output ordering on this screen.</p></section><section><h2>Inspect predicted content</h2><p>Hover a box to see its ID, source and text. Orange rows below are generated icon captions.</p>']
parts.append(f'<svg viewBox="0 0 {w} {h}"><image href="source.png" width="{w}" height="{h}"/>')
for i,e in enumerate(els):
 l,t,r,b=[v*s for v,s in zip(e['bbox'],[w,h,w,h])]
 title=html.escape(f'{i}: {e["content"]} [{e.get("source","")}]')
 parts.append(f'<rect x="{l}" y="{t}" width="{r-l}" height="{b-t}"><title>{title}</title></rect>')
parts.append('</svg><table><tr><th>ID</th><th>Type/source</th><th>Predicted content</th></tr>')
for i,e in enumerate(els):
 cls='caption' if e.get('source')=='box_yolo_content_florence' else ''
 parts.append(f'<tr class="{cls}"><td>{i}</td><td>{html.escape(e.get("source",""))}</td><td>{html.escape(e.get("content") or "")}</td></tr>')
parts.append('</table></section><section><h2>ScreenVLM diagnostic</h2><p>The initial eager-attention diagnostic took 21.44 seconds for 512 tokens and stopped at the token cap: 25 complete boxes, mostly browser controls and tabs. This is incomplete and cannot be compared as equivalent coverage. Token caching was explicitly enabled because the checkpoint disables it by default.</p><p>A second run using the checkpoint-matched Transformers 4.55.2 runtime and SDPA reached a 60-second generation limit (60.52 s including preprocessing), generated 2,291 tokens, and fell into repeated text. It yielded only 35 completed leaf tags and did not produce a usable complete screen parse. This is a single-screen result, not a general claim about the model.</p></section>')
(root/'semantics.html').write_text(''.join(parts))
captioned=[(i,e) for i,e in enumerate(els) if e.get('source')=='box_yolo_content_florence']
sheet=Image.new('RGB',(1000,220*((len(captioned)+3)//4)),'#ffffff');draw=ImageDraw.Draw(sheet)
for j,(i,e) in enumerate(captioned):
 l,t,r,b=[round(v*s) for v,s in zip(e['bbox'],[w,h,w,h])]
 crop=im.crop((max(0,l-12),max(0,t-12),min(w,r+12),min(h,b+12)))
 crop.thumbnail((230,170));x=(j%4)*250;y=(j//4)*220
 sheet.paste(crop,(x,y));draw.text((x+3,y+175),f'{i}: {e["content"]}',fill='black')
sheet.save(root/'omni-caption-crops.jpg')
