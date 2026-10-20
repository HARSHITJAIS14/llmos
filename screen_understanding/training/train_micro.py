"""Small VLM adaptation: max-five-token contextual box labels, frozen vision."""
import argparse
import collections
import json
import random
import re
import time
import hashlib
import os
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageOps
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForVision2Seq, AutoProcessor

MODEL = 'HuggingFaceTB/SmolVLM-256M-Instruct'
PROMPT = ('Left: screen with target outlined red. Right: enlarged target. '
          'Name the target with a short contextual label, at most five tokens.')


def compact_target(name, tokenizer):
    original = re.sub(r'\s+', ' ', name).strip().strip('. ')
    compact = re.sub(r'\b(navigation item|list item|section|panel|control|element)\b', '', original, flags=re.I)
    compact = re.sub(r'\s+', ' ', compact).strip(' -:')
    for value, method in [(original, 'original_name'), (compact, 'removed_generic_suffix')]:
        if value and 0 < len(tokenizer.encode(value, add_special_tokens=False)) <= 5:
            return value, method
    # Never slice a phrase in the middle merely to hit the token limit.
    return None, 'excluded_over_budget'


@lru_cache(maxsize=192)
def source_image(path):
    with Image.open(path) as source:
        return source.convert('RGB')


def panel(root, record):
    im = source_image(str(root / record['image']))
    x1, y1, x2, y2 = record['bbox']
    w, h = im.size
    assert 0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h
    # Fixed composite: one encoded image, both screen and local evidence.
    canvas = Image.new('RGB', (512, 512), '#777777')
    overview = ImageOps.contain(im, (256, 480))
    ox, oy = (256 - overview.width) // 2, (512 - overview.height) // 2
    canvas.paste(overview, (ox, oy))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([ox+x1*overview.width/w, oy+y1*overview.height/h,
                    ox+x2*overview.width/w, oy+y2*overview.height/h], outline='red', width=2)
    px, py = max(4, (x2-x1)*.15), max(4, (y2-y1)*.15)
    crop = im.crop((max(0, int(x1-px)), max(0, int(y1-py)), min(w, int(x2+px)), min(h, int(y2+py))))
    crop = ImageOps.contain(crop, (250, 480))
    canvas.paste(crop, (256+(256-crop.width)//2, (512-crop.height)//2))
    return canvas


class Records(Dataset):
    def __init__(self, rows, root): self.rows, self.root = rows, root
    def __len__(self): return len(self.rows)
    def __getitem__(self, i): return self.rows[i], panel(self.root, self.rows[i])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=2)
    p.add_argument('--batch-size', type=int, default=16)
    p.add_argument('--accumulate', type=int, default=1)
    p.add_argument('--max-steps', type=int, default=0)
    p.add_argument('--lr', type=float, default=2e-5)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--resume', type=Path)
    p.add_argument('--init-checkpoint', type=Path, help='Warm-start weights only on an expanded dataset; new optimizer')
    p.add_argument('--save-every', type=int, default=25)
    p.add_argument('--cache-workers', type=int, default=8)
    p.add_argument('--skip-baseline-predictions', action='store_true')
    p.add_argument('--overview-dropout', type=float, default=0.)
    args = p.parse_args()
    assert not (args.resume and args.init_checkpoint)
    assert 0<=args.overview_dropout<=1
    args.output.mkdir(parents=True, exist_ok=bool(args.resume))
    random.seed(args.seed); torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    processor = AutoProcessor.from_pretrained(MODEL)
    processor.image_processor.do_image_splitting = False
    processor.image_processor.size = {'longest_edge': 512}
    processor.tokenizer.padding_side = 'right'
    prompt = processor.apply_chat_template([{'role':'user', 'content':[
        {'type':'image'}, {'type':'text','text':PROMPT}]}], add_generation_prompt=True)
    rows = []
    counts = collections.Counter()
    for line in (args.data / 'records.jsonl').read_text().splitlines():
        r = json.loads(line)
        target, method = compact_target(r['semantic_name'], processor.tokenizer)
        counts[method] += 1
        if target:
            r.update(target=target, target_method=method,
                     target_tokens=len(processor.tokenizer.encode(target, add_special_tokens=False)))
            rows.append(r)
            counts[r['split']] += 1
    (args.output/'targets.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (args.output/'target_summary.json').write_text(json.dumps(dict(counts), indent=2))
    print('TARGETS', json.dumps(dict(counts)), flush=True)
    model = AutoModelForVision2Seq.from_pretrained(str(args.resume or args.init_checkpoint) if (args.resume or args.init_checkpoint) else MODEL, torch_dtype=torch.bfloat16,
                                                   attn_implementation='sdpa').cuda()
    frozen = 0
    for name, parameter in model.named_parameters():
        if 'vision_model' in name:
            parameter.requires_grad_(False); frozen += parameter.numel()
    assert frozen > 0, 'Vision module naming changed; refuse accidental full fine-tune'
    model.config.use_cache = False
    config = dict(vars(args)); config = {k:str(v) if isinstance(v,Path) else v for k,v in config.items()}
    config.update(model=MODEL, revision=getattr(model.config,'_commit_hash',None),
                  frozen_parameters=frozen, trainable_parameters=sum(x.numel() for x in model.parameters() if x.requires_grad),
                  gpu=torch.cuda.get_device_name(), torch=torch.__version__, prompt=PROMPT)
    (args.output/'config.json').write_text(json.dumps(config, indent=2))
    processor.save_pretrained(args.output/'processor')
    print('CONFIG', json.dumps(config), flush=True)

    def device(batch):
        result={}
        for k,v in batch.items():
            if k=='pixel_values' and v.dtype==torch.uint8:
                result[k]=(v.cuda().float().div(255.).sub(.5).div(.5)).to(torch.bfloat16)
            else:
                result[k]=v.cuda().to(torch.bfloat16) if v.is_floating_point() else v.cuda()
        return result

    train_rows = [r for r in rows if r['split']=='train']
    val_rows = [r for r in rows if r['split']=='val']
    random.Random(42).shuffle(val_rows)
    val_rows = val_rows[:128]
    # Tokenize the generation prompt ONCE and concatenate independently encoded
    # targets. BPE can merge the last prompt newline with the first target symbol
    # if raw strings are concatenated and re-tokenized; that caused v1's crash.
    reference_image=panel(args.data,train_rows[0])
    reference=processor(text=prompt,images=[reference_image],return_tensors='pt')
    prefix=reference['input_ids'][0].tolist()
    extra_keys=set(reference)-{'input_ids','attention_mask','pixel_values','pixel_attention_mask'}
    assert not extra_keys, f'Unsupported processor inputs: {extra_keys}'
    assert reference['pixel_values'].shape==(1,1,3,512,512)
    manual=torch.from_numpy(np.array(reference_image)).permute(2,0,1).float().div(255.).sub(.5).div(.5)
    torch.testing.assert_close(manual,reference['pixel_values'][0,0],rtol=0,atol=1e-6)
    assert reference['pixel_attention_mask'].all(), 'Fixed composite must have no masked pixels'
    for r in rows:
        ids=processor.tokenizer.encode(r['target'],add_special_tokens=False)
        assert 1<=len(ids)<=5
        assert processor.tokenizer.decode(ids)==r['target']
        r['target_ids']=ids+[processor.tokenizer.eos_token_id]
    print('PREFLIGHT_TOKEN_TARGETS_PASSED',len(rows),flush=True)
    cache={}
    def build_cache(r):
        return (r['screen'],r['node']), torch.from_numpy(np.array(panel(args.data,r))).permute(2,0,1).contiguous()
    with ThreadPoolExecutor(max_workers=args.cache_workers) as pool:
        for i,(key,value) in enumerate(pool.map(build_cache,train_rows+val_rows)):
            cache[key]=value
            if (i+1)%1000==0: print('CACHE',i+1,flush=True)
    print('CACHE_READY',len(cache),flush=True)

    def collate(recs):
        length=len(prefix)+max(len(r['target_ids']) for r in recs)
        ids=torch.full((len(recs),length),processor.tokenizer.pad_token_id,dtype=torch.long)
        attention=torch.zeros_like(ids); labels=torch.full_like(ids,-100)
        for i,r in enumerate(recs):
            combined=prefix+r['target_ids']; n=len(combined)
            ids[i,:n]=torch.tensor(combined); attention[i,:n]=1
            labels[i,len(prefix):n]=torch.tensor(r['target_ids'])
        assert (labels[:,:len(prefix)]==-100).all()
        return dict(input_ids=ids,attention_mask=attention,labels=labels,
                    pixel_values=torch.stack([cache[(r['screen'],r['node'])] for r in recs]).unsqueeze(1),
                    pixel_attention_mask=reference['pixel_attention_mask'].expand(len(recs),-1,-1,-1))
    # Every target and every cached training/validation image is checked before
    # the first optimizer step; cover the former boundary failure explicitly.
    for subset in (train_rows,val_rows):
        for start in range(0,len(subset),args.batch_size):
            batch=collate(subset[start:start+args.batch_size])
            assert (batch['labels']!=-100).any(1).all()
    print('PREFLIGHT_ALL_BATCHES_PASSED',flush=True)
    val_loader=DataLoader(val_rows,batch_size=args.batch_size,collate_fn=collate)
    optimizer = torch.optim.AdamW([x for x in model.parameters() if x.requires_grad], lr=args.lr, weight_decay=.01)

    @torch.inference_mode()
    def validate():
        model.eval(); total=0.; n=0
        for batch in val_loader:
            bs=batch['input_ids'].shape[0]
            total += float(model(**device(batch)).loss)*bs; n+=bs
        return total/max(n,1)

    @torch.inference_mode()
    def predictions(tag):
        model.eval()
        selected=val_rows[:24]
        output=[]
        for r in selected:
            im=panel(args.data,r)
            inputs=device(processor(text=prompt,images=[im],return_tensors='pt'))
            torch.cuda.synchronize(); start=time.perf_counter()
            ids=model.generate(**inputs,max_new_tokens=5,do_sample=False,use_cache=True)
            torch.cuda.synchronize()
            out=processor.tokenizer.decode(ids[0,inputs['input_ids'].shape[1]:],skip_special_tokens=True)
            output.append(dict(screen=r['screen'],node=r['node'],target=r['target'],prediction=out,
                               model_seconds=time.perf_counter()-start))
        (args.output/f'{tag}_predictions.json').write_text(json.dumps(output,indent=2))

    baseline=validate(); print('BASELINE_VAL_LOSS',baseline,flush=True)
    if not args.skip_baseline_predictions: predictions('baseline')
    metrics=open(args.output/'metrics.jsonl','a',buffering=1)
    step=0; best=baseline; started=time.perf_counter(); start_epoch=0; start_batch=0
    fingerprint=hashlib.sha256(json.dumps([(r['screen'],r['node'],r['target_ids']) for r in train_rows]).encode()).hexdigest()
    if args.resume:
        state=torch.load(args.resume/'training_state.pt',map_location='cpu',weights_only=False)
        assert state['fingerprint']==fingerprint
        assert state['batch_size']==args.batch_size and state['accumulate']==args.accumulate
        assert state['seed']==args.seed
        optimizer.load_state_dict(state['optimizer'])
        step=state['step']; start_epoch=state['epoch']; start_batch=state['next_batch']; best=state['best']
        torch.set_rng_state(state['torch_rng']); torch.cuda.set_rng_state_all(state['cuda_rng']); random.setstate(state['python_rng'])
        print('RESUMED',step,start_epoch,start_batch,flush=True)

    def save_checkpoint(epoch,next_batch):
        target=args.output/f'checkpoint-{step:06d}'
        if target.exists(): return target
        temp=args.output/f'.checkpoint-{step:06d}-tmp'; temp.mkdir()
        model.save_pretrained(temp); processor.save_pretrained(temp)
        torch.save(dict(optimizer=optimizer.state_dict(),epoch=epoch,next_batch=next_batch,step=step,best=best,
                        fingerprint=fingerprint,batch_size=args.batch_size,accumulate=args.accumulate,seed=args.seed,
                        torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),python_rng=random.getstate()),temp/'training_state.pt')
        (temp/'complete.json').write_text(json.dumps(dict(step=step,epoch=epoch,next_batch=next_batch)))
        temp.rename(target)
        latest=args.output/'latest.json.tmp'; latest.write_text(json.dumps(dict(checkpoint=str(target),step=step))); latest.replace(args.output/'latest.json')
        checkpoints=sorted(args.output.glob('checkpoint-*'))
        for old in checkpoints[:-2]: shutil.rmtree(old)
        print('CHECKPOINT',str(target),flush=True)
        return target

    for epoch in range(start_epoch,args.epochs):
        order=list(train_rows); random.Random(args.seed+epoch).shuffle(order)
        loader=DataLoader(order,batch_size=args.batch_size,collate_fn=collate)
        model.train(); optimizer.zero_grad(set_to_none=True)
        for i,batch in enumerate(loader):
            if epoch==start_epoch and i<start_batch: continue
            inputs=device(batch)
            if args.overview_dropout:
                # Blank the overview for a subset, retaining the same crop and
                # prompt/serving layout. This tests dependence on page context.
                drop=torch.rand(inputs['pixel_values'].shape[0],device='cuda')<args.overview_dropout
                inputs['pixel_values'][drop,:,:,:,:256]=(119/255.-.5)/.5
            loss=model(**inputs).loss
            if not torch.isfinite(loss): raise RuntimeError('Nonfinite loss')
            group_start=(i//args.accumulate)*args.accumulate
            group_size=min(args.accumulate,len(loader)-group_start)
            (loss/group_size).backward()
            if (i+1)%args.accumulate==0 or i+1==len(loader):
                norm=torch.nn.utils.clip_grad_norm_([x for x in model.parameters() if x.requires_grad],1.)
                if not torch.isfinite(norm): raise RuntimeError('Nonfinite gradient')
                optimizer.step(); optimizer.zero_grad(set_to_none=True); step+=1
                item=dict(epoch=epoch+1,step=step,loss=float(loss),elapsed_seconds=time.perf_counter()-started,
                          peak_gpu_mb=torch.cuda.max_memory_allocated()/1024**2)
                metrics.write(json.dumps(item)+'\n')
                if step%10==0 or step==1: print('TRAIN',json.dumps(item),flush=True)
                if step%args.save_every==0: save_checkpoint(epoch,i+1)
                if args.max_steps and step>=args.max_steps:break
        val=validate(); print('VALIDATION',epoch+1,val,flush=True)
        metrics.write(json.dumps(dict(epoch=epoch+1,step=step,val_loss=val))+'\n')
        checkpoint=args.output/'last'; model.save_pretrained(checkpoint); processor.save_pretrained(checkpoint)
        save_checkpoint(epoch,i+1)
        if val<best:
            best=val; model.save_pretrained(args.output/'best'); processor.save_pretrained(args.output/'best')
        predictions(f'epoch_{epoch+1}')
        if args.max_steps and step>=args.max_steps:break
    (args.output/'completed.json').write_text(json.dumps(dict(steps=step,baseline_val_loss=baseline,best_val_loss=best)))
    print('COMPLETED',step,flush=True)


if __name__=='__main__':
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
