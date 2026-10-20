"""Reproduce the same canonicalization on every available cross-app capture."""
import hashlib
import html
import json
import os
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from canonicalize import canonicalize


HERE=Path(__file__).resolve().parent
ROOT=HERE/'runs/cross-app-01'
CASES=[('finder','Finder',HERE/'runs/finder-live-01'),
       ('calculator','Calculator',ROOT/'calculator'),
       ('settings','System Settings',ROOT/'settings')]


def main(cases=None, root=None, failures=None, scope=None):
    cases=CASES if cases is None else cases
    root=ROOT if root is None else Path(root)
    scope=scope or 'Six app attempts; three paired captures, including the earlier Finder baseline. One surface per app; not an accuracy benchmark.'
    results=[]; cards=[]
    for stem,app,base in cases:
        out=root/'comparison'/stem;out.mkdir(parents=True,exist_ok=True)
        ax=json.loads((base/'ax.json').read_text()); after=json.loads((base/'ax-after.json').read_text())
        meta=json.loads((base/'frame.json').read_text())
        m2=dict(meta,ax_snapshot_id=after['data'].get('snapshot_id'))
        before=canonicalize(ax,meta);aftergraph=canonicalize(after,m2)
        meta['validation']['visible_ax_signature_unchanged']=before['visible_fingerprint']==aftergraph['visible_fingerprint']
        (out/'analysis-frame.json').write_text(json.dumps(meta,indent=2))
        g=canonicalize(ax,meta)
        (out/'entities.json').write_text(json.dumps(g,indent=2))
        samples=[canonicalize(ax,meta)['processing_ms'] for _ in range(20)]
        counts=g['counts']
        lossless=sum(len(e['member_ids']) for e in g['entities'])==counts['projected']
        result={'app':app,'source':str(base),'counts':counts,'lossless_membership':lossless,
                'capture_status':g['capture_status'],'capture_reasons':g['capture_reasons'],
                'validation':meta['validation'],'skew_ms':abs(meta['screenshot_time']-meta['ax_time'])*1000,
                'p50_processing_ms':statistics.median(samples),'p95_processing_ms':sorted(samples)[18],
                'node_count_is_not_accuracy':True,'capture_depth_limit':meta.get('ax_depth_limit',14)}
        results.append(result)
        source=os.path.relpath(base/'capture.png',out)
        im=Image.open(base/'capture.png').convert('RGB'); draw=ImageDraw.Draw(im)
        try:font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',14)
        except OSError:font=ImageFont.load_default()
        raw=[]; canonical=[]; rows=[]
        for n in g['all_nodes']:
            if not n['bbox']:continue
            x,y,x2,y2=n['bbox']
            raw.append(f'<rect x="{x}" y="{y}" width="{x2-x}" height="{y2-y}" fill="none" stroke="#e8791a" stroke-width="1"><title>{html.escape(n["id"]+" "+n["role"]+" "+n["name"])}</title></rect>')
        for i,e in enumerate((e for e in g['entities'] if e['kind']=='control'),1):
            n=e['primary'];x,y,x2,y2=n['bbox'];cid=f'C{i:03}'
            color='#ef4444' if e['overlap_ambiguities'] else '#0284c7'
            desc=f"{cid}: {n['role']} {e['label']} | context: {' / '.join(c['label'] for c in e['context'])} | states: {n['states']} | members: {e['member_ids']}"
            canonical.append(f'<g><title>{html.escape(desc)}</title><rect x="{x}" y="{y}" width="{x2-x}" height="{y2-y}" fill="none" stroke="{color}" stroke-width="2"/><text x="{x+2}" y="{max(14,y-3)}" fill="{color}" font-size="14" style="paint-order:stroke;stroke:white;stroke-width:3px">{cid}</text></g>')
            draw.rectangle((x,y,x2,y2),outline=color,width=2)
            draw.text((x+2,max(0,y-17)),cid,fill=color,font=font,stroke_width=1,stroke_fill='white')
            rows.append('<li>'+html.escape(desc)+'</li>')
        im.save(out/'controls.png')
        page=f'''<!doctype html><meta charset="utf-8"><title>{app} — same AX rule</title>
<style>body{{font:15px system-ui;margin:22px;background:#f5f7fa}}.grid{{display:grid;grid-template-columns:3fr 1fr;gap:20px}}.shot{{position:relative;align-self:start}}img{{width:100%;display:block}}svg{{position:absolute;inset:0;width:100%;height:100%}}li{{padding:8px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}}ol{{max-height:85vh;overflow:auto;padding:12px}}pre{{white-space:pre-wrap}}</style>
<h1>{app}: identical rule, no manual box edits</h1><p>Capture status: <b>{g['capture_status']}</b> · {html.escape(str(g['capture_reasons']))}. Red boxes are unresolved overlaps; blue boxes are candidate controls. None authorizes an action.</p>
<label><input type="checkbox" onchange="document.querySelector('#raw').style.display=this.checked?'block':'none'"> All projected raw nodes</label>
<label><input type="checkbox" checked onchange="document.querySelector('#entities').style.display=this.checked?'block':'none'"> Canonical controls</label>
<p><a href="{source}">Original screenshot</a> · <a href="entities.json">Lossless entity graph + all raw nodes</a> · <a href="analysis-frame.json">Capture validation</a></p>
<div class="grid"><div class="shot"><img src="{source}"><svg viewBox="0 0 {im.width} {im.height}"><g id="raw" style="display:none">{''.join(raw)}</g><g id="entities">{''.join(canonical)}</g></svg></div><ol>{''.join(rows)}</ol></div>
<details><summary>Measurements and capture checks</summary><pre>{html.escape(json.dumps(result,indent=2))}</pre></details>'''
        (out/'index.html').write_text(page)
        cards.append(f'<article><h2>{app}</h2><p>{counts["projected"]} projected nodes → {counts["entities"]} entities; {counts["controls"]} control candidates; {counts["ambiguous_controls"]} with unresolved overlaps.</p><p><b>Capture: {g["capture_status"]}</b> {html.escape(str(g["capture_reasons"]))}</p><a href="{stem}/index.html"><img src="{stem}/controls.png"></a><p><a href="{stem}/index.html">Inspect raw versus canonical overlays</a></p></article>')
    if failures is None: failures=[{'app':'Safari (isolated local fixture)','status':'collector_failed','detail':'Exact CGWindow ID rejected by agent-desktop as window_without_accessibility_element. Original attempt and isolated-window retry both failed. No app-wide tree captured.'},
              {'app':'Antigravity IDE (Electron)','status':'collector_failed','detail':'Exact CGWindow ID rejected as window_without_accessibility_element. CUA could read its tree, so this does not establish that the app lacks AX.'},
              {'app':'TextEdit','status':'capture_tool_failed','detail':'CUA returned ScreenCaptureKit audio/video capture failure (-3811); no usable paired capture.'}]
    rule_hashes={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ['render_overlay.py','canonicalize.py']}
    report={'scope':scope,
            'rules_sha256':rule_hashes,'results':results,'failures':failures,
            'limits':['No manually labeled cross-app precision/recall benchmark.',
                      'No detector/OCR visual proposals used in these live tests; native AX projection and canonicalization only.',
                      'Full screenshots retained. Canonical control counts do not measure visual coverage.',
                      'Mapping timing excludes screenshot capture, AX IPC and downstream model inference.']}
    if any(f['app'].startswith('Safari') for f in failures):
        report['limits'].append('Controlled Safari fixture authored for that test; its native paired capture failed.')
    dest=root/'comparison';(dest/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    failures_html=''.join(f'<li><b>{html.escape(f["app"])}</b>: {html.escape(f["detail"])}</li>' for f in failures)
    (dest/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>AX mapping comparison</title><style>body{{font:16px system-ui;margin:30px;background:#f5f7fb;color:#18263b}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}}article{{padding:20px;background:white;border-radius:12px}}img{{width:100%}}li{{margin:12px}}a{{color:#174ed0}}</style><h1>Same conservative AX mapping rules</h1><p>{html.escape(scope)}</p><p>No per-app box edits. The algorithm preserves every projected node, coalesces only compatible nested nodes, retains context, and flags unresolved control overlaps. Raw layers remain available. This is a diagnostic, not proof of universal reliability.</p><main>{''.join(cards)}</main><h2>Failures retained</h2><ul>{failures_html}</ul><p><a href="summary.json">Full measurements and limitations</a></p>''')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
