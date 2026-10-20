"""Compare fixed checkpoints on held-out targets and measure whole requests."""
import argparse
import collections
import html
import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import torch
from transformers import AutoModelForVision2Seq, AutoProcessor
from train_micro import panel, source_image, PROMPT


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--targets',type=Path,required=True)
    p.add_argument('--old',required=True)
    p.add_argument('--new',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4)
    rows=[json.loads(l) for l in a.targets.read_text().splitlines() if json.loads(l)['split']=='test']
    cohorts=json.loads((a.data/'evaluation_cohorts.json').read_text())
    processor=AutoProcessor.from_pretrained(a.new); processor.tokenizer.padding_side='left'
    prompt=processor.apply_chat_template([{'role':'user','content':[{'type':'image'},{'type':'text','text':PROMPT}]}],add_generation_prompt=True)
    first=panel(a.data,rows[0]); ref=processor(text=prompt,images=[first],return_tensors='pt')
    prefix=ref['input_ids']; pmask=ref['pixel_attention_mask']
    assert ref['pixel_values'].shape==(1,1,3,512,512) and pmask.all()
    special=set(processor.tokenizer.all_special_ids)

    def array(r): return torch.from_numpy(np.array(panel(a.data,r))).permute(2,0,1).contiguous()
    def inputs(arrays):
        pixels=torch.stack(arrays).unsqueeze(1).cuda().float().div(255.).sub(.5).div(.5).to(torch.bfloat16)
        return dict(input_ids=prefix.expand(len(arrays),-1).cuda(),attention_mask=ref['attention_mask'].expand(len(arrays),-1).cuda(),
                    pixel_values=pixels,pixel_attention_mask=pmask.expand(len(arrays),-1,-1,-1).cuda())
    for r in rows[::max(1,len(rows)//5)]:
        im=panel(a.data,r); standard=processor(text=prompt,images=[im],return_tensors='pt')
        manual=array(r).float().div(255.).sub(.5).div(.5)
        torch.testing.assert_close(manual,standard['pixel_values'][0,0],atol=1e-6,rtol=0)
        assert torch.equal(prefix,standard['input_ids'])
    print('PREPROCESS_EQUIVALENCE_PASSED',flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool: cache=list(pool.map(array,rows))
    predictions={}; summaries={}; timing=[]
    for tag,checkpoint in [('old',a.old),('new',a.new)]:
        model=AutoModelForVision2Seq.from_pretrained(checkpoint,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
        output=[]
        with torch.inference_mode():
            # Compare generated IDs using the reference and accelerated paths.
            fast=inputs(cache[:1]); standard=processor(text=prompt,images=[first],return_tensors='pt')
            standard={k:v.cuda().to(torch.bfloat16) if v.is_floating_point() else v.cuda() for k,v in standard.items()}
            one=model.generate(**fast,max_new_tokens=5,do_sample=False,use_cache=True)
            two=model.generate(**standard,max_new_tokens=5,do_sample=False,use_cache=True)
            assert torch.equal(one,two), 'Optimized/reference generation differ'
            for start in range(0,len(rows),32):
                batch=inputs(cache[start:start+32]); ids=model.generate(**batch,max_new_tokens=5,do_sample=False,use_cache=True)
                new_ids=ids[:,batch['input_ids'].shape[1]:]
                labels=processor.batch_decode(new_ids,skip_special_tokens=True)
                for r,label,tokens in zip(rows[start:start+32],labels,new_ids.tolist()):
                    output.append(dict(screen=r['screen'],node=r['node'],bbox=r['bbox'],role=r['role'],target=r['target'],
                                       label=label,cohort=cohorts[r['screen']],tokens=len([t for t in tokens if t not in special]),
                                       hit_cap=processor.tokenizer.eos_token_id not in tokens and len(tokens)>=5))
        predictions[tag]=output
        (a.output/f'{tag}_predictions.json').write_text(json.dumps(output,indent=2))
        groups={}
        for cohort in ['all','old_regression','new_capture']:
            subset=[r for r in output if cohort=='all' or r['cohort']==cohort]
            groups[cohort]=dict(boxes=len(subset),screens=len({r['screen'] for r in subset}),
                exact=sum(r['label'].strip().casefold()==r['target'].strip().casefold() for r in subset),
                appearance=sum('appearance' in r['label'].casefold() for r in subset),
                appearance_target_mismatch=sum('appearance' in r['label'].casefold() and 'appearance' not in r['target'].casefold() for r in subset),
                window_icon=sum(r['label'].strip().casefold()=='window icon' for r in subset),cap_hits=sum(r['hit_cap'] for r in subset))
        summaries[tag]=groups; print(tag,json.dumps(groups),flush=True)
        if tag=='new':
            by_screen=collections.defaultdict(list)
            for r in rows:by_screen[r['screen']].append(r)
            screens=[v for v in by_screen.values() if len(v)>=50]
            assert screens
            for n in [1,8,32,50]:
                measured=[]
                for repeat in range(11):
                    selected=screens[repeat%len(screens)][:n]
                    # No reuse of composite cache in latency measurements.
                    if repeat==0:source_image.cache_clear()
                    torch.cuda.synchronize(); start=time.perf_counter()
                    arr=[array(r) for r in selected]; batch=inputs(arr)
                    torch.cuda.synchronize(); prep=time.perf_counter()-start; decode_start=time.perf_counter()
                    with torch.inference_mode(): ids=model.generate(**batch,max_new_tokens=5,do_sample=False,use_cache=True)
                    torch.cuda.synchronize(); generation=time.perf_counter()-decode_start
                    labels=processor.batch_decode(ids[:,batch['input_ids'].shape[1]:],skip_special_tokens=True)
                    # Include response construction and token decoding in wall time.
                    response=[dict(node=r['node'],bbox=r['bbox'],label=label) for r,label in zip(selected,labels)]
                    json.dumps(response)
                    wall=time.perf_counter()-start
                    measured.append(dict(repeat=repeat,warmup=repeat==0,screen=selected[0]['screen'],preprocess_seconds=prep,
                                         model_seconds=generation,wall_seconds=wall))
                warm=[r['wall_seconds'] for r in measured[1:]]
                result=dict(boxes=n,runs=measured,warm_median_seconds=statistics.median(warm),observed_max_seconds=max(warm),
                            warm_measured_requests=len(warm),batch_size=n,excludes=['capture','detector','network','queue','model_loading'])
                timing.append(result);print('LATENCY',n,result['warm_median_seconds'],flush=True)
                (a.output/'latency.json').write_text(json.dumps(timing,indent=2))
        del model; torch.cuda.empty_cache()
    (a.output/'summary.json').write_text(json.dumps(summaries,indent=2))
    # Fixed random gallery, not selected by success category.
    sample=random.Random(19).sample(range(len(rows)),min(60,len(rows)))
    (a.output/'crops').mkdir()
    body=[]
    for i in sample:
        r=rows[i]; filename=f"{r['screen']}_{r['node']}.jpg";panel(a.data,r).save(a.output/'crops'/filename)
        values=[f"<img width='256' src='crops/{filename}'>",html.escape(r['screen']+' '+r['node']+' '+cohorts[r['screen']]),
                html.escape(r['target']),html.escape(predictions['old'][i]['label']),html.escape(predictions['new'][i]['label'])]
        body.append('<tr>'+''.join('<td>'+v+'</td>' for v in values)+'</tr>')
    (a.output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Expanded model comparison</title>'
        '<style>body{font:15px system-ui;margin:30px}td,th{padding:12px;border:1px solid #ddd}table{border-collapse:collapse}</style>'
        '<h1>Old versus expanded checkpoint</h1><p>Fixed random sample of held-out boxes. Teacher names are unreviewed targets. '
        'See summary.json for all-box metrics and latency.json for whole-request timings.</p><table><tr><th>Input</th><th>Box</th><th>Teacher</th>'
        '<th>Old model</th><th>Expanded model</th></tr>'+''.join(body)+'</table>')
    (a.output/'completed.json').write_text(json.dumps(dict(status='completed',boxes=len(rows))))
    print('EVALUATION_COMPLETED',flush=True)


if __name__=='__main__':main()
