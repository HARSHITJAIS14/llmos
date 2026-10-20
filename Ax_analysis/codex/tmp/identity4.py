#!/usr/bin/env python3
import json, os, re
from collections import Counter, defaultdict

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox','gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs','reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']
def load(app,f):
    p=os.path.join(BASE,app,f)
    if not os.path.exists(p): return None
    try: j=json.load(open(p))
    except Exception: return None
    if isinstance(j,dict) and 'data' in j:
        return j['data'] if j.get('ok',True) else None
    return j
def walk(n,parent=None):
    if not isinstance(n,dict): return
    yield n,parent
    for c in n.get('children',[]) or []:
        yield from walk(c,n)
def best(app):
    order=['forced_warm.json','forced.json','full.json'] if app!='music' else ['full.json']
    b=None;bn=None
    for f in order:
        d=load(app,f)
        if not d or not d.get('tree'): continue
        n=sum(1 for _ in walk(d['tree']))
        if b is None or n>b[1]: b=(d,n);bn=f
    return (b[0] if b else None),bn

# 0. music/full.json really Apple Music?
m=load('music','full.json'); print("music/full app:", m.get('app'), "window title:", (m.get('window') or {}).get('title'))

# 1. parent context of value-only textfields in finder/keynote/textedit
for a in ['finder','keynote','textedit','reminders']:
    d,_=best(a)
    pr=Counter()
    for n,p in walk(d['tree']):
        if n.get('role')=='textfield' and isinstance(n.get('value'),str) and n['value'].strip() and not (isinstance(n.get('name'),str) and n['name'].strip()):
            pr[p.get('role') if p else None]+=1
    print(a, "value-only textfield parents:", dict(pr))

# 2. LRM positions in word/safari/whatsapp
import unicodedata
for a in ['microsoft_word','safari','whatsapp']:
    d,_=best(a)
    pos=Counter(); roles=Counter()
    for n,p in walk(d['tree']):
        for fld in ('name','value'):
            s=n.get(fld)
            if isinstance(s,str) and '‎' in s:
                roles[(n.get('role'),fld)]+=1
                idx=s.index('‎')
                pos['leading' if idx==0 else ('interior' if idx< len(s)-1 else 'trailing')]+=1
    print(a, "LRM positions:", dict(pos), "roles:", dict(roles.most_common(5)))

# 3. React auto-id pattern in dom identifiers
pat_react=re.compile(r'^(_r_.+_|:r.+:)$')
for a in APPS:
    d,_=best(a)
    if not d: continue
    vals=[n['native_id']['value'] for n,p in walk(d['tree']) if n.get('native_id',{}).get('kind')=='ax_dom_identifier']
    if not vals: continue
    r=sum(1 for v in vals if pat_react.match(v))
    print(f"{a:18s} dom_ids={len(vals):4d} react_auto={r:4d} ({100*r/len(vals):.0f}%)")

# 4. which roles get ref_id WITHOUT available_actions
agg=Counter()
for a in APPS:
    d,_=best(a)
    if not d: continue
    for n,p in walk(d['tree']):
        if n.get('ref_id') and not n.get('available_actions'):
            agg[n.get('role')]+=1
print("refs w/o actions by role:", dict(agg.most_common(12)))

# 5. notion still-dup-with-bounds: what are they (roles only + zero-size?)
d,_=best('notion')
nodes=[n for n,p in walk(d['tree']) if n.get('role') in {'button','combobox','textfield','link','cell','row','tab','checkbox','switch','menuitem'} and isinstance(n.get('name'),str) and n['name'].strip()]
c1=Counter((n['role'],n['name']) for n in nodes)
dup=[n for n in nodes if c1[(n['role'],n['name'])]>1]
c2=Counter((n['role'],n['name'],json.dumps(n.get('bounds'),sort_keys=True)) for n in dup)
amb=[k for k,v in c2.items() if v>1]
for k in amb[:6]:
    b=json.loads(k[2]) if k[2]!='null' else None
    print("notion ambiguous:", k[0], repr(k[1])[:40], "bounds:", b)

# 6. per-framework rollup of ax_identifier coverage on interactives
FW={'finder':'appkit','calendar':'appkit','notes':'appkit','reminders':'appkit','textedit':'appkit','keynote':'appkit','music':'appkit','utm':'appkit',
 'safari':'appkit+webkit','vlc':'qt','obs':'qt','microsoft_word':'custom','zoom_us':'custom','whatsapp':'catalyst/swift','gemini':'electron?','telegram':'opaque',
 'brave_browser':'chromium','google_chrome':'chromium','firefox':'gecko','discord':'electron','claude':'electron','notion':'electron','antigravity_ide':'electron','yt_music':'chromium-pwa'}
INT={'button','checkbox','radiobutton','combobox','popupbutton','menuitem','link','textfield','searchfield','slider','tab','row','cell','switch','menubutton','scrollbar'}
roll=defaultdict(lambda:[0,0,0])
for a in APPS:
    d,_=best(a)
    if not d: continue
    for n,p in walk(d['tree']):
        if n.get('role') in INT:
            fw=FW[a]
            roll[fw][0]+=1
            k=n.get('native_id',{}).get('kind') if n.get('native_id') else None
            if k=='ax_identifier': roll[fw][1]+=1
            elif k=='ax_dom_identifier': roll[fw][2]+=1
for fw,(t,ax,dom) in sorted(roll.items()):
    print(f"{fw:16s} inter={t:5d} ax_identifier%={100*ax/t:5.1f} ax_dom%={100*dom/t:5.1f}")

# 7. does (role,name) stay stable across full vs forced snapshots? (selector re-resolution)
print("\nstability of (role,name) sets across full vs forced:")
for a in APPS:
    dfull=load(a,'full.json'); dforce=load(a,'forced.json')
    if not dfull or not dforce or not dfull.get('tree') or not dforce.get('tree'): continue
    s1={(n.get('role'),n.get('name')) for n,p in walk(dfull['tree']) if n.get('name')}
    s2={(n.get('role'),n.get('name')) for n,p in walk(dforce['tree']) if n.get('name')}
    if not s1: continue
    inter=len(s1&s2)
    print(f"{a:18s} full_named={len(s1):4d} forced_named={len(s2):4d} overlap%={100*inter/len(s1):5.1f}")
