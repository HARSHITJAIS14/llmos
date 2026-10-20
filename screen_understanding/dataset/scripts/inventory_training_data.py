"""Offline inventory of candidate training supervision; makes no API calls."""
import argparse, collections, hashlib, json
from pathlib import Path
from PIL import Image
from run_contextual_lite import validate_annotation


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--dataset',type=Path,default=Path(__file__).resolve().parents[1]/'captures_1000')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    meta={r['id']:r for line in (args.dataset/'manifest.jsonl').read_text().splitlines() if line.strip() for r in [json.loads(line)]}
    counts=collections.Counter();apps=collections.Counter();hashes=collections.defaultdict(list);rows=[];errors=[]
    masks=[]
    for f in sorted(args.run.glob('screen_*/annotation.json')):
        a=json.loads(f.read_text());sid=a['screen_id'];src=f.parent/'source.png'
        try:
            original=args.dataset/'screens'/f'{sid}.png'
            actual=hashlib.sha256(original.read_bytes()).hexdigest()
            if actual!=a['image']['sha256']:raise ValueError('Image hash mismatch')
            with Image.open(src) as im, Image.open(original) as original_im:
                if list(im.size)!=[a['image']['width'],a['image']['height']]:raise ValueError('Image dimensions mismatch')
                pixels=im.convert('RGB').tobytes()
                if im.size!=original_im.size or pixels!=original_im.convert('RGB').tobytes():raise ValueError('Report image pixels differ from source')
                pixel_hash=hashlib.sha256(str(im.size).encode()+pixels).hexdigest()
            props=json.loads((args.dataset/'proposals'/f'{sid}.json').read_text())['proposals']
            validate_annotation(a,props)
        except Exception as e:
            errors.append({'screen':sid,'error':str(e)[:300]});continue
        hashes[pixel_hash].append(sid);apps[meta.get(sid,{}).get('app_name','unknown')]+=1
        disps=a['coverage']['proposals_disposition'];accepted={pid for pid,d in disps.items() if d['disposition']=='retained'}
        counts['screens']+=1;counts['nodes']+=len(a['nodes']);counts['proposals']+=len(disps)
        counts['human_reviewed_screens']+=bool(a['annotation_provenance']['human_reviewed'])
        usable=0
        for n in a['nodes']:
            counts['level_'+n['level']]+=1
            linked=n['proposal_ids']
            geometry_ok=not linked or all(pid in accepted for pid in linked)
            if n['level']!='screen' and geometry_ok:usable+=1
            masks.append({'screen':sid,'node':n['id'],'candidate_for_teacher_supervision':n['level']!='screen' and geometry_ok,
                          'parent_supervision_candidate':n['level']!='screen' and geometry_ok,
                          'exact_text_supervision':bool(n['visible_text']),
                          'state_supervision_requires_review':True,'semantic_correctness_verified':False})
            counts['nodes_with_visible_text']+=bool(n['visible_text'])
        counts['candidate_nonroot_nodes']+=usable
        for d in disps.values():counts['disposition_'+d['disposition']]+=1
        rows.append({'screen':sid,'annotation':str(f.resolve()),'image':str(src.resolve()),'sha256':actual,
                     'app':meta.get(sid,{}).get('app_name','unknown'),'candidate_nodes':usable,
                     'capture_timestamp':meta.get(sid,{}).get('timestamp'),
                     'session_group_id':meta.get(sid,{}).get('session_group_id'),
                     'split':'unassigned_pending_duplicate_and_capture_group_review'})
    summary={'counts':dict(counts),'applications':dict(apps),'unique_pixel_images':len(hashes),
             'exact_duplicate_groups':[v for v in hashes.values() if len(v)>1],
             'errors':errors,'status':'Candidate teacher data; semantic quality unverified; no train/test split created.',
             'notes':['Unresolved/rejected proposal-linked nodes are excluded from candidate supervision.',
                      'Exact decoded-pixel grouping is not near-duplicate detection. Group related captures before splitting.',
                      'Field masks are eligibility hints, not assertions of ground truth.',
                      'Current role aliases such as slider->toggle and radio->checkbox require correction or masking before training.']}
    (args.output/'inventory.json').write_text(json.dumps(summary,indent=2))
    for name,records in [('screens.jsonl',rows),('candidate_masks.jsonl',masks)]:
        (args.output/name).write_text(''.join(json.dumps(r)+'\n' for r in records))
    print(json.dumps({'counts':dict(counts),'unique_pixel_images':len(hashes),'duplicate_groups':len(summary['exact_duplicate_groups']),'errors':errors[:3],'total_errors':len(errors)},indent=2))

if __name__=='__main__':main()
