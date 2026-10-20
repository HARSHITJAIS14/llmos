"""Bidirectional AX/image evidence map. Accounts for all nodes; never executes input."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from canonicalize import canonicalize, text
from matcher import Frame, area, intersection, rect, words

CLICK={'click','press','axpress','doubleclick'}
EDIT={'setvalue','typetext','axsetvalue'}
SELECT={'select','check','uncheck','toggle','expand','collapse'}
SCROLL={'scroll'}
STRUCTURAL={'application','window','dialog','group','webarea','navigation','banner','main',
            'tabpanel','tablist','toolbar','table','row','column','list','outline','scrollarea'}


def capabilities(node):
    acts={str(a).lower().replace(' ','') for a in node['actions']}
    return [kind for kind,group in [('click',CLICK),('edit',EDIT),('select',SELECT),('scroll',SCROLL),
            ('secondary',{'rightclick','showmenu','axshowmenu'}),('reveal',{'scrollto','axscrolltopvisible'}),
            ('focus',{'setfocus'})] if acts & group]


def compatible_text(label, observed):
    a,b=words(label),words(observed)
    if not a or not b:return 0.0
    # A short AX label can occur in a longer OCR line, but neither is treated as perfect truth.
    return 2*len(a&b)/(len(a)+len(b))


def build_map(snapshot, metadata, image_bytes, image_size, visual):
    start=time.perf_counter();frame=Frame(metadata)
    if list(image_size)!=metadata['image_size']:raise ValueError('Image/frame dimensions differ')
    image_hash=hashlib.sha256(image_bytes).hexdigest()
    if visual.get('image_sha256')!=image_hash:raise ValueError('Visual evidence belongs to another image')
    if visual.get('image_size')!=list(image_size):raise ValueError('Visual evidence dimensions differ')
    graph=canonicalize(snapshot,metadata)
    capture_reasons=list(graph['capture_reasons'])
    expected=metadata.get('validation',{}).get('screenshot_sha256')
    if expected and expected!=image_hash:capture_reasons.append('capture_image_hash_mismatch')
    items=[];seen=set()
    for raw in visual.get('items',[]):
        vid=str(raw['id'])
        if vid in seen:raise ValueError('Duplicate visual evidence ID')
        seen.add(vid);box=rect(raw['bbox'])
        if intersection(box,frame.content)!=box:raise ValueError('Visual evidence outside captured content')
        conf=float(raw.get('confidence',0))
        if not math.isfinite(conf) or not 0<=conf<=1:raise ValueError('Invalid evidence confidence')
        item=dict(raw,id=vid,bbox=box)
        items.append(item)
    entity_for={mid:e for e in graph['entities'] for mid in e['member_ids']}
    by_id={n['id']:n for n in graph['all_nodes']}
    records=[];visual_links={v['id']:[] for v in items}
    for idx,n in enumerate(graph['all_nodes'],1):
        caps=capabilities(n);primary_interaction=bool(set(caps)&{'click','edit','select','scroll'})
        entity=entity_for.get(n['id']);box=n['bbox'];reject=[];review=[]
        states={str(s).lower() for s in n['states']}
        if box is None:
            reject.append('hidden_or_unprojectable')
        else:
            width=(box[2]-box[0])/frame.sx;height=(box[3]-box[1])/frame.sy
            if min(width,height)<3:reject.append('less_than_3_logical_points_thick')
            if n.get('visible_fraction',1)<.9:review.append('partially_outside_capture')
            aid=n['parent']
            while aid:
                a=by_id[aid]
                if a['role']=='scrollarea' and a.get('bbox') and area(intersection(box,a['bbox']))/area(box)<.5:
                    reject.append('outside_ancestor_scrollport');break
                aid=a['parent']
        if 'disabled' in states:reject.append('disabled')
        if primary_interaction and n['ref'] is None:review.append('no_native_action_reference')
        if entity and entity['overlap_ambiguities']:review.append('overlapping_control_entities')
        if box and primary_interaction and area(box)/area(frame.content)>.25:
            review.append('broad_interaction_surface')
        label=text(n)
        if primary_interaction and not label:review.append('unnamed_target')
        if primary_interaction and n['role'] in STRUCTURAL and not set(caps)&{'edit','scroll'}:
            review.append('structural_node_action_needs_resolution')
        links=[]
        if box and not reject:
            for v in items:
                overlap=area(intersection(box,v['bbox']))
                if not overlap:continue
                visual_coverage=overlap/area(v['bbox']);ax_coverage=overlap/area(box)
                if v.get('kind')=='text':
                    sim=compatible_text(label,v.get('text',''))
                    if sim<.5 or visual_coverage<.7 or v.get('confidence',0)<.45:continue
                    # A container containing matching text has context evidence, not a proven control.
                    spatial=.5+.5*math.sqrt(min(area(box),area(v['bbox']))/max(area(box),area(v['bbox'])))
                    score=.65*sim+.25*spatial+.1*v['confidence']
                    evidence_kind='ocr_label'
                elif v.get('kind')=='control_proposal':
                    iou=overlap/(area(box)+area(v['bbox'])-overlap)
                    if iou<.6 or v.get('confidence',0)<.6:continue
                    sim=None;score=iou;evidence_kind='detector_geometry'
                elif v.get('kind')=='shape_proposal':
                    iou=overlap/(area(box)+area(v['bbox'])-overlap)
                    if iou<.75:continue
                    sim=None;score=iou;evidence_kind='shape_geometry'
                else:continue
                link={'visual_id':v['id'],'kind':evidence_kind,'score':round(score,4),
                      'visual_coverage':round(visual_coverage,4),'ax_coverage':round(ax_coverage,4),
                      'text_similarity':sim}
                links.append(link)
            links.sort(key=lambda x:(-x['score'],x['visual_id']))
        if reject:
            status='excluded'
        elif not primary_interaction:
            status='context_only'
        elif review:
            status='unresolved'
        elif links:
            status='visually_supported'
        else:
            status='unresolved';review.append('no_independent_visual_evidence')
        for link in links:
            visual_links[link['visual_id']].append({'ax_node_id':n['id'],
                'entity_id':entity['id'] if entity else None,'status':status,'score':link['score']})
        records.append({'alias':f'A{idx:04}','ax_node_id':n['id'],'snapshot_id':graph['ax_observation']['snapshot_id'],
            'ref':n['ref'],'entity_id':entity['id'] if entity else None,'role':n['role'],
            'label':label,'value':n['value'],'states':n['states'],'native_actions':n['actions'],
            'capabilities':caps,'primary_interaction':primary_interaction,'bbox_px':box,'context':entity['context'] if entity else [],
            'status':status,'exclusion_reasons':reject,'review_reasons':review,'visual_links':links,
            'action_authorized':False})
    # Many-to-many links are explicit: OCR may label a text child and its interactive parent.
    for v in items:v['ax_links']=sorted(visual_links[v['id']],key=lambda x:(-x['score'],x['ax_node_id']))
    counts={s:sum(r['status']==s for r in records) for s in ['visually_supported','unresolved','context_only','excluded']}
    interaction=[r for r in records if r['primary_interaction']]
    grouped={}
    for r in interaction:
        if r['status']!='visually_supported':continue
        key=r['entity_id'] or r['ax_node_id']
        grouped.setdefault(key,[]).append(r)
    target_groups=[]
    for i,(eid,bindings) in enumerate(grouped.items(),1):
        target_groups.append({'alias':f'G{i:03}','entity_id':eid,
            'bindings':[{'alias':r['alias'],'ref':r['ref'],'role':r['role'],
                         'native_actions':r['native_actions'],'bbox_px':r['bbox_px']} for r in bindings],
            'label':bindings[0]['label'],'context':bindings[0]['context'],
            'visual_ids':sorted({v['visual_id'] for r in bindings for v in r['visual_links']}),
            'binding_status':'requires_live_resolution' if len(bindings)>1 else 'requires_live_revalidation',
            'action_authorized':False})
    return {'version':'screen-map-v1','image_sha256':image_hash,'image_size':list(image_size),
        'snapshot_id':graph['ax_observation']['snapshot_id'],'capture_status':'blocked' if capture_reasons else 'unverified',
        'capture_reasons':capture_reasons,'action_authorized':False,
        'evidence_source':visual.get('source'),'records':records,'visual_regions':items,
        'candidate_targets':target_groups,
        'executable_targets':[],
        'score_kind':'heuristic association ranking, not calibrated probability',
        'unmatched_visual_regions':[v['id'] for v in items if not v['ax_links']],
        'coverage':{'ax_records':len(records),'accounted_ax_records':sum(counts.values()),
                    'native_interaction_records':len(interaction),'statuses':counts,
                    'visual_regions':len(items),'visual_regions_without_ax_support':sum(not v['ax_links'] for v in items),
                    'visual_clickable_recall':None},
        'timing_ms':{'mapping':(time.perf_counter()-start)*1000,'ocr':visual.get('processing_ms')},
        'limits':['Visual support is an OCR/geometry association, not proven clickability or hit-test ownership.',
                  'Generic contour proposals can coincide with noninteractive decoration and do not establish icon semantics.',
                  'All clickable pixel objects cannot be enumerated from AX or OCR alone.',
                  'Before execution, revalidate live AX identity, supported action, enabled state, point ownership and observed result.',
                  'OCR/detector false positives, missing labels, and occlusion remain unresolved; no action executor is installed.']}


def main():
    from PIL import Image
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('ax','frame','image','visual','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();image=Image.open(a.image)
    data=build_map(json.loads(a.ax.read_text()),json.loads(a.frame.read_text()),a.image.read_bytes(),
                   image.size,json.loads(a.visual.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'coverage':data['coverage'],'capture_status':data['capture_status'],'timing_ms':data['timing_ms']},indent=2))


if __name__=='__main__':main()
