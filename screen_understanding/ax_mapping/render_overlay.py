"""Render native AX geometry over a genuine, separately captured screenshot."""
import argparse
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from matcher import Frame, normalize_ax


CONTAINERS = {'application', 'window', 'group', 'scrollarea', 'splitgroup',
              'toolbar', 'list', 'outline', 'table', 'row', 'layoutarea'}


def render(ax_path, frame_path, image_path, out):
    out.mkdir(parents=True, exist_ok=True)
    snapshot = json.loads(ax_path.read_text())
    meta = json.loads(frame_path.read_text())
    frame = Frame(meta)
    image = Image.open(image_path).convert('RGB')
    if list(image.size) != meta['image_size']:
        raise ValueError('Screenshot dimensions differ from frame metadata')
    nodes, info = normalize_ax(snapshot, frame)
    # Preserve every projected node in the JSON; deduplicate only the display layer.
    visible = [n for n in nodes if n['bbox']]
    display, seen = [], set()
    # Prefer named/control nodes over unnamed wrappers with identical bounds.
    for n in sorted(visible, key=lambda n: (n['role'] in CONTAINERS, not bool(n['name']), not bool(n['actions']))):
        if n['role'] in CONTAINERS:
            continue
        key = tuple(round(v) for v in n['bbox'])
        if key in seen:
            continue
        seen.add(key)
        display.append(n)
    display.sort(key=lambda n: (n['bbox'][1], n['bbox'][0]))
    for i, n in enumerate(display, 1):
        n['overlay_id'] = f'A{i:03d}'
    (out / 'projected_nodes.json').write_text(json.dumps({'metadata': meta, 'observation': info,
                                                        'all_projected_nodes': visible,
                                                        'display_nodes': display}, indent=2) + '\n')
    # Keep native image resolution; labels contain IDs so long names do not hide UI.
    scale = max(1, round(image.width / 1100))
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 11 * scale)
    except OSError:
        font = ImageFont.load_default()
    canvas = image.convert('RGBA')
    layer = Image.new('RGBA', canvas.size)
    draw = ImageDraw.Draw(layer)
    rects, rows = [], []
    for n in display:
        b = n['bbox']
        color = '#2563eb' if n['actions'] else '#15803d'
        label = n['overlay_id']
        draw.rectangle(b, outline=color, width=max(1, scale))
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0] + 6, tb[3] - tb[1] + 6
        x = min(max(0, b[0]), image.width - tw)
        y = min(max(0, b[1] - th), image.height - th)
        draw.rectangle((x, y, x + tw, y + th), fill=color)
        draw.text((x + 3, y + 3 - tb[1]), label, font=font, fill='white')
        name = str(n['name'] or n.get('description') or n.get('value') or '(unnamed)')
        detail = f"{label}: {n['role']} | {name} | states={n['states']} | actions={n['actions']} | ref={n['ref']}"
        esc = html.escape(detail)
        rects.append(f'<g class="axbox" data-id="{label}"><title>{esc}</title>'
                     f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" '
                     f'fill="transparent" stroke="{color}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>'
                     f'<text x="{b[0]+2}" y="{max(12,b[1]-3)}" fill="{color}" font-size="12" '
                     f'style="paint-order:stroke;stroke:white;stroke-width:3px">{label}</text></g>')
        rows.append(f'<li data-id="{label}"><b>{label} · {html.escape(n["role"])}</b> '
                    f'{html.escape(name)}<small>states: {html.escape(str(n["states"]))} · '
                    f'actions: {html.escape(str(n["actions"]))}<br>{html.escape(str(n["ref"]))}</small></li>')
    Image.alpha_composite(canvas, layer).convert('RGB').save(out / 'overlay.png')
    # A second view focuses on named controls. Keep the all-node view unchanged.
    clean_layer = Image.new('RGBA', canvas.size)
    clean_draw = ImageDraw.Draw(clean_layer)
    clean_count = 0
    for n in display:
        name = str(n['name'] or n.get('value') or '')
        if not name or not n['actions'] or n['role'] not in {
                'button', 'textfield', 'treeitem', 'menubutton', 'combobox',
                'checkbox', 'radiobutton', 'tab', 'link'}:
            continue
        if n['role'] == 'treeitem' and any(
                d['id'].startswith(n['id'] + '.') and d['role'] == 'textfield'
                and (d['name'] or d.get('value')) for d in display):
            # A file row aggregates all its columns; show its editable name instead.
            continue
        b = n['bbox']
        label = f"{n['overlay_id']} {name[:26]}"
        available_width = max(60, b[2]-b[0])
        while len(label) > len(n['overlay_id']) and clean_draw.textbbox((0,0), label, font=font)[2] + 6 > available_width:
            label = label[:-1]
        tb = clean_draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2]-tb[0]+6, tb[3]-tb[1]+6
        x, y = min(b[0], image.width-tw), max(0, b[1]-th)
        clean_draw.rectangle(b, outline='#38bdf8', width=max(1,scale))
        clean_draw.rectangle((x,y,x+tw,y+th), fill='#075985')
        clean_draw.text((x+3,y+3-tb[1]), label, font=font, fill='white')
        clean_count += 1
    Image.alpha_composite(canvas, clean_layer).convert('RGB').save(out / 'context-overlay.png')
    image.save(out / 'source.png')
    note = {'image_size': image.size, 'projected_nodes': len(visible), 'display_boxes': len(display),
            'named_controls_in_clean_view': clean_count,
            'frame_check': frame.check, 'capture_validation': meta.get('validation'),
            'observation': info}
    (out / 'summary.json').write_text(json.dumps(note, indent=2) + '\n')
    page = '''<!doctype html><meta charset="utf-8"><title>Native AX screenshot overlay</title>
<style>body{font:15px system-ui;margin:24px;color:#182332;background:#f5f7fb}h1{margin-bottom:8px}
.layout{display:grid;grid-template-columns:minmax(0,3fr) minmax(260px,1fr);gap:20px}.shot{position:relative;background:white;align-self:start}
.shot img{width:100%;display:block}.shot svg{position:absolute;inset:0;width:100%;height:100%}li{padding:9px;border-bottom:1px solid #ddd;cursor:pointer}
small{display:block;color:#566273;overflow-wrap:anywhere}ol{padding:0;list-style:none;max-height:80vh;overflow:auto;background:white}
.axbox:hover rect,.axbox.selected rect{stroke:#e11d48;stroke-width:4}.selected{background:#ffe4e6}button{margin:8px 8px 12px 0;padding:8px}
pre{white-space:pre-wrap}details{margin-top:20px}@media(max-width:800px){.layout{grid-template-columns:1fr}}</style>
<h1>Native accessibility bounds on a real screenshot</h1>
<p>Boxes and labels come from AX, without a vision model. Blue: node exposes native actions. Green: other node.
IDs identify display records; hover/click a box or list entry. Matching geometry does not prove visibility, clickability or semantic completeness.</p>
<button onclick="document.querySelector('svg').style.display=document.querySelector('svg').style.display==='none'?'block':'none'">Toggle AX overlay</button>
<a href="context-overlay.png">Named controls PNG</a> · <a href="overlay.png">All boxes PNG</a> · <a href="source.png">Raw screenshot</a> · <a href="projected_nodes.json">All projected AX nodes</a>
<div class="layout"><div class="shot"><img src="source.png"><svg viewBox="0 0 WIDTH HEIGHT">RECTS</svg></div><ol>ROWS</ol></div>
<details><summary>Capture provenance and limitations</summary><pre>NOTE</pre></details>
<script>document.querySelectorAll('[data-id]').forEach(e=>e.addEventListener('click',()=>{document.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'));document.querySelectorAll('[data-id="'+e.dataset.id+'"]').forEach(x=>{x.classList.add('selected');if(x.tagName==='LI')x.scrollIntoView({block:'nearest'})})}));</script>'''
    page = page.replace('WIDTH HEIGHT', f'{image.width} {image.height}').replace('RECTS', ''.join(rects)).replace('ROWS', ''.join(rows)).replace('NOTE', html.escape(json.dumps(note, indent=2)))
    (out / 'index.html').write_text(page)
    return note


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('ax', 'frame', 'image', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(render(a.ax, a.frame, a.image, a.out), indent=2))
