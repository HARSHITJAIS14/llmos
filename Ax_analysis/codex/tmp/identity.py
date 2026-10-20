#!/usr/bin/env python3
import json, os, re, sys, unicodedata
from collections import Counter, defaultdict

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox','gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs','reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']

INTERACTIVE_ROLES={'button','checkbox','radiobutton','combobox','popupbutton','menuitem','menubaritem','link','textfield','textarea','searchfield','slider','tab','row','cell','outlinerow','disclosuretriangle','incrementor','switch','togglebutton','menubutton','colorwell','scrollbar','stepper'}

def load(app, fname):
    p=os.path.join(BASE,app,fname)
    if not os.path.exists(p): return None
    try:
        j=json.load(open(p))
    except Exception:
        return None
    if isinstance(j,dict) and 'data' in j:
        return j['data'] if j.get('ok',True) else None
    return j

def walk(n):
    if not isinstance(n,dict): return
    yield n
    for c in n.get('children',[]) or []:
        yield from walk(c)

def tree_of(data):
    if not data: return None
    if isinstance(data,dict):
        return data.get('tree')
    return None

def framework_class(app):
    m=load(app,'meta.json') or json.load(open(os.path.join(BASE,app,'meta.json')))
    return m

# classify frameworks
def classify(meta):
    fw=' '.join(meta.get('framework_signals',{}).get('frameworks',[]))
    hints=' '.join(meta.get('framework_signals',{}).get('hints',[]))
    exe=meta.get('framework_signals',{}).get('exe','')
    blob=(fw+' '+hints+' '+exe).lower()
    if 'electron' in blob or 'helper (gpu)' in blob: return 'electron'
    if 'qt' in blob and 'webengine' not in blob: return 'qt'
    return None

MANUAL={
 'brave_browser':'chromium','google_chrome':'chromium','firefox':'gecko','safari':'webkit',
 'discord':'electron','claude':'electron','notion':'electron','whatsapp':'electron/native?','gemini':'?','yt_music':'?','antigravity_ide':'electron',
 'finder':'appkit','calendar':'appkit','notes':'appkit','reminders':'appkit','textedit':'appkit','keynote':'appkit','music':'appkit',
 'microsoft_word':'custom-cxx','zoom_us':'custom-cxx','obs':'qt','vlc':'qt/appkit','utm':'appkit/swiftui','telegram':'opaque'
}

results={}
for app in APPS:
    per={'files':{}}
    for f in ['skeleton.json','full.json','forced.json','forced_warm.json']:
        d=load(app,f)
        t=tree_of(d)
        if t is None: continue
        nodes=list(walk(t))
        per['files'][f]={'snapshot_id': d.get('snapshot_id'), 'n':len(nodes), 'nodes':nodes,
                         'ref_count':d.get('ref_count'), 'window':d.get('window')}
    results[app]=per

# ---------- A. native_id coverage by kind ----------
print("=== A. native_id kinds & coverage (best capture = forced if bigger else full) ===")
report_a={}
for app in APPS:
    files=results[app]['files']
    best=None; bname=None
    for f in ['forced_warm.json','forced.json','full.json']:
        if f in files and (best is None or files[f]['n']>best['n']):
            best=files[f]; bname=f
    if not best: print(app,'NO CAPTURE'); continue
    nodes=best['nodes']
    kinds=Counter()
    nid_by_role=Counter()
    inter=[n for n in nodes if n.get('role') in INTERACTIVE_ROLES]
    inter_with=0
    for n in nodes:
        nid=n.get('native_id')
        if nid: kinds[nid.get('kind')]+=1
    for n in inter:
        if n.get('native_id'): inter_with+=1
    report_a[app]={'file':bname,'total':len(nodes),'kinds':dict(kinds),
                   'interactive':len(inter),'interactive_with_nid':inter_with,
                   'pct_all': round(100*sum(kinds.values())/len(nodes),1) if nodes else 0,
                   'pct_inter': round(100*inter_with/len(inter),1) if inter else None}
    print(f"{app:18s} {bname:16s} n={len(nodes):6d} nid_kinds={dict(kinds)} all%={report_a[app]['pct_all']} inter={len(inter)} inter%={report_a[app]['pct_inter']}")

# nonempty vs empty ax_identifier values
print("\n=== A2. ax_identifier value shapes (empty, _NS:, other) ===")
for app in APPS:
    files=results[app]['files']
    best=None
    for f in ['forced_warm.json','forced.json','full.json']:
        if f in files and (best is None or files[f]['n']>best['n']): best=files[f]
    if not best: continue
    shapes=Counter()
    for n in best['nodes']:
        nid=n.get('native_id')
        if not nid: continue
        v=nid.get('value','')
        k=nid.get('kind')
        if k!='ax_identifier':
            shapes[f'kind:{k}']+=1; continue
        if v=='' : shapes['empty']+=1
        elif re.match(r'^_NS:\d+$',v): shapes['_NS:n']+=1
        elif re.match(r'^[0-9]+$',v): shapes['numeric']+=1
        else: shapes['semantic']+=1
    if shapes: print(f"{app:18s} {dict(shapes)}")
