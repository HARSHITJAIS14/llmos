"""Micro-caption inference and synchronized batch timing for a trained checkpoint."""
import argparse
import json
import statistics
import time
from pathlib import Path

import torch
from transformers import AutoModelForVision2Seq, AutoProcessor
from train_micro import PROMPT, panel


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--checkpoint',required=True)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--records',type=Path,required=True,help='JSONL with image relative to data, bbox, node and screen; no labels needed')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--batch-size',type=int,default=8)
    p.add_argument('--repeats',type=int,default=3)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4)
    processor=AutoProcessor.from_pretrained(args.checkpoint)
    processor.tokenizer.padding_side='left'
    model=AutoModelForVision2Seq.from_pretrained(args.checkpoint,torch_dtype=torch.bfloat16,
        attn_implementation='sdpa').cuda().eval()
    prompt=processor.apply_chat_template([{'role':'user','content':[{'type':'image'},{'type':'text','text':PROMPT}]}],add_generation_prompt=True)
    rows=[json.loads(line) for line in args.records.read_text().splitlines() if line.strip()]
    results=[]
    for repeat in range(args.repeats+1):
        torch.cuda.synchronize(); total_start=time.perf_counter()
        predictions=[]; batches=[]
        for offset in range(0,len(rows),args.batch_size):
            selected=rows[offset:offset+args.batch_size]
            start=time.perf_counter()
            images=[panel(args.data,r) for r in selected]
            cpu=processor(text=[prompt]*len(selected),images=[[im] for im in images],return_tensors='pt',padding=True)
            inputs={k:v.cuda().to(torch.bfloat16) if v.is_floating_point() else v.cuda() for k,v in cpu.items()}
            torch.cuda.synchronize(); prep=time.perf_counter()-start; generation_start=time.perf_counter()
            with torch.inference_mode():
                ids=model.generate(**inputs,max_new_tokens=5,do_sample=False,use_cache=True)
            torch.cuda.synchronize(); generation=time.perf_counter()-generation_start
            generated=ids[:,inputs['input_ids'].shape[1]:]
            text=processor.batch_decode(generated,skip_special_tokens=True)
            for r,label,tokens in zip(selected,text,generated.tolist()):
                special=set(processor.tokenizer.all_special_ids)
                content=[t for t in tokens if t not in special]
                predictions.append(dict(screen=r['screen'],node=r['node'],bbox=r['bbox'],label=label,
                    generated_content_tokens=len(content),hit_cap_without_eos=len(tokens)>=5 and processor.tokenizer.eos_token_id not in tokens,
                    provenance='micro-caption-v1'))
            batches.append(dict(count=len(selected),preprocess_seconds=prep,generation_seconds=generation,
                                batch_wall_seconds=time.perf_counter()-start))
        results.append(dict(repeat=repeat,warmup=repeat==0,wall_seconds=time.perf_counter()-total_start,batches=batches))
        (args.output/'predictions.json').write_text(json.dumps(predictions,indent=2))
        (args.output/'timing.json').write_text(json.dumps(dict(runs=results,boxes=len(rows),batch_size=args.batch_size,
             excludes=['detector','network','capture'],warm_median_seconds=statistics.median([r['wall_seconds'] for r in results[1:]]) if repeat else None),indent=2))
        print(json.dumps(results[-1]),flush=True)


if __name__=='__main__':main()
