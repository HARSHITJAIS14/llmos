"""Perception only: Jev populates detector boxes with typed semantic context.
No desktop control, AX input, OCR text, or action planning.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import statistics
import time
from PIL import Image,ImageDraw,ImageFont
from benchmark_jev import API,compliant_image,make_body,read_key_file

REGIONS={
 'browser_chrome':'the browser toolbar, address bar and tab strip at the top, excluding the web page itself',
 'app_header':'the application or webpage top navigation header, excluding browser chrome',
 'main_content':'the primary content or workspace area of the application or webpage',
 'secondary_panel':'the secondary side panel of recommendations, tools, or navigation alongside the main content',
 'details_panel':'the descriptive metadata/details area accompanying the primary content',
 'dialog':'a foreground modal dialog or popup overlay',
 'status_bar':'the application bottom status bar'}
APPS={'browser':'Web browser','editor':'Code or text editor','spreadsheet':'Spreadsheet','file_manager':'File manager','terminal':'Terminal','media':'Dedicated media app','settings':'Settings/preferences','other':'Another kind of application','unknown':'Cannot determine'}
PAGES={'video_watch':'Video watch page','search_results':'Search results','document':'Document or article','code_workspace':'Code editing workspace','table':'Spreadsheet/table','form':'Data entry form','conversation':'Messaging conversation','file_listing':'File listing','settings':'Settings/preferences view','other':'Other view','unknown':'Cannot determine'}
ROLES={'button':'Button/control','text_input':'Text input or search field','image':'Image or thumbnail','video':'Video content','text':'Text or heading','branding':'Logo or branding','tab':'Browser/app tab','container':'A group or panel','decoration':'Decoration','unknown':'Unknown'}
FUNCTIONS={k:v for k,v in [
 ('navigate','Back/forward navigation'),('sidebar','Toggle sidebar'),('search','Search'),('notifications','Notifications'),('profile','Account/profile'),('window_controls','Window controls'),('tab_overview','Tab overview'),('main_menu','Main navigation menu'),('new_tab','New tab'),('share','Share'),('download','Download'),('refresh','Reload/refresh'),('subscribe','Subscribe/follow'),('like','Like/rate'),('dislike','Dislike'),('more_options','Overflow options'),('create','Create content'),('voice_input','Voice input'),('filter','Filter/category selector'),('open_content','Open another content item'),('branding','Brand identity'),('content_only','Displays content; no identifiable control function'),('other','Another function'),('unknown','Cannot determine') ]}
SURFACES={'browser_ui':'Browser interface chrome','app_ui':'Actual application/webpage interface','embedded_content':'Depicted inside video/image/thumbnail content, not an outer application control','uncertain':'Cannot distinguish'}


def choice(instructions,criteria):return {'type':'choice','instructions':instructions,'criteria':criteria}


def box_pixels(answer,size):
 b=answer['box'];values=[b[k] for k in ('left','top','right','bottom')]
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):raise ValueError('Box coordinates must be finite numbers')
 l,t,r,bb=values
 if not(0<=l<r<=1 and 0<=t<bb<=1):raise ValueError('Invalid region geometry')
 return [l*size[0],t*size[1],r*size[0],bb*size[1]]


def spatial_relation(child,parent):
 l,t,r,b=child;x,y,rr,bb=parent
 area=(r-l)*(b-t)
 return max(0,min(r,rr)-max(l,x))*max(0,min(b,bb)-max(t,y))/area


def validate_answers(raw,questions):
 answers=raw.get('answers',{});issues=[]
 for key,q in questions.items():
  a=answers.get(key,{})
  if a.get('type')!=q['type']:issues.append(key+': missing/wrong answer type');continue
  if q['type']=='choice' and a.get('choice') not in q['criteria']:issues.append(key+': unknown choice')
  if q['type']=='noul' and not(isinstance(a.get('noul'),(float,int)) and 0<=a['noul']<=1):issues.append(key+': invalid presence')
 return issues


def call(api,image,questions,out,name,state_extra=None):
 start=time.perf_counter();body=make_body('jev-1.14.0',image,questions,'direct')
 if state_extra:body['state'].update(state_extra)
 build=time.perf_counter()-start
 result=api.call(body)
 record={'request_build_seconds':build,'question_count':len(questions),'questions':questions,**result}
 (out/(name+'.json')).write_text(json.dumps(record,indent=2))
 if result.get('error'):raise RuntimeError(json.dumps(result['error'])[:1000])
 issues=validate_answers(result['response'],questions)
 if issues:raise ValueError('; '.join(issues))
 return result['response']['answers'],{'api_seconds':result['seconds'],'build_seconds':build,'questions':len(questions),'usage':result['response'].get('usage',{})}


def render(image,result,out):
 import html
 w,h=image.size
 p=['<!doctype html><meta charset="utf-8"><title>Jev screen perception</title><style>body{font:16px system-ui;background:#f4f5f7;max-width:1500px;margin:32px auto;padding:16px}section{background:white;padding:24px;margin:20px 0}svg{width:100%;height:auto}rect:hover{fill:#ffc04d55;stroke-width:4}td,th{padding:8px;text-align:left;border-bottom:1px solid #ddd}table{width:100%;border-collapse:collapse}pre{white-space:pre-wrap;overflow-wrap:anywhere}.note{background:#fff0d4;padding:16px}</style><h1>Perception: detected boxes populated by Jev</h1><p class="note">Model hypotheses from one saved screenshot. No actions, AX tree or OCR transcription. Boxes are detected independently; roles, function, source and parent are predictions. Unknowns and geometry conflicts are retained.</p><section><h2>Context assembled from typed answers</h2><p>'+html.escape(result['description'])+'</p><pre>'+html.escape(json.dumps(result['timing_summary'],indent=2))+'</pre></section><section><h2>Regions</h2>']
 p.append(f'<svg viewBox="0 0 {w} {h}"><image href="submitted.png" width="{w}" height="{h}"/>')
 for reg in result['regions']:
  if 'submitted_box' not in reg or reg['presence_probability']<.5:continue
  l,t,r,b=reg['submitted_box'];color='#00a878' if reg['presence_probability']>=.5 else '#888888'
  p.append(f'<rect x="{l}" y="{t}" width="{r-l}" height="{b-t}" fill="none" stroke="{color}" stroke-width="2"><title>'+html.escape(f'{reg["id"]}: presence {reg["presence_probability"]}, box confidence {reg["confidence"]}')+'</title></rect>')
 p.append('</svg><p>Only regions with predicted presence ≥ 0.5 are drawn. All predictions remain in the table.</p><table><tr><th>Region</th><th>Presence probability</th><th>Box confidence</th></tr>')
 for reg in result['regions']:p.append(f'<tr><td>{reg["id"]}</td><td>{reg["presence_probability"]}</td><td>{reg["confidence"]}</td></tr>')
 p.append('</table></section><section><h2>Populated detector boxes</h2><p>Hover a box for its predicted context. All 54 saved detections are retained. The browser’s zoom can help inspect small controls.</p>')
 p.append(f'<svg viewBox="0 0 {w} {h}"><image href="submitted.png" width="{w}" height="{h}"/>')
 for e in result['elements']:
  l,t,r,b=e['submitted_box'];color='#e27d22' if e['surface']=='embedded_content' else '#e03c45'
  p.append(f'<rect x="{l}" y="{t}" width="{r-l}" height="{b-t}" fill="none" stroke="{color}" stroke-width="1.5"><title>'+html.escape(e['id']+': '+e['description'])+'</title></rect>')
 p.append('</svg><table><tr><th>ID</th><th>Role</th><th>Function</th><th>Surface</th><th>Parent</th><th>Issues</th></tr>')
 for e in result['elements']:
  p.append('<tr>'+''.join('<td>'+html.escape(str(e[k]))+'</td>' for k in ('id','role','function','surface','parent','issues'))+'</tr>')
 p.append('</table></section><section><h2>Limits</h2><p>The narrative uses a fixed vocabulary and templates; it is not generated prose or a verbatim transcription. Jev receives only pixels, numeric boxes and neutral IDs, not prior icon captions, OCR text or known answers. Region presence threshold 0.5 is provisional. Confidence is not calibrated on these screens. Parent attachment also requires at least 50% box overlap; rejected relationships remain visible as issues. Detector time is a prior GPU measurement, not included in measured replay time. Capture and remote detector transfer are not measured.</p></section>')
 (out/'report.html').write_text(''.join(p))


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--env-file',type=Path,required=True)
 p.add_argument('--image',type=Path,required=True)
 p.add_argument('--detections',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 p.add_argument('--repeats',type=int,default=3)
 a=p.parse_args();key=read_key_file(a.env_file,('TYPESAFE_API_KEY',))
 if not key:raise SystemExit('TYPESAFE_API_KEY missing')
 a.output.mkdir(parents=True,exist_ok=False)
 start=time.perf_counter();source=Image.open(a.image).convert('RGB');image,meta=compliant_image(source);image.save(a.output/'submitted.png')
 det=json.loads(a.detections.read_text());elements=[]
 for i,e in enumerate(det['elements']):
  l,t,r,b=e['bbox']
  if not(0<=l<r<=source.width and 0<=t<b<=source.height):raise ValueError('Detector coordinates invalid')
  elements.append({'id':f'b{i:03}','source_box':[l,t,r,b],'submitted_box':[l*meta['scale_x'],t*meta['scale_y'],r*meta['scale_x'],b*meta['scale_y']],'detector_confidence':e['confidence']})
 prep=time.perf_counter()-start
 api=API(key,'direct');layout_q={'app':choice('What application category is visible in `image`?',APPS),'view':choice('What type of view is visible in `image`?',PAGES)}
 for name,desc in REGIONS.items():
  layout_q[name+'_present']={'type':'noul','instructions':f'Is there a visible region corresponding to {desc} in `image`?'}
  layout_q[name+'_box']={'type':'box','instructions':desc+' in `image`'}
 layout,layout_t=call(api,image,layout_q,a.output,'layout')
 regions=[];parents={'root':'The entire application/screen','unknown':'Cannot determine a suitable containing region'}
 for name in REGIONS:
  reg={'id':name,'presence_probability':layout[name+'_present']['noul'],'confidence':layout[name+'_box'].get('confidence'),'raw_box':layout[name+'_box'].get('box'),'issues':[]}
  try:
   reg['submitted_box']=box_pixels(layout[name+'_box'],image.size)
   reg['source_box']=[v/s for v,s in zip(reg['submitted_box'],[meta['scale_x'],meta['scale_y'],meta['scale_x'],meta['scale_y']])]
   if reg['presence_probability']>=.5:parents[name]=REGIONS[name]
  except (ValueError,KeyError,TypeError) as exc:reg['issues'].append(str(exc))
  regions.append(reg)
 # Overlay labels only; all descriptive words come from Jev in the next stage.
 overlay=image.copy();draw=ImageDraw.Draw(overlay)
 font_path=Path('/System/Library/Fonts/Supplemental/Arial.ttf');font=ImageFont.truetype(str(font_path),12) if font_path.exists() else ImageFont.load_default()
 for e in elements:
  l,t,r,b=e['submitted_box'];draw.rectangle((l,t,r,b),outline='#ff4040',width=1);draw.text((l,max(0,t-12)),e['id'],font=font,fill='#ff4040')
 overlay.save(a.output/'numbered.png')
 q={}
 for e in elements:
  label=e['id'];ref=f'the numbered box {label} in `image` (coordinates in `detected_boxes`)'
  q[label+'_role']=choice('What visible UI role describes '+ref+'?',ROLES)
  q[label+'_function']=choice('What function is visually supported for '+ref+'? Choose unknown rather than guessing.',FUNCTIONS)
  q[label+'_surface']=choice('Is '+ref+' an actual application control or depicted inside image/video content?',SURFACES)
  q[label+'_parent']=choice('Which proposed region best contains '+ref+'? Consider coordinates and semantic grouping.',parents)
 extra={'detected_boxes':[{'id':e['id'],'bbox':e['submitted_box']} for e in elements],'regions':[{'id':r['id'],'bbox':r.get('submitted_box')} for r in regions if r['id'] in parents]}
 result={'mode':'vision-only perception','image':meta,'detector_source':str(a.detections),'detector_prior_warm_seconds':det.get('warm_median_seconds'),'regions':regions,'trials':[],'elements':elements}
 region_map={r['id']:r for r in regions}
 first_replay_seconds=None
 for repeat in range(a.repeats):
  trial_start=time.perf_counter()
  answers,timing=call(api,overlay,q,a.output,f'elements-{repeat+1}',extra)
  populated=[]
  for e in elements:
   node=dict(e);node['issues']=[];node['confidence']={}
   for head in ('role','function','surface','parent'):
    ans=answers[node['id']+'_'+head];node[head]=ans['choice'];node['confidence'][head]=ans.get('confidence')
   node['proposed_parent']=node['parent']
   if node['parent'] not in ('root','unknown'):
    overlap=spatial_relation(node['submitted_box'],region_map[node['parent']]['submitted_box']);node['parent_overlap_fraction']=overlap
    if overlap<.5:node['issues'].append('Predicted parent rejected: less than 50% overlap');node['parent']='unknown'
   node['description']=f"{node['role'].replace('_',' ')}; function: {node['function'].replace('_',' ')}; surface: {node['surface'].replace('_',' ')}; region: {node['parent'].replace('_',' ')}."
   populated.append(node)
  result['elements']=populated
  active=[r['id'].replace('_',' ') for r in regions if r['id'] in parents]
  result['description']=f"A {layout['app']['choice'].replace('_',' ')} showing a {layout['view']['choice'].replace('_',' ')} view. Proposed regions: {', '.join(active)}. "
  embedded=sum(e['surface']=='embedded_content' for e in populated);unknown=sum(any(e[k] in ('unknown','uncertain') for k in ('role','function','surface','parent')) for e in populated)
  result['description']+=f"Among {len(populated)} detected boxes, {embedded} are classified as embedded content and {unknown} have at least one unresolved field."
  result['trials'].append({'repeat':repeat+1,**timing,'enrichment_and_assembly_seconds':time.perf_counter()-trial_start,'elements':populated})
  if first_replay_seconds is None:first_replay_seconds=time.perf_counter()-start
  totals=[r['enrichment_and_assembly_seconds'] for r in result['trials']]
  result['timing_summary']={'image_preparation_seconds':prep,'layout_api_seconds':layout_t['api_seconds'],'layout_build_seconds':layout_t['build_seconds'],'layout_questions':len(layout_q),'element_questions_per_call':len(q),'detector_prior_warm_seconds':det.get('warm_median_seconds'),'enrichment_seconds':totals,'enrichment_median_seconds':statistics.median(totals),'first_replay_seconds':first_replay_seconds,'scope':'First replay: wall clock from image preparation through first populated result, including layout, annotation, request construction, API calls, raw response writes and local assembly. Repeats reuse layout, not image content interpretation. Excludes live capture, live detection, detector transfer, and report rendering. Detector prior is shown separately.'}
  (a.output/'result.json').write_text(json.dumps(result,indent=2));render(image,result,a.output)
  print(json.dumps({'repeat':repeat+1,'layout_seconds':layout_t['api_seconds'],'enrichment_seconds':totals[-1],'elements':len(elements),'embedded':embedded,'unresolved':unknown,'parent_conflicts':sum(bool(e['issues']) for e in populated)}),flush=True)

if __name__=='__main__':main()
