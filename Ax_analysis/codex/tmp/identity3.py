#!/usr/bin/env python3
import json, os, re, unicodedata
from collections import Counter, defaultdict

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox','gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs','reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']
INTERACTIVE_ROLES={'button','checkbox','radiobutton','combobox','popupbutton','menuitem','menubaritem','link','textfield','textarea','searchfield','slider','tab','row','cell','outlinerow','disclosuretriangle','incrementor','switch','togglebutton','menubutton','colorwell','scrollbar','stepper'}

def load(app,f):
    p=os.path.join(BASE,app,f)
    if not os.path.exists(p): return None
    try: j=json.load(open(p))
    except Exception: return None
    if isinstance(j,dict) and 'data' in j:
        return j['data'] if j.get('ok',True) else None
    return j

def walk(n):
    if not isinstance(n,dict): return
    yield n
    for c in n.get('children',[]) or []:
        yield from walk(c)

def best_capture(app):
    order=['forced_warm.json','forced.json','full.json'] if app!='music' else ['full.json']
    best=None;bn=None
    for f in order:
        d=load(app,f)
        if not d or not d.get('tree'): continue
        n=sum(1 for _ in walk(d['tree']))
        if best is None or n>best[1]: best=(d,n);bn=f
    return (best[0] if best else None),bn

CAP={a:best_capture(a) for a in APPS}

# ---------- E. bidi / invisible char scan across ALL string fields ----------
INVIS={'‎':'LRM','‏':'RLM','‪':'LRE','‫':'RLE','‬':'PDF','‭':'LRO','‮':'RLO','​':'ZWSP','‌':'ZWNJ','‍':'ZWJ','⁠':'WJ','﻿':'BOM','⁦':'LRI','⁧':'RLI','⁨':'FSI','⁩':'PDI','­':'SHY'}
print("=== E. invisible/bidi chars in name/value/description, ALL files ===")
grand=defaultdict(Counter)
for a in APPS:
    hits=Counter(); fields=Counter(); total_strings=0
    for f in ['skeleton.json','full.json','forced.json','forced_warm.json']:
        d=load(a,f)
        if not d or not d.get('tree'): continue
        for n in walk(d['tree']):
            for fld in ('name','value','description'):
                s=n.get(fld)
                if not isinstance(s,str): continue
                total_strings+=1
                found=set(ch for ch in s if ch in INVIS)
                for ch in found:
                    hits[INVIS[ch]]+=1; fields[fld]+=1
                    grand[a][INVIS[ch]]+=1
    if hits: print(f"{a:18s} strings={total_strings:6d} chars={dict(hits)} fields={dict(fields)}")
print("apps with no invisible chars:", [a for a in APPS if not grand[a]])

# ---------- F. do bounds disambiguate remaining dupes? ----------
print("\n=== F. dupes after adding bounds ===")
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    nodes=[n for n in walk(d['tree']) if n.get('role') in INTERACTIVE_ROLES and isinstance(n.get('name'),str) and n['name'].strip()]
    c1=Counter((n.get('role'),n['name']) for n in nodes)
    dup=[n for n in nodes if c1[(n.get('role'),n['name'])]>1]
    if not dup: continue
    c2=Counter((n.get('role'),n['name'],json.dumps(n.get('bounds'),sort_keys=True)) for n in dup)
    still=sum(v for k,v in c2.items() if v>1)
    print(f"{a:18s} dup={len(dup):4d} still_dup_with_bounds={still}")

# ---------- G. ax_dom_identifier value shapes ----------
print("\n=== G. ax_dom_identifier values (shape only) ===")
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    vals=[n['native_id']['value'] for n in walk(d['tree']) if n.get('native_id',{}).get('kind')=='ax_dom_identifier']
    if not vals: continue
    shapes=Counter()
    for v in vals:
        if v=='': shapes['empty']+=1
        elif re.match(r'^[A-Za-z][\w-]*$',v): shapes['html_id_like']+=1
        else: shapes['other']+=1
    ex=[v for v in vals if v][:4]
    print(f"{a:18s} n={len(vals)} shapes={dict(shapes)} examples={ex}")

# ---------- H. description as identity (Discord/Electron) ----------
print("\n=== H. interactives that are unnamed but have description ===")
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    inter=[n for n in walk(d['tree']) if n.get('role') in INTERACTIVE_ROLES]
    unnamed=[n for n in inter if not (isinstance(n.get('name'),str) and n['name'].strip())]
    withdesc=[n for n in unnamed if isinstance(n.get('description'),str) and n['description'].strip()]
    if inter:
        print(f"{a:18s} inter={len(inter):4d} unnamed={len(unnamed):4d} unnamed_with_desc={len(withdesc):4d}")

# ---------- I. Finder/Reminders identity-in-value textfields: are they actionable? ----------
print("\n=== I. value-only textfields: actions present? role context ===")
for a in ['finder','keynote','textedit','reminders','notes','notion']:
    d,f=CAP[a]
    if not d: continue
    tf=[n for n in walk(d['tree']) if n.get('role')=='textfield' and (isinstance(n.get('value'),str) and n['value'].strip()) and not (isinstance(n.get('name'),str) and n['name'].strip())]
    acts=Counter()
    for n in tf: acts[tuple(n.get('available_actions',[]))]+=1
    print(f"{a:18s} value_only_textfields={len(tf)} action_profiles={dict(acts.most_common(4))}")

# ---------- J. snapshot_id alphabet / length ----------
print("\n=== J. snapshot_id + ref ordinal stats ===")
sids=[]
for a in APPS:
    for f in ['skeleton.json','full.json','forced.json','forced_warm.json']:
        d=load(a,f)
        if d and d.get('snapshot_id'): sids.append(d['snapshot_id'])
import re as _re
print("count:",len(sids),"unique:",len(set(sids)),"all match ^s[0-9a-z]{11,14}$:",all(_re.match(r'^s[0-9a-z]{11,14}$',s) for s in sids), "len range:",min(map(len,sids)),max(map(len,sids)))
# e-ordinals: sequential pre-order?
d,_=CAP['finder']
ords=[int(n['ref_id'].split(':e')[1]) for n in walk(d['tree']) if n.get('ref_id')]
print("finder e-ordinals: min",min(ords),"max",max(ords),"count",len(ords),"strictly_increasing_preorder:",ords==sorted(ords))
