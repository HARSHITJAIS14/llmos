"""Independent Apple Vision OCR on a saved image; no desktop access or model API."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import Quartz
from Foundation import NSURL

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lsfg/src'))
from lsfg.vision.ocr import recognize


def extract(path, level='fast'):
    start=time.perf_counter()
    data=path.read_bytes()
    source=Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(str(path.resolve())), None)
    img=Quartz.CGImageSourceCreateImageAtIndex(source,0,None) if source else None
    if img is None: raise ValueError('Cannot decode screenshot')
    w,h=int(Quartz.CGImageGetWidth(img)),int(Quartz.CGImageGetHeight(img))
    boxes=recognize(img,(0,0,w,h),level=level,min_conf=.45,max_boxes=1500)
    items=[]
    for i,b in enumerate(boxes):
        x,y,bw,bh=b.bounds
        items.append({'id':f'T{i+1:04}', 'kind':'text', 'bbox':[x,y,x+bw,y+bh],
                      'text':b.text,'confidence':b.confidence})
    return {'version':1,'source':'Apple Vision OCR '+level,'image_sha256':hashlib.sha256(data).hexdigest(),
            'status':'observations_returned' if items else 'empty_or_failed',
            'image_size':[w,h],'items':items,'processing_ms':(time.perf_counter()-start)*1000,
            'warning':'OCR can miss or misread visible text; it does not prove clickability.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--level',choices=['fast','accurate'],default='fast');a=p.parse_args()
    result=extract(a.image,a.level);a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'items':len(result['items']),'processing_ms':result['processing_ms'],'out':str(a.out)}))
