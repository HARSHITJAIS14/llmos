#!/usr/bin/env python3
import json, os, collections

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox','gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs','reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']
CLICKY={'Click','Press','Toggle','Select'}

def nodes_of(x, parent=None):
    if isinstance(x,dict):
        if 'role' in x:
            yield x, parent
            for c in x.get('children') or []:
                yield from nodes_of(c, x)
        else:
            for v in x.values():
                yield from nodes_of(v, parent)
    elif isinstance(x,list):
        for v in x:
            yield from nodes_of(v, parent)

def load(app,name):
    p=os.path.join(BASE,app,name)
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except Exception: return None

def b_ok(b): return isinstance(b,dict) and all(k in b for k in ('x','y','width','height'))

def tree_of(app):
    src='forced.json'; d=load(app,src)
    if d is None or not d.get('ok',True): src='full.json'; d=load(app,src)
    return src,d

# ---- 1. the "exactly 3 zero-size buttons" pattern ----
print('=== ZERO-SIZE BUTTON IDENTITY (abstract: role/name-class/pos only) ===')
for app in ['calendar','finder','keynote','microsoft_word','safari','textedit','zoom_us','gemini']:
    src,d=tree_of(app)
    if not d: continue
    for n,p in nodes_of(d.get('data',d)):
        b=n.get('bounds')
        if b_ok(b) and (b['width']<=0 or b['height']<=0) and set(n.get('available_actions') or [])&CLICKY:
            nm=n.get('name','')
            # classify name without quoting personal content: these are UI chrome names, safe-ish; keep short
            print(' %-15s role=%-12s size=%gx%g pos=(%g,%g) name=%r states=%s'%(app,n['role'],b['width'],b['height'],b['x'],b['y'],(nm or '')[:28],n.get('states')))

print()
# ---- 2. discord on_out (not offscreen-marked but outside desktop) ----
print('=== NOT-OFFSCREEN NODES WITH BOUNDS OUTSIDE 3840x1600 DESKTOP ===')
for app in ['discord','claude','whatsapp','music','calendar']:
    src,d=tree_of(app)
    out=[]
    for n,p in nodes_of(d.get('data',d)):
        b=n.get('bounds')
        if not b_ok(b) or b['width']<=0: continue
        if 'offscreen' in (n.get('states') or []): continue
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        if not(0<=cx<=3840 and 0<=cy<=1600): out.append((n,b,cx,cy))
    print(app, len(out))
    kinds=collections.Counter((n['role'], 'x>3840' if c>3840 else 'y>1600' if cy>1600 else 'neg') for n,b,c,cy in out)
    for k,v in kinds.most_common(8): print('   ',k,v)
    for n,b,cx,cy in out[:4]:
        print('    e.g.', n['role'], b)

print()
# ---- 3. offscreen semantics: where are offscreen-marked nodes actually? ----
print('=== OFFSCREEN-MARKED NODE LOCATION vs WINDOW ===')
for app in APPS:
    src,d=tree_of(app)
    if not d: continue
    data=d.get('data',d)
    # find window node bounds (first role==window)
    winb=None
    for n,p in nodes_of(data):
        if n['role']=='window' and b_ok(n.get('bounds')):
            winb=n['bounds']; break
    offs=[n for n,p in nodes_of(data) if 'offscreen' in (n.get('states') or [])]
    if not offs or not winb:
        continue
    inside=out_win=zero=0
    for n in offs:
        b=n.get('bounds')
        if not b_ok(b): continue
        if b['width']<=0 or b['height']<=0: zero+=1; continue
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        if winb['x']<=cx<=winb['x']+winb['width'] and winb['y']<=cy<=winb['y']+winb['height']:
            inside+=1
        else:
            out_win+=1
    # how many offscreen nodes have ScrollTo?
    st=sum(1 for n in offs if 'ScrollTo' in (n.get('available_actions') or []))
    print('%-16s offscr=%4d insideWin=%4d outsideWin=%4d zerosize=%3d withScrollTo=%4d'%(app,len(offs),inside,out_win,zero,st))

print()
# ---- 4. AX window node bounds vs window-server (windows.json) ----
print('=== AX WINDOW vs WINDOW-SERVER BOUNDS ===')
for app in APPS:
    src,d=tree_of(app)
    wins=load(app,'windows.json') or []
    if not d: continue
    data=d.get('data',d)
    axwins=[n for n,p in nodes_of(data) if n['role']=='window' and b_ok(n.get('bounds'))]
    for aw in axwins[:2]:
        ab=aw['bounds']
        # find best window-server match by min corner distance
        best=None;bd=None
        for w in wins:
            wb=w.get('bounds')
            if not b_ok(wb): continue
            dist=abs(wb['x']-ab['x'])+abs(wb['y']-ab['y'])+abs(wb['width']-ab['width'])+abs(wb['height']-ab['height'])
            if bd is None or dist<bd: bd=dist; best=w
        if best:
            print('%-16s AX=(%g,%g,%g,%g) WS=(%g,%g,%g,%g) L1diff=%g visible=%s'%(app,ab['x'],ab['y'],ab['width'],ab['height'],best['bounds']['x'],best['bounds']['y'],best['bounds']['width'],best['bounds']['height'],bd,best.get('visible')))

print()
# ---- 5. parent-child containment (bounds lies) ----
print('=== CHILD-ESCAPES-PARENT RATE (child with positive size, center outside parent rect; parents with positive size) ===')
for app in APPS:
    src,d=tree_of(app)
    if not d: continue
    tot=esc=0
    esc_roles=collections.Counter()
    for n,p in nodes_of(d.get('data',d)):
        if p is None: continue
        b=n.get('bounds'); pb=p.get('bounds')
        if not(b_ok(b) and b_ok(pb)): continue
        if b['width']<=0 or b['height']<=0 or pb['width']<=0 or pb['height']<=0: continue
        tot+=1
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        if not (pb['x']<=cx<=pb['x']+pb['width'] and pb['y']<=cy<=pb['y']+pb['height']):
            esc+=1; esc_roles[(p['role'],n['role'])]+=1
    if tot:
        print('%-16s pairs=%5d escapes=%4d (%.1f%%) top:%s'%(app,tot,esc,100*esc/tot,esc_roles.most_common(3)))
