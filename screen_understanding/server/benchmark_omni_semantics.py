"""Instrument OmniParser V2 detection + EasyOCR + Florence icon captions.
Overlap merge function comes from Microsoft's upstream utils.py; see upstream/OmniParser-LICENSE.
"""
import argparse
import ast
import json
from pathlib import Path
import statistics
import time
from typing import List


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--image',required=True)
    p.add_argument('--weights',required=True)
    p.add_argument('--caption',required=True)
    p.add_argument('--processor',required=True)
    p.add_argument('--upstream',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--runs',type=int,default=4)
    p.add_argument('--ocr-batch-size',type=int,default=1)
    a=p.parse_args()
    import numpy as np
    import cv2
    import torch
    from PIL import Image
    from ultralytics import YOLO
    import easyocr
    from transformers import AutoProcessor, AutoModelForCausalLM
    torch.set_num_threads(4)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    # Load only the pure overlap merger, avoiding upstream import-time model creation.
    tree=ast.parse(Path(a.upstream).read_text())
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='remove_overlap_new']
    assert len(funcs)==1
    scope={'List':List}
    exec(compile(ast.Module(body=funcs,type_ignores=[]),a.upstream,'exec'),scope)
    merge=scope['remove_overlap_new']
    image=Image.open(a.image).convert('RGB');im=np.asarray(image);w,h=image.size
    start=time.perf_counter()
    detector=YOLO(a.weights)
    reader=easyocr.Reader(['en'],gpu=True,model_storage_directory='/data/harshitj23/cache/easyocr')
    processor=AutoProcessor.from_pretrained(a.processor,trust_remote_code=True,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(a.caption,torch_dtype=torch.float16,trust_remote_code=True,attn_implementation='eager',local_files_only=True).to('cuda').eval()
    torch.cuda.synchronize()
    result={'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'load_seconds':time.perf_counter()-start,
            'variant':'OmniParser V2 detector + EasyOCR GPU + Florence2 icon captions; upstream overlap merge',
            'settings':{'imgsz':1280,'detector_conf':0.1,'detector_nms_iou':0.1,'merge_iou':0.7,'ocr_text_threshold':0.9,'ocr_batch_size':a.ocr_batch_size,'crop_size':64,'caption_batch':128,'caption_max_tokens':20,'cpu_threads':4},'image_size':[w,h],'runs':[]}
    for i in range(a.runs):
        torch.cuda.synchronize();start=time.perf_counter()
        ocr=reader.readtext(im,paragraph=False,text_threshold=0.9,batch_size=a.ocr_batch_size)
        torch.cuda.synchronize();ocr_end=time.perf_counter()
        prediction=detector.predict(image,imgsz=1280,conf=0.10,iou=0.10,device=0,verbose=False)[0]
        torch.cuda.synchronize();det_end=time.perf_counter()
        texts=[]
        for polygon,text,confidence in ocr:
            xs=[v[0] for v in polygon];ys=[v[1] for v in polygon]
            texts.append({'type':'text','bbox':[min(xs)/w,min(ys)/h,max(xs)/w,max(ys)/h], 'interactivity':False,'content':text,'source':'box_ocr_content_ocr'})
        boxes=[{'type':'icon','bbox':[b[0]/w,b[1]/h,b[2]/w,b[3]/h],'interactivity':True,'content':None} for b in prediction.boxes.xyxy.cpu().tolist()]
        elements=merge(boxes,0.7,texts)
        pending=[];crops=[]
        for e in elements:
            if e['content'] is None:
                l,t,r,b=e['bbox'];crop=im[max(0,int(t*h)):min(h,int(b*h)),max(0,int(l*w)):min(w,int(r*w))]
                if not crop.size:
                    e['caption_error']='empty crop';continue
                crops.append(Image.fromarray(cv2.resize(crop,(64,64))))
                pending.append(e)
        merge_end=time.perf_counter()
        for offset in range(0,len(crops),128):
            batch=crops[offset:offset+128]
            inputs=processor(images=batch,text=['<CAPTION>']*len(batch),return_tensors='pt',do_resize=False).to(device='cuda',dtype=torch.float16)
            with torch.inference_mode():
                ids=model.generate(input_ids=inputs['input_ids'],pixel_values=inputs['pixel_values'],max_new_tokens=20,num_beams=1,do_sample=False)
            captions=processor.batch_decode(ids,skip_special_tokens=True)
            for e,caption in zip(pending[offset:offset+128],captions):
                e['content']=caption.strip();e['source']='box_yolo_content_florence'
        torch.cuda.synchronize();end=time.perf_counter()
        run={'ocr_seconds':ocr_end-start,'detector_seconds':det_end-ocr_end,'merge_crop_seconds':merge_end-det_end,'caption_seconds':end-merge_end,'total_seconds':end-start,'ocr_count':len(ocr),'caption_count':len(crops),'count':len(elements),'elements':elements}
        result['runs'].append(run)
        if i:result['warm_median_seconds']=statistics.median(r['total_seconds'] for r in result['runs'][1:])
        result['peak_allocated_gpu_mb']=torch.cuda.max_memory_allocated()/1024**2
        (out/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({'run':i,**{k:v for k,v in run.items() if k!='elements'}}),flush=True)

if __name__=='__main__':main()
