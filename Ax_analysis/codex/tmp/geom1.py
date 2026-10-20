#!/usr/bin/env python3
import json, os, collections, math

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox','gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs','reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']

INTERACT={'Click','Press','Toggle','Select','SetValue','Expand','Collapse','SetFocus','RightClick'}
CLICKY={'Click','Press','Toggle','Select'}

def nodes_of(x, parent=None):
    """yield (node,parent) for dict nodes with role"""
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

def load(app, name):
    p=os.path.join(BASE,app,name)
    if not os.path.exists(p): return None
    try:
        return json.load(open(p))
    except Exception:
        return None

def b_ok(b):
    return isinstance(b,dict) and all(k in b for k in ('x','y','width','height'))

# ---- displays inferred from all windows.json ----
all_wins=[]
for app in APPS:
    w=load(app,'windows.json')
    if isinstance(w,list):
        for win in w:
            win['_app']=app
            all_wins.append(win)
print('=== WINDOW SERVER GEOMETRY ===')
print('total windows:', len(all_wins))
xs=[w['bounds']['x'] for w in all_wins if b_ok(w.get('bounds'))]
ys=[w['bounds']['y'] for w in all_wins if b_ok(w.get('bounds'))]
rights=[w['bounds']['x']+w['bounds']['width'] for w in all_wins if b_ok(w.get('bounds'))]
bots=[w['bounds']['y']+w['bounds']['height'] for w in all_wins if b_ok(w.get('bounds'))]
print('window x range: [%s, %s], y range: [%s, %s], max right %s, max bottom %s' % (min(xs),max(xs),min(ys),max(ys),max(rights),max(bots)))
neg=[w for w in all_wins if b_ok(w.get('bounds')) and (w['bounds']['x']<0 or w['bounds']['y']<0)]
print('windows with negative origin:', len(neg), collections.Counter(w['_app'] for w in neg))
for w in neg[:8]:
    print('  ', w['_app'], w['bounds'], 'visible=',w.get('visible'))
# cluster window x origins to guess display arrangement
print('x-origin histogram (rounded to 100):', collections.Counter(int(x//100)*100 for x in xs).most_common(12))
print('windows fully beyond x=2560:', sum(1 for w in all_wins if b_ok(w.get('bounds')) and w['bounds']['x']>=2560))
vis=[w for w in all_wins if w.get('visible')]
print('visible windows:', len(vis), 'of', len(all_wins))
print()

# ---- per-app node geometry from forced.json (fallback full.json) ----
print('=== PER-APP NODE GEOMETRY (forced.json, fallback full.json) ===')
hdr=('app','src','nodes','w/bounds','inter','inter_nb','zerosz','sliver','neg','offscr','off_in','on_out')
print(('%-16s %-7s %6s %8s %6s %8s %7s %7s %5s %7s %6s %6s')%hdr)
rows={}
# main display guess: union of two displays: D1 = (0,0,2560,1440?) D2=(2560, ?, 1280, ?)
# infer display extents from window maxima
DISPLAYS=[(0,0,2560,1600),(2560,0,1280+2560,1600)]  # provisional; refine below

per_app={}
for app in APPS:
    src='forced.json'
    d=load(app,src)
    if d is None or not d.get('ok', True):
        src='full.json'; d=load(app,src)
    if d is None:
        print('%-16s MISSING'%app); continue
    ns=list(nodes_of(d.get('data',d)))
    total=len(ns)
    wb=sum(1 for n,_ in ns if b_ok(n.get('bounds')))
    inter=[(n,p) for n,p in ns if set(n.get('available_actions') or [])&CLICKY]
    inter_nb=sum(1 for n,_ in inter if not b_ok(n.get('bounds')))
    def dims(n):
        b=n['bounds']; return b['width'],b['height'],b['x'],b['y']
    zerosz=[n for n,_ in inter if b_ok(n.get('bounds')) and (n['bounds']['width']<=0 or n['bounds']['height']<=0)]
    sliver=[n for n,_ in inter if b_ok(n.get('bounds')) and 0<min(n['bounds']['width'],n['bounds']['height'])<=3]
    negc=[n for n,_ in ns if b_ok(n.get('bounds')) and (n['bounds']['x']<0 or n['bounds']['y']<0)]
    offscr=[n for n,_ in ns if 'offscreen' in (n.get('states') or [])]
    # offscreen-marked but bounds look onscreen (inside union of displays and positive size)
    def onscreen(b):
        if b['width']<=0 or b['height']<=0: return False
        cx=b['x']+b['width']/2; cy=b['y']+b['height']/2
        return (0<=cx<=3840) and (0<=cy<=1600)
    off_in=[n for n in offscr if b_ok(n.get('bounds')) and onscreen(n['bounds'])]
    on_out=[n for n,_ in ns if 'offscreen' not in (n.get('states') or []) and b_ok(n.get('bounds')) and n['bounds']['width']>0 and not onscreen(n['bounds'])]
    print('%-16s %-7s %6d %8d %6d %8d %7d %7d %5d %7d %6d %6d'%(app,src.split(".")[0],total,wb,len(inter),inter_nb,len(zerosz),len(sliver),len(negc),len(offscr),len(off_in),len(on_out)))
    per_app[app]=dict(src=src,total=total,wb=wb,inter=inter,zerosz=zerosz,sliver=sliver,negc=negc,offscr=offscr,off_in=off_in,on_out=on_out,ns=ns,data=d)

json_out={}
print()
print('=== ZERO-SIZE / SLIVER INTERACTIVE EXAMPLES (roles only) ===')
for app,info in per_app.items():
    if info['zerosz'] or info['sliver']:
        zr=collections.Counter(n['role'] for n in info['zerosz'])
        sr=collections.Counter((n['role'], n['bounds']['width'], n['bounds']['height']) for n in info['sliver'])
        print(app, 'zero:',dict(zr), 'sliver:', list(sr.items())[:6])
