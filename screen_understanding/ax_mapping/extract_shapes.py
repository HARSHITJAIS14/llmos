"""Generic image contours, independently of AX; proposals are not control detections."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2


def extract(path):
    start=time.perf_counter();data=path.read_bytes();img=cv2.imread(str(path))
    if img is None:raise ValueError('Cannot decode image')
    h,w=img.shape[:2];gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    # Low-contrast dark-mode buttons have much weaker edges than their glyphs.
    edge=cv2.Canny(gray,10,30)
    edge=cv2.morphologyEx(edge,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(3,3)))
    contours,_=cv2.findContours(edge,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    for c in contours:
        x,y,bw,bh=cv2.boundingRect(c)
        if min(bw,bh)<max(12,round(w/120)) or bw*bh>w*h*.25 or not .12<bw/bh<8:continue
        fill=cv2.contourArea(c)/(bw*bh)
        if fill<.45:continue
        boxes.append((x,y,x+bw,y+bh))
    kept=[]
    for b in sorted(boxes,key=lambda b:((b[2]-b[0])*(b[3]-b[1]),b)):
        if any((max(0,min(b[2],a[2])-max(b[0],a[0]))*max(0,min(b[3],a[3])-max(b[1],a[1]))) /
               ((b[2]-b[0])*(b[3]-b[1])+(a[2]-a[0])*(a[3]-a[1])-
                max(0,min(b[2],a[2])-max(b[0],a[0]))*max(0,min(b[3],a[3])-max(b[1],a[1])))>.85 for a in kept):continue
        kept.append(b)
    return {'source':'OpenCV closed-contour proposals; not a trained UI detector',
            'image_sha256':hashlib.sha256(data).hexdigest(),'image_size':[w,h],
            'items':[{'id':f'S{i:04}','kind':'shape_proposal','bbox':b} for i,b in enumerate(kept,1)],
            'processing_ms':(time.perf_counter()-start)*1000}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=extract(a.image);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({'items':len(r['items']),'processing_ms':r['processing_ms']}))
