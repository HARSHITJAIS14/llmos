import json, os
BASE='/Users/harshit/Desktop/YC/Ax_analysis'
def walk(n,d=0,parent=None):
    if not isinstance(n,dict): return
    yield n,d,parent
    for c in (n.get('children') or []): yield from walk(c,d+1,n)

def analyze(path):
    doc=json.load(open(path))
    t=(doc.get('data') or {}).get('tree')
    if t is None: return None
    nodes=list(walk(t))
    md=max(d for _,d,_ in nodes)
    stubs=[(n,d) for n,d,_ in nodes if n.get('children_count') and not n.get('children')]
    cap_stubs=[x for x in stubs if x[1]==md]
    lazy_stubs=[x for x in stubs if x[1]<md]
    trunc=[(n,d) for n,d,_ in nodes if n.get('subtree_truncated')]
    leaves=[(n,d) for n,d,_ in nodes if not n.get('children')]
    interactive=[n for n,_,_ in nodes if n.get('available_actions') and set(n['available_actions'])-{'SetFocus'}]
    return dict(
      path=path, N=len(nodes), maxdepth=md,
      stubs=len(stubs), cap_stubs=len(cap_stubs), lazy_stubs=len(lazy_stubs),
      lazy_detail=[(n.get('role'),n.get('children_count'),d,bool(n.get('name'))) for n,d in lazy_stubs][:12],
      trunc=len(trunc), trunc_detail=[(n.get('role'),n.get('children_count'),d) for n,d in trunc][:8],
      leaves=len(leaves),
      named=sum(1 for n,_,_ in nodes if n.get('name')),
      interactive=len(interactive),
      named_interactive=sum(1 for n in interactive if n.get('name')),
      offscreen=sum(1 for n,_,_ in nodes if 'offscreen' in (n.get('states') or [])),
      valued=sum(1 for n,_,_ in nodes if n.get('value')),
      adv=sum(n.get('children_count',0) or 0 for n,_,_ in nodes),
      web=sum(1 for n,_,_ in nodes if 'web' in str(n.get('role','')).lower()),
      complete=(doc.get('data') or {}).get('complete'),
    )

apps=sorted(d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,'meta.json')))
res={}
for a in apps:
    res[a]={}
    for k in ['skeleton','full','forced','forced_warm']:
        p=os.path.join(BASE,a,k+'.json')
        if os.path.exists(p):
            try: r=analyze(p)
            except Exception as e: r={'err':str(e)}
            if r: res[a][k]=r
json.dump(res,open(BASE+'/codex/tmp/husk.json','w'),indent=1)

print('%-18s %-8s %5s %3s %5s %5s %5s %6s %6s %6s %6s'%('app','cap','N','md','lazy','cap_s','trunc','named','inter','n_int','offscr'))
for a in apps:
    for k in ['full','forced']:
        r=res[a].get(k)
        if not r: continue
        print('%-18s %-8s %5d %3d %5d %5d %5d %6d %6d %6d %6d'%(a,k,r['N'],r['maxdepth'],r['lazy_stubs'],r['cap_stubs'],r['trunc'],r['named'],r['interactive'],r['named_interactive'],r['offscreen']))
