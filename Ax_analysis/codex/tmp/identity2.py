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
    # music/forced.json is contaminated (captured YT Music) -> use full
    order=['forced_warm.json','forced.json','full.json'] if app!='music' else ['full.json']
    best=None;bn=None
    for f in order:
        d=load(app,f)
        if not d or not d.get('tree'): continue
        n=sum(1 for _ in walk(d['tree']))
        if best is None or n>best[1]:
            best=(d,n); bn=f
    return (best[0] if best else None), bn

CAP={}
for a in APPS:
    d,f=best_capture(a)
    CAP[a]=(d,f)

# ---------- B. name vs value as identity, per role ----------
print("=== B. per-role: has name / has value / value-not-name (identity-in-value candidates) ===")
role_stats=defaultdict(lambda: Counter())
app_role_valonly=defaultdict(Counter)
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    for n in walk(d['tree']):
        r=n.get('role')
        if r not in INTERACTIVE_ROLES: continue
        name=n.get('name'); val=n.get('value')
        hn = isinstance(name,str) and name.strip()!=''
        hv = isinstance(val,str) and val.strip()!=''
        role_stats[r]['total']+=1
        if hn: role_stats[r]['name']+=1
        if hv: role_stats[r]['value']+=1
        if hv and not hn:
            role_stats[r]['value_only']+=1
            app_role_valonly[a][r]+=1
for r,c in sorted(role_stats.items(), key=lambda x:-x[1]['total']):
    t=c['total']
    print(f"{r:20s} total={t:5d} name%={100*c['name']/t:5.1f} value%={100*c['value']/t:5.1f} value_only%={100*c['value_only']/t:5.1f}")
print("\nvalue-only hotspots per app (role:count):")
for a,c in app_role_valonly.items():
    tot=sum(c.values())
    if tot>=3: print(f"  {a:18s} {dict(c.most_common(6))}")

# quantify rows specifically: where does row identity live?
print("\n=== B2. rows/cells/outlinerows: identity location ===")
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    rows=[n for n in walk(d['tree']) if n.get('role') in ('row','outlinerow','cell')]
    if not rows: continue
    hn=sum(1 for n in rows if isinstance(n.get('name'),str) and n['name'].strip())
    hv=sum(1 for n in rows if isinstance(n.get('value'),str) and str(n['value']).strip())
    # identity via descendant statictext?
    def has_text_desc(n):
        return any(c.get('role')=='statictext' and c.get('value') for c in walk(n))
    hd=sum(1 for n in rows if has_text_desc(n))
    print(f"{a:18s} rows={len(rows):4d} name={hn} value={hv} statictext_desc={hd}")

# ---------- C. (role,name) uniqueness among named interactives ----------
print("\n=== C. (role,name) uniqueness within best capture ===")
uni_rows=[]
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    named=[(n.get('role'),n.get('name')) for n in walk(d['tree'])
           if n.get('role') in INTERACTIVE_ROLES and isinstance(n.get('name'),str) and n['name'].strip()]
    if not named: continue
    c=Counter(named)
    uniq=sum(1 for k,v in c.items() if v==1)
    dup_named=sum(v for k,v in c.items() if v>1)
    pct=100*uniq/len(named)
    top_dupes=[(k,v) for k,v in c.most_common(3) if v>1]
    uni_rows.append((a,len(named),uniq,pct))
    print(f"{a:18s} named_inter={len(named):4d} unique_pairs={uniq:4d} pct_elements_unique={100*(len(named)-dup_named)/len(named):5.1f} dupes_top={top_dupes}")

# also (role,name,value) and (role,name)+bounds-free alternatives
print("\n=== C2. does adding value or native_id disambiguate dupes? ===")
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    nodes=[n for n in walk(d['tree']) if n.get('role') in INTERACTIVE_ROLES and isinstance(n.get('name'),str) and n['name'].strip()]
    if not nodes: continue
    c1=Counter((n.get('role'),n['name']) for n in nodes)
    dup_nodes=[n for n in nodes if c1[(n.get('role'),n['name'])]>1]
    if not dup_nodes: continue
    c2=Counter((n.get('role'),n['name'],str(n.get('value')),json.dumps(n.get('native_id'))) for n in dup_nodes)
    still=sum(v for k,v in c2.items() if v>1)
    print(f"{a:18s} dup_elements={len(dup_nodes):4d} still_ambiguous_with_value+nid={still:4d}")

# ---------- D. ref_id format & volatility ----------
print("\n=== D. ref_id format ===")
pat=re.compile(r'^@s[a-z0-9]+:e\d+$')
bad=0; tot=0; maxe=0
for a in APPS:
    for f in ['skeleton.json','full.json','forced.json','forced_warm.json']:
        d=load(a,f)
        if not d or not d.get('tree'): continue
        sid=d.get('snapshot_id')
        for n in walk(d['tree']):
            r=n.get('ref_id')
            if r is None: continue
            tot+=1
            if not pat.match(r): bad+=1; print("BAD",a,f,r)
            elif not r.startswith('@'+sid+':'): bad+=1; print("MISMATCH sid",a,f,r,sid)
print(f"ref_ids checked={tot} bad={bad}")
# which nodes get ref_ids? (ref = actionable?)
print("\nref_id assignment: pct of nodes with ref_id, by whether node has available_actions")
for a in APPS:
    d,f=CAP[a]
    if not d: continue
    nodes=list(walk(d['tree']))
    w=[n for n in nodes if n.get('ref_id')]
    act=[n for n in nodes if n.get('available_actions')]
    act_w=[n for n in act if n.get('ref_id')]
    noact_w=[n for n in w if not n.get('available_actions')]
    print(f"{a:18s} nodes={len(nodes):5d} ref={len(w):5d} actionable={len(act):5d} actionable_with_ref={len(act_w):5d} ref_without_actions={len(noact_w):4d}")
