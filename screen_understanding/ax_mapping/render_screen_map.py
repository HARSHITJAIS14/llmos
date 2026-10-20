"""Evidence inspector: AX boxes, independent image regions and many-to-many links."""
import argparse
import html
import json
import os
from pathlib import Path


def render(mapping, image, out):
    out.mkdir(parents=True,exist_ok=True)
    data=json.loads(mapping.read_text())
    payload=json.dumps(data).replace('<','\\u003c')
    source=html.escape(os.path.relpath(image.resolve(),out.resolve()),quote=True)
    page='''<!doctype html><meta charset="utf-8"><title>AX ↔ screenshot evidence map</title>
<style>body{font:15px system-ui;margin:22px;background:#f4f6fa;color:#172435}h1{margin-bottom:7px}.warning{padding:12px;background:#fff0cf;border-radius:8px}button,input{padding:8px;margin:5px}.grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(300px,1fr);gap:18px}.shot{position:relative;align-self:start;background:white}.shot img{width:100%;display:block}svg{position:absolute;inset:0;width:100%;height:100%}ol{padding:0;list-style:none;max-height:75vh;overflow:auto}li{background:white;padding:10px;margin:5px 0;cursor:pointer;border-left:4px solid #aaa}small{display:block;overflow-wrap:anywhere;color:#475569}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:12px}.selected{background:#e0eaff}svg rect:hover{stroke-width:5}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style>
<h1>AX ↔ screenshot evidence map</h1>
<p>Green: independent visual support · amber: unresolved · red: excluded · gray: context. Visual support does not prove clickability. All input records are retained.</p>
<p class="warning" id="guard"></p><p id="summary"></p>
<div id="tabs"></div><input id="search" placeholder="Search native labels / roles / reasons"><label><input type="checkbox" id="ocr">Image OCR boxes</label><label><input type="checkbox" id="shapes">Image contour proposals</label>
<p><a href="MAPFILE">Full mapping JSON</a> · <a href="IMAGEFILE">Original screenshot</a></p>
<div class="grid"><div class="shot"><img src="IMAGEFILE"><svg id="overlay"></svg></div><aside><ol id="records"></ol><pre id="detail">Select a box or row to inspect its AX reference and linked image evidence.</pre></aside></div>
<details><summary>Coverage, timings and limitations</summary><pre id="metrics"></pre></details>
<script id="data" type="application/json">PAYLOAD</script>
<script>
const d=JSON.parse(document.querySelector('#data').textContent),svg=document.querySelector('#overlay');let mode='visually_supported',selected=null;
const colors={visually_supported:'#15803d',unresolved:'#d97706',excluded:'#dc2626',context_only:'#64748b'};
const V=new Map(d.visual_regions.map(v=>[v.id,v]));svg.setAttribute('viewBox',`0 0 ${d.image_size[0]} ${d.image_size[1]}`);
document.querySelector('#guard').textContent=`Capture: ${d.capture_status}. ${d.capture_reasons.join('; ')}. Execution authorization: false. Candidate groups require live resolution/revalidation.`;
document.querySelector('#summary').textContent=`${d.coverage.ax_records} AX records accounted for. ${d.candidate_targets.length} candidate groups with visual support. ${d.unmatched_visual_regions.length} image regions have no accepted AX label/shape link. These counts are not accuracy scores.`;
document.querySelector('#metrics').textContent=JSON.stringify({coverage:d.coverage,timing_ms:d.timing_ms,limits:d.limits},null,2);
function el(tag,attrs){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));return e;}
function box(b,color,dash=''){return el('rect',{x:b[0],y:b[1],width:b[2]-b[0],height:b[3]-b[1],fill:'transparent',stroke:color,'stroke-width':2,'stroke-dasharray':dash,'vector-effect':'non-scaling-stroke'});}
function select(r){selected=r;document.querySelector('#detail').textContent=JSON.stringify(r,null,2);draw();}
function draw(){svg.replaceChildren();const q=document.querySelector('#search').value.toLowerCase();const rows=d.records.filter(r=>(mode==='all'||r.status===mode)&&JSON.stringify([r.alias,r.label,r.role,r.exclusion_reasons,r.review_reasons]).toLowerCase().includes(q));
 const list=document.querySelector('#records');list.replaceChildren();
 for(const r of rows){const li=document.createElement('li');li.style.borderColor=colors[r.status];li.textContent=`${r.alias} · ${r.role} · ${r.label||'(unnamed)'}`;const s=document.createElement('small');s.textContent=[r.status,...r.exclusion_reasons,...r.review_reasons].join(' · ');li.append(s);li.onclick=()=>select(r);if(selected?.alias===r.alias)li.classList.add('selected');list.append(li);
 if(r.bbox_px){const b=box(r.bbox_px,colors[r.status]);const t=el('title',{});t.textContent=`${r.alias}: ${r.label} (${r.status})`;b.append(t);b.onclick=()=>select(r);svg.append(b);}}
 for(const v of d.visual_regions){const show=v.kind==='text'?document.querySelector('#ocr').checked:document.querySelector('#shapes').checked;if(show){const b=box(v.bbox,'#0891b2','3 3');const t=el('title',{});t.textContent=`${v.id} ${v.text||v.kind}`;b.append(t);svg.append(b);}}
 if(selected?.bbox_px){const b=selected.bbox_px;svg.append(box(b,'#4f46e5'));for(const link of selected.visual_links){const v=V.get(link.visual_id);if(!v)continue;svg.append(box(v.bbox,'#06b6d4'));svg.append(el('line',{x1:(b[0]+b[2])/2,y1:(b[1]+b[3])/2,x2:(v.bbox[0]+v.bbox[2])/2,y2:(v.bbox[1]+v.bbox[3])/2,stroke:'#7c3aed','stroke-width':2}));}}}
for(const m of ['visually_supported','unresolved','excluded','context_only','all']){const b=document.createElement('button');b.textContent=m+' '+(d.coverage.statuses[m]??d.coverage.ax_records);b.onclick=()=>{mode=m;selected=null;draw()};document.querySelector('#tabs').append(b);}
['search','ocr','shapes'].forEach(id=>document.getElementById(id).addEventListener('input',draw));draw();
</script>'''
    page=page.replace('MAPFILE',html.escape(os.path.relpath(mapping.resolve(),out.resolve()),quote=True)).replace('IMAGEFILE',source).replace('PAYLOAD',payload)
    (out/'index.html').write_text(page)
    return out/'index.html'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--map',type=Path,required=True);p.add_argument('--image',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(render(a.map,a.image,a.out))
