"""End-to-end ScreenVLM screen parsing with synchronized CUDA timings."""
import argparse
import json
from pathlib import Path
import re
import statistics
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',required=True)
    p.add_argument('--image',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--max-tokens',type=int,default=6192)
    p.add_argument('--runs',type=int,default=4)
    p.add_argument('--max-seconds',type=float,default=60)
    p.add_argument('--attention',choices=['eager','sdpa','flash_attention_2'],default='eager')
    a=p.parse_args()
    import torch
    import transformers
    from transformers import AutoProcessor, AutoModelForVision2Seq
    from transformers.generation.streamers import BaseStreamer
    from PIL import Image
    torch.set_num_threads(4)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    image=Image.open(a.image).convert('RGB');w,h=image.size
    start=time.perf_counter()
    processor=AutoProcessor.from_pretrained(a.model,local_files_only=True)
    model=AutoModelForVision2Seq.from_pretrained(a.model,torch_dtype=torch.bfloat16,attn_implementation=a.attention,local_files_only=True).to('cuda').eval()
    torch.cuda.synchronize();load=time.perf_counter()-start
    prompt=processor.apply_chat_template([{'role':'user','content':[{'type':'image'},{'type':'text','text':'Generate the screen representation for this UI:'}]}],add_generation_prompt=True)
    result={'model':'docling-project/ScreenVLM','revision':json.loads((Path(a.model)/'snapshot.json').read_text())['revision'],'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'transformers':transformers.__version__,'dtype':'bfloat16','use_cache':True,'attention':a.attention,'max_tokens':a.max_tokens,'max_generation_seconds':a.max_seconds,'image_size':[w,h],'load_seconds':load,'runs':[]}
    class Progress(BaseStreamer):
        def __init__(self, path):
            self.path=path;self.tokens=[];self.prompt=True
        def put(self,value):
            if self.prompt:self.prompt=False;return
            self.tokens.extend(value.reshape(-1).tolist())
            if len(self.tokens)%100==0:
                self.path.write_text(processor.tokenizer.decode(self.tokens,skip_special_tokens=False))
        def end(self):
            self.path.write_text(processor.tokenizer.decode(self.tokens,skip_special_tokens=False))
    for i in range(a.runs):
        torch.cuda.synchronize();start=time.perf_counter()
        inputs=processor(text=prompt,images=[image],return_tensors='pt').to('cuda',dtype=torch.bfloat16)
        torch.cuda.synchronize();preprocess=time.perf_counter()-start
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            ids=model.generate(**inputs,max_new_tokens=a.max_tokens,do_sample=False,use_cache=True,max_time=a.max_seconds,streamer=Progress(out/f"progress-{i}.txt"))
        torch.cuda.synchronize();generation=time.perf_counter()-start-preprocess
        new_ids=ids[:,inputs.input_ids.shape[1]:]
        text=processor.batch_decode(new_ids,skip_special_tokens=False)[0].lstrip()
        (out/f'output-{i}.txt').write_text(text)
        elements=[];issues=[]
        pattern=r'<(?P<tag>[a-zA-Z][a-zA-Z0-9_]*)>\s*<loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>([^<]*)</(?P=tag)>'
        for m in re.finditer(pattern,text):
            l,t,r,b=map(int,m.group(2,3,4,5))
            if not (0<=l<r<=500 and 0<=t<b<=500):issues.append(m.group(0));continue
            elements.append({'label':m.group('tag'),'bbox':[l*w/500,t*h/500,r*w/500,b*h/500],'text':m.group(6).strip()})
        total=time.perf_counter()-start
        result['runs'].append({'preprocess_seconds':preprocess,'generation_seconds':generation,'total_seconds':total,'output_tokens':new_ids.shape[1],'hit_token_limit':new_ids.shape[1]>=a.max_tokens,'hit_time_limit':generation>=a.max_seconds,'count':len(elements),'geometry_issues':issues,'elements':elements})
        if i:result['warm_median_seconds']=statistics.median(r['total_seconds'] for r in result['runs'][1:])
        result['peak_allocated_gpu_mb']=torch.cuda.max_memory_allocated()/1024**2
        (out/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({'run':i,**{k:v for k,v in result['runs'][-1].items() if k not in ('elements','geometry_issues')}}),flush=True)

if __name__=='__main__':main()
