#!/usr/bin/env python3
import json, os, collections

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox','gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs','reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']
CLICKY={'Click','Press','Toggle','Select'}
# display model to verify
D1=(0,0,2560,1440); D2=(2560,536,1280,832)

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
    # music/forced.json is a mis-capture of YT Music -> use full.json for music
    if app=='music':
        return 'full.json', load(app,'full.json')
    src='forced.json'; d=load(app,src)
    if d is None or not d.get('ok',True): src='full.json'; d=load(app,src)
    return src,d

def in_disp(cx,cy):
    for (dx,dy,dw,dh) in (D1,D2):
        if dx<=cx<=dx+dw and dy<=cy<=dy+dh: return True
    return False

# ---- A. display model verification against ALL window-server windows ----
viol=0; tot=0; vapps=collections.Counter()
for app in APPS:
    for w in load(app,'windows.json') or []:
        b=w.get('bounds')
        if not b_ok(b): continue
        tot+=1
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        if not in_disp(cx,cy):
            viol+=1; vapps[app]+=1
print('A. window-server windows with center outside D1(0,0,2560,1440)+D2(2560,536,1280,832):',viol,'of',tot,dict(vapps))
# also strict: fully contained?
part=0
for app in APPS:
    for w in load(app,'windows.json') or []:
        b=w.get('bounds')
        if not b_ok(b): continue
        ok=False
        for (dx,dy,dw,dh) in (D1,D2):
            if b['x']>=dx-1 and b['y']>=dy-1 and b['x']+b['width']<=dx+dw+1 and b['y']+b['height']<=dy+dh+1: ok=True
        if not ok: part+=1
print('   windows not fully inside a single display (spanning or overhanging):',part,'of',tot)
print()

# ---- B. triplet zero-size button parents in finder ----
print('B. parent chain of unnamed zero-size buttons (finder):')
src,d=tree_of('finder')
def walk(n, path):
    if 'role' in n:
        b=n.get('bounds')
        if b_ok(b) and (b['width']<=0 or b['height']<=0) and n['role']=='button' and not n.get('name'):
            print('   path:', ' > '.join(path[-5:]))
        for c in n.get('children') or []:
            walk(c, path+[n['role']+(':'+n['name'][:15] if n.get('name') else '')])
data=d['data']['tree'] if 'tree' in d.get('data',{}) else d['data']
walk(data, [])
print()

# ---- C. reminders 2px ----
print('C. reminders AX vs WS same-size rows:')
src,d=tree_of('reminders')
axw=[n for n,p in nodes_of(d['data']) if n['role']=='window'][0]['bounds']
for w in load('reminders','windows.json'):
    b=w['bounds']
    if b['width']==axw['width'] and b['height']==axw['height']:
        print('   AX',axw,' WS',b,' visible',w.get('visible'), 'title-ish len', len(w.get('title') or ''))
print()

# ---- D. click-safety partition of clickable interactives ----
print('D. CLICK-SAFETY PARTITION (clickable = has Click/Press/Toggle/Select)')
print('%-16s %6s | %7s %7s %7s %8s | out_w/ScrollTo  off_flag_FN'%('app','click','safe','sliver','zero','outWin'))
agg=collections.Counter()
for app in APPS:
    if app=='yt_music': pass
    src,d=tree_of(app)
    if not d or 'data' not in d: continue
    data=d['data']
    wins=[n for n,p in nodes_of(data) if n['role']=='window' and b_ok(n.get('bounds'))]
    if not wins:
        print('%-16s no window node'%app); continue
    wb=wins[0]['bounds']
    def inwin(cx,cy): return wb['x']<=cx<=wb['x']+wb['width'] and wb['y']<=cy<=wb['y']+wb['height']
    clk=[n for n,p in nodes_of(data) if set(n.get('available_actions') or [])&CLICKY]
    safe=sliver=zero=outw=0; outw_st=0; fn=0
    for n in clk:
        b=n.get('bounds')
        if not b_ok(b): continue
        if b['width']<=0 or b['height']<=0:
            zero+=1; continue
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        if not inwin(cx,cy):
            outw+=1
            if 'ScrollTo' in (n.get('available_actions') or []): outw_st+=1
            if 'offscreen' not in (n.get('states') or []): fn+=1
            continue
        if min(b['width'],b['height'])<=3: sliver+=1
        else: safe+=1
    n_=len(clk)
    print('%-16s %6d | %7d %7d %7d %8d | %d/%d           %d'%(app,n_,safe,sliver,zero,outw,outw_st,outw,fn))
print()

# ---- E. offscreen flag false negatives across ALL positive-area nodes ----
print('E. positive-area nodes, center OUTSIDE AX-window rect: offscreen-flag coverage')
for app in APPS:
    src,d=tree_of(app)
    if not d or 'data' not in d: continue
    data=d['data']
    wins=[n for n,p in nodes_of(data) if n['role']=='window' and b_ok(n.get('bounds'))]
    if not wins: continue
    wb=wins[0]['bounds']
    outside=flagged=0
    roles_fn=collections.Counter()
    for n,p in nodes_of(data):
        b=n.get('bounds')
        if not b_ok(b) or b['width']<=0 or b['height']<=0: continue
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        if wb['x']<=cx<=wb['x']+wb['width'] and wb['y']<=cy<=wb['y']+wb['height']: continue
        outside+=1
        if 'offscreen' in (n.get('states') or []): flagged+=1
        else: roles_fn[n['role']]+=1
    if outside:
        print('%-16s outside=%4d flagged=%4d unflagged=%4d %s'%(app,outside,flagged,outside-flagged,roles_fn.most_common(4)))
print()

# ---- F. calendar grid escape geometry (why 26%) ----
print('F. calendar grid>button escapes: distances')
src,d=tree_of('calendar')
data=d['data']
dists=[]
for n,p in nodes_of(data):
    if p and p.get('role')=='grid' and n['role']=='button':
        b=n.get('bounds'); pb=p.get('bounds')
        if not (b_ok(b) and b_ok(pb)) or b['width']<=0: continue
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        dx=max(pb['x']-cx, cx-(pb['x']+pb['width']),0); dy=max(pb['y']-cy, cy-(pb['y']+pb['height']),0)
        if dx or dy: dists.append((dx,dy))
print('   escapes:',len(dists),'dx range',min(x for x,y in dists) if dists else '-',max(x for x,y in dists) if dists else '-','dy range',min(y for x,y in dists) if dists else '-',max(y for x,y in dists) if dists else '-')
# grid bounds vs window
grids=[n for n,p in nodes_of(data) if n['role']=='grid']
print('   grid bounds:', [g['bounds'] for g in grids][:3])
print()

# ---- G. VLC sliver detail ----
print('G. VLC 2px buttons:')
src,d=tree_of('vlc')
for n,p in nodes_of(d['data']):
    b=n.get('bounds')
    if b_ok(b) and 0<min(b['width'],b['height'])<=3 and n['role']=='button':
        print('   ',b,'actions',n.get('available_actions'),'name?',bool(n.get('name')),'parent',p['role'] if p else None)
