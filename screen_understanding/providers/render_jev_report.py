"""Render saved Jev visual measurements without making API calls."""
from pathlib import Path
import html
import json
import statistics

root=Path(__file__).parent/'runs/jev-direct-vision-02'
d=json.loads((root/'results.json').read_text());rows=d['results']
expected={'38':'navigation','39':'sidebar','41':'search','47':'notifications','48':'profile','53':'window_controls','54':'tab_overview','58':'main_menu'}
summary=[]
for task in ('icons','grounding','single_icon'):
 rr=[r for r in rows if r['task']==task];times=[r['seconds'] for r in rr]
 summary.append({'task':task,'n':len(rr),'median_seconds':statistics.median(times),'minimum_seconds':min(times),'maximum_seconds':max(times),'under_500ms':sum(t<=0.5 for t in times)})
summary_data={'route':'direct TypeSafe /v1/systemone','model':'jev-1.14.0','timings':summary,'total_valid_visual_calls':len(rows),'under_500ms':sum(r['seconds']<=.5 for r in rows),'manual_references':expected,'notes':['One screenshot, three repeats per task, not a tail-latency or general accuracy benchmark.','Eight labels from predefined choices differs from Qwen free-form labels.','Image sizes differ from Qwen because of Jev API limits.','Grounding reference boxes are previous detector proposals, not human-certified clickable bounds.','First image attempt was rejected at 1568x256; direct API requires at least 280 pixels per side. This failed request is preserved separately and excluded from successful-call timings.']}
(root/'summary.json').write_text(json.dumps(summary_data,indent=2))
parts=['<!doctype html><meta charset="utf-8"><title>Jev 1.14 vision benchmark</title><style>body{font:16px system-ui;background:#f4f5f7;max-width:1450px;margin:32px auto;padding:16px}section{background:white;padding:24px;margin:20px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}img,svg{width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}.note{background:#fff4db;padding:16px}.bad{background:#ffe7e7}</style><h1>Jev 1.14: direct visual decisions</h1><p class="note">Some calls finished within 500 ms; the requirement was not met consistently. These results do not establish calibrated confidence, general icon accuracy or safe clickability.</p><section><h2>Complete-response timings</h2><table><tr><th>Task</th><th>Median</th><th>Observed range</th><th>Under 500 ms</th></tr>']
for s in summary:
 parts.append(f'<tr><td>{s["task"]}</td><td>{s["median_seconds"]*1000:.0f} ms</td><td>{s["minimum_seconds"]*1000:.0f}–{s["maximum_seconds"]*1000:.0f} ms</td><td>{s["under_500ms"]}/{s["n"]}</td></tr>')
parts.append('</table><p>Measured from this Mac to TypeSafe directly using persistent HTTPS. Includes upload, network and inference; excludes preparing screenshots and encoding JSON. Sequential requests without automatic retries. One warm-up text request was run separately (1.263 s) in another process/connection. Screenshot is the same source used for earlier experiments.</p></section><section><h2>Contextual icon labels</h2><img src="icon-context.png"><table><tr><th>ID</th><th>Manual reference</th><th>Trial 1</th><th>Trial 2</th><th>Trial 3</th></tr>')
icon_rows=[r for r in rows if r['task']=='icons']
for i,ref in expected.items():
 parts.append('<tr><td>'+i+'</td><td>'+ref+'</td>')
 for r in icon_rows:
  a=r['response']['answers'][i];cls='bad' if a['choice']!=ref else ''
  parts.append(f'<td class="{cls}">{html.escape(a["choice"])} (confidence {a["confidence"]:.2f})</td>')
 parts.append('</tr>')
parts.append('</table><p>Predefined options included the eight intended functions, unknown, and new-tab/clear/copy distractors. The same options were offered for every question. Side bar was confused with tab overview in all trials. Tab overview was correct once and confused with copy twice. Confidence is provider-reported and has not been calibrated on our data.</p><p>Submitted context image: 1568 × 280, scaled from 2398 × 390 and padded at the bottom. Earlier Qwen tests used 2398 × 390 and open-ended labels, so the comparison is not controlled for resolution or output vocabulary.</p></section><section><h2>Grounding — first trial</h2><p>Colored boxes are predictions; same-colored dashed boxes are prior detector references. Hover predicted boxes for target and confidence. Reference rectangles are not certified clickable bounds.</p>')
r=next(r for r in rows if r['task']=='grounding');w,h=r['image']['submitted_size']
parts.append(f'<svg viewBox="0 0 {w} {h}"><image href="screen.png" width="{w}" height="{h}"/>')
colors={'search':'#ff3333','sidebar':'#14dc80','tabs':'#49aaff'}
for name,color in colors.items():
 a=r['response']['answers'][name+'_box'];b=a['box'];x=b['left']*w;y=b['top']*h;ww=(b['right']-b['left'])*w;hh=(b['bottom']-b['top'])*h
 parts.append(f'<rect x="{x}" y="{y}" width="{ww}" height="{hh}" fill="none" stroke="{color}" stroke-width="3"><title>{name}, confidence {a["confidence"]}</title></rect>')
 l,t,rr,bb=d['reference_boxes'][name];parts.append(f'<rect x="{l*w}" y="{t*h}" width="{(rr-l)*w}" height="{(bb-t)*h}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="5 4"/>')
parts.append('</svg><p>Search and sidebar are broadly localized; the tab-overview box is shifted and varies across repeats. Precise target bounds still need human review. Submitted full screen: 1568 × 1197, downscaled from 2398 × 1830.</p><table><tr><th>Trial</th><th>Absent Delete account: P(present)</th><th>Returned box confidence</th></tr>')
for r in rows:
 if r['task']=='grounding':
  a=r['response']['answers'];parts.append(f'<tr><td>{r["repeat"]}</td><td>{a["absent_present"]["noul"]}</td><td>{a["absent_box"]["confidence"]}</td></tr>')
parts.append('</table><p>Box always returns coordinates, including for absent targets. The absent-target box is deliberately not overlaid or treated as a valid target. Presence was correctly near zero in all three trials.</p></section><section><h2>Single-icon task</h2><p>Native-pixel crop padded to the required 280 × 280 minimum. Search was selected correctly in all three trials. See raw responses for provider-reported confidence.</p></section><section><h2>Raw typed answers</h2>')
for r in rows:
 parts.append('<details><summary>'+html.escape(f'{r["task"]} trial {r["repeat"]}: {r["seconds"]:.3f} s')+'</summary><pre>'+html.escape(json.dumps(r['response'],indent=2))+'</pre></details>')
parts.append('</section>')
(root/'report.html').write_text(''.join(parts))
print(json.dumps(summary_data,indent=2))
