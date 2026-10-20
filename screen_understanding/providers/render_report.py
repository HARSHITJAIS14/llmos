"""Render measured provider results; no API calls."""
from pathlib import Path
import html
import json
import statistics
import shutil

root=Path(__file__).parent
out=root/'runs/qwen-vision-01'
main=json.loads((out/'results.json').read_text())
single=json.loads((root/'runs/qwen-single-icon-01/results.json').read_text())
all_rows=main['results']+single['results']
shutil.copyfile('/tmp/qwen-openrouter-endpoints.json',out/'endpoint-metadata.json')
summary=[]
for provider in main['providers']:
 for task in ('single_icon','icons','screen'):
  rows=[r for r in all_rows if r['requested_provider']==provider and r['task']==task and not r.get('error')]
  summary.append({'provider':provider,'task':task,'n':len(rows),'median_seconds':statistics.median(r['total_seconds'] for r in rows),'minimum_seconds':min(r['total_seconds'] for r in rows),'maximum_seconds':max(r['total_seconds'] for r in rows),'median_first_visible_seconds':statistics.median(r['first_visible_seconds'] for r in rows),'under_500ms':sum(r['total_seconds']<=0.5 for r in rows)})
vision_cost=sum(r.get('usage',{}).get('cost',0) for r in all_rows)
smoke=[]
for p in sorted((root/'runs/qwen-smoke-01').glob('turn-*.json')):
 d=json.loads(p.read_text());raw=d['response'];smoke.append({'seconds':d['total_seconds'],'provider':raw['provider'],'content':raw['choices'][0]['message']['content'],'cost':raw.get('usage',{}).get('cost',0)})
report={'model':main['model'],'summary':summary,'vision_calls':len(all_rows),'vision_reported_cost_usd':vision_cost,'smoke_calls':smoke,'total_reported_cost_usd':vision_cost+sum(x['cost'] for x in smoke),'manual_assessment':'Eight hand-reviewed controls on one screenshot; unblinded qualitative assessment, not a general accuracy benchmark.'}
(out/'summary.json').write_text(json.dumps(report,indent=2))
parts=['<!doctype html><meta charset="utf-8"><title>Qwen hosted-provider benchmark</title><style>body{font:16px system-ui;background:#f4f5f7;max-width:1450px;margin:32px auto;padding:16px}section{background:white;padding:24px;margin:20px 0}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}img{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}.note{background:#fff4db;padding:16px}</style><h1>Qwen3.8 27B: hosted inference</h1><p class="note">No tested request met 500 ms. Timings include network, routing, image upload and answer generation from this Mac. They exclude image preparation, detection and OCR. Three repeats per task/provider are insufficient for p95/p99 or worst-case guarantees.</p><section><h2>Latency with reasoning disabled</h2><table><tr><th>Provider</th><th>Task</th><th>Median total</th><th>Observed range</th><th>Median first text</th></tr>']
for s in summary:
 parts.append(f'<tr><td>{s["provider"]}</td><td>{s["task"]}</td><td>{s["median_seconds"]:.3f} s</td><td>{s["minimum_seconds"]:.3f}–{s["maximum_seconds"]:.3f} s</td><td>{s["median_first_visible_seconds"]:.3f} s</td></tr>')
parts.append('</table><p>Persistent HTTPS connection within each provider; fallback disabled; no concurrent requests or retries. All 18 multi-label/screen responses parsed as JSON, and all icon-label responses returned the eight requested IDs. All 27 vision responses finished normally. This validates format, not factual accuracy.</p></section><section><h2>Eight controls with browser context</h2><img src="icon-context.png"><table><tr><th>ID</th><th>Manual reference</th><th>ModelRun, first response</th><th>Cerebras, first response</th><th>DeepInfra, first response</th></tr>')
references={38:'Back/forward navigation',39:'Sidebar / sidebar-menu control',41:'Search',47:'Notifications',48:'Profile/account',53:'Window close/minimize/fullscreen controls',54:'Tab overview',58:'YouTube navigation menu'}
labels={}
for provider in main['providers']:
 r=next(r for r in main['results'] if r['requested_provider']==provider and r['task']=='icons' and r['repeat']==1)
 labels[provider]={e['id']:e['label'] for e in r['parsed']['labels']}
for i,ref in references.items():
 parts.append('<tr><td>'+str(i)+'</td><td>'+html.escape(ref)+'</td>'+''.join('<td>'+html.escape(labels[p][i])+'</td>' for p in main['providers'])+'</tr>')
parts.append('</table><p>ModelRun labels were broadly correct across the three repeats, with “Manage tabs” less specific than “Tab overview.” Cerebras consistently mislabeled sidebar and tab overview, and named only one direction for the paired navigation control. DeepInfra identified tab overview twice but said “New tab” on repeat 3. The same public model is being served with different endpoint settings: metadata lists ModelRun FP4, Cerebras FP16, DeepInfra BF16. This experiment cannot isolate why their outputs differ.</p><p>This input supplies browser context and larger pixels than the earlier isolated 64-pixel Florence crops. It does not isolate model quality from the effect of context/resolution.</p></section><section><h2>Full-screen context outputs</h2>')
for provider in main['providers']:
 r=next(r for r in main['results'] if r['requested_provider']==provider and r['task']=='screen' and r['repeat']==1)
 parts.append('<h3>'+provider+'</h3><pre>'+html.escape(json.dumps(r['parsed'],indent=2))+'</pre>')
parts.append('</section><section><h2>Single-icon latency floor</h2><img src="../qwen-single-icon-01/single-icon.png"><p>One small crop, one-word answer, maximum 8 output tokens. This deliberately reduced task is not an equivalent screen-understanding benchmark. All nine answers were Search; completed-request times ranged from 0.543 to 0.908 seconds.</p></section><section><h2>Reasoning example</h2><p>Both text turns succeeded via Cerebras: 3.308 s then 0.696 s. Assistant reasoning_details were passed back unmodified and both calls included authentication headers. Reasoning content is not displayed here. Vision tests disabled reasoning; reported reasoning-token usage was zero.</p>')
parts.append(f'<p>Total API-reported cost for 29 calls: ${report["total_reported_cost_usd"]:.5f}. Reported by OpenRouter, not an independently reconciled invoice.</p></section><section><h2>All vision responses</h2>')
for r in all_rows:
 title=f'{r["requested_provider"]} / {r["task"]} / trial {r["repeat"]}: {r["total_seconds"]:.3f} s'
 parts.append('<details><summary>'+html.escape(title)+'</summary><pre>'+html.escape(r.get('content',str(r.get('error',''))))+'</pre></details>')
parts.append('</section>')
(out/'report.html').write_text(''.join(parts))
print(json.dumps(report,indent=2))
