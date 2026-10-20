"""Run screen-map-v1 on saved native captures, without moving the desktop."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from extract_shapes import extract as shapes
from screen_map import build_map
from render_screen_map import render

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASES=[('notion',HERE/'runs/notion-live-02',HERE/'runs/notion-live-02/comparison/notion/analysis-frame.json'),
       ('finder',HERE/'runs/finder-live-01',HERE/'runs/cross-app-01/comparison/finder/analysis-frame.json'),
       ('calculator',HERE/'runs/cross-app-01/calculator',HERE/'runs/cross-app-01/comparison/calculator/analysis-frame.json'),
       ('settings',HERE/'runs/cross-app-01/settings',HERE/'runs/cross-app-01/comparison/settings/analysis-frame.json')]


def main():
    dest=HERE/'runs/screen-map-v1';dest.mkdir(parents=True,exist_ok=True);summaries=[]
    for name,base,frame_path in CASES:
        out=dest/name;out.mkdir(exist_ok=True);start=time.perf_counter()
        subprocess.run([str(ROOT/'lsfg/.venv/bin/python'),str(HERE/'extract_visual_text.py'),
            '--image',str(base/'capture.png'),'--out',str(out/'ocr.json')],check=True,capture_output=True,text=True,timeout=30)
        ocr=json.loads((out/'ocr.json').read_text());contours=shapes(base/'capture.png')
        if ocr['image_sha256']!=contours['image_sha256']:raise ValueError('Evidence image mismatch')
        (out/'shapes.json').write_text(json.dumps(contours,indent=2))
        visual=dict(ocr,source=ocr['source']+' + '+contours['source'],items=ocr['items']+contours['items'],
                    processing_ms=ocr['processing_ms']+contours['processing_ms'])
        (out/'visual.json').write_text(json.dumps(visual,indent=2))
        im=Image.open(base/'capture.png');data=build_map(json.loads((base/'ax.json').read_text()),
            json.loads(frame_path.read_text()),(base/'capture.png').read_bytes(),im.size,visual)
        wall=(time.perf_counter()-start)*1000
        data['timing_ms'].update(ocr=ocr['processing_ms'],shapes=contours['processing_ms'],
            saved_image_to_map_wall=wall,scope='Single saved-image run; includes file reads, OCR subprocess startup, shapes and mapping. Excludes live capture/AX IPC, controller/hit-test and report rendering. Not p95.')
        (out/'mapping.json').write_text(json.dumps(data,indent=2)+'\n')
        render(out/'mapping.json',base/'capture.png',out/'review')
        summary={'case':name,'coverage':data['coverage'],'candidate_groups':len(data['candidate_targets']),
                 'capture_status':data['capture_status'],'capture_reasons':data['capture_reasons'],'timing_ms':data['timing_ms']}
        summaries.append(summary);print(json.dumps(summary),flush=True)
    report={'algorithm':'screen-map-v1','cases':summaries,'code_sha256':{
        f:hashlib.sha256((HERE/f).read_bytes()).hexdigest() for f in ['screen_map.py','canonicalize.py','extract_shapes.py','extract_visual_text.py']},
        'warning':'Unlabeled diagnostic. All AX nodes accounted for does not mean all clickable visual objects matched. No actual input executed.'}
    (dest/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    rows=''.join(f'<tr><td><a href="{s["case"]}/review/index.html">{s["case"]}</a></td><td>{s["coverage"]["ax_records"]}</td><td>{s["candidate_groups"]}</td><td>{s["coverage"]["statuses"]["unresolved"]}</td><td>{s["coverage"]["statuses"]["excluded"]}</td><td>{s["capture_status"]}</td><td>{s["timing_ms"]["saved_image_to_map_wall"]:.0f} ms</td></tr>' for s in summaries)
    (dest/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Screenshot/AX matching with independent image evidence</title><style>body{{font:16px system-ui;margin:35px;background:#f5f7fb;color:#172435}}td,th{{padding:14px;text-align:left;border-bottom:1px solid #ccc}}table{{background:white;border-collapse:collapse}}a{{color:#174ed0}}</style><h1>Screenshot/AX matching with independent image evidence</h1><p>Same algorithm on four saved captures. No desktop movement, external model calls or input execution. All nodes are retained with explicit dispositions.</p><p>“Visual support” means text or contour correspondence. It does not prove clickability, identity or occlusion. Candidate groups require live resolution. No labeled accuracy benchmark has been run.</p><table><tr><th>Inspect</th><th>AX records</th><th>Supported candidate groups</th><th>Unresolved records</th><th>Excluded records</th><th>Capture</th><th>Saved image → map</th></tr>{rows}</table><p>Times are single offline wall-clock runs, including OCR process startup and image processing; they exclude live screenshot/AX acquisition and execution checks. Capture “unverified” is not execution permission. <a href="summary.json">Full measurements</a>.</p>''')


if __name__=='__main__':main()
