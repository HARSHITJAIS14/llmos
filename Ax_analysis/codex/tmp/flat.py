import json,glob,os,collections
BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=sorted([d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,'meta.json'))])
def load(app,f):
    p=os.path.join(BASE,app,f)
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except Exception: return None
def flatten(tree):
    out=[]
    def walk(n,depth,path,parent):
        if not isinstance(n,dict): return
        rec=dict(n); rec.pop('children',None)
        rec['_depth']=depth; rec['_path']=path; rec['_parent']=parent
        rec['_nkids']=len(n.get('children') or [])
        out.append(rec)
        for i,c in enumerate(n.get('children') or []):
            walk(c,depth+1,path+'/'+str(i),rec)
    walk(tree,0,'',None)
    return out
def get(app,f):
    d=load(app,f)
    if not d: return None
    t=(d.get('data') or {}).get('tree')
    if not t: return None
    return flatten(t)
