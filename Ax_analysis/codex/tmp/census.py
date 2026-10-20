import json, os, glob, sys
BASE = '/Users/harshit/Desktop/YC/Ax_analysis'

def load(p):
    try:
        with open(p) as f: return json.load(f)
    except Exception as e:
        return None

def tree_of(doc):
    if not isinstance(doc, dict): return None
    d = doc.get('data') or {}
    return d.get('tree')

def walk(n, depth=0):
    if not isinstance(n, dict): return
    yield n, depth
    for c in (n.get('children') or []):
        yield from walk(c, depth+1)

def stats(doc):
    t = tree_of(doc)
    if t is None:
        return None
    nodes = list(walk(t))
    N = len(nodes)
    s = dict(nodes=N, maxdepth=max(d for _,d in nodes),
             trunc=sum(1 for n,_ in nodes if n.get('subtree_truncated')),
             cc_no_children=sum(1 for n,_ in nodes if n.get('children_count') and not n.get('children')),
             named=sum(1 for n,_ in nodes if n.get('name')),
             valued=sum(1 for n,_ in nodes if n.get('value')),
             bounded=sum(1 for n,_ in nodes if n.get('bounds')),
             withrefs=sum(1 for n,_ in nodes if n.get('ref_id')),
             actionable=sum(1 for n,_ in nodes if n.get('available_actions')),
             offscreen=sum(1 for n,_ in nodes if 'offscreen' in (n.get('states') or [])),
             enabled=sum(1 for n,_ in nodes if 'enabled' in (n.get('states') or [])),
             webarea=sum(1 for n,_ in nodes if 'web' in str(n.get('role','')).lower()),
             )
    roles = {}
    for n,_ in nodes: roles[n.get('role')] = roles.get(n.get('role'),0)+1
    s['roles'] = roles
    s['complete'] = (doc.get('data') or {}).get('complete')
    s['ref_count'] = (doc.get('data') or {}).get('ref_count')
    s['ok'] = doc.get('ok')
    # advertised vs delivered children
    adv = 0; deliv = 0
    for n,_ in nodes:
        cc = n.get('children_count')
        if cc is not None:
            adv += cc; deliv += len(n.get('children') or [])
    s['adv_cc'] = adv; s['deliv_cc'] = deliv
    return s

apps = sorted([d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,'meta.json'))])
out = {}
for a in apps:
    p = os.path.join(BASE,a)
    meta = load(os.path.join(p,'meta.json')) or {}
    rec = dict(app=meta.get('app',a), dir=a,
               was_running=meta.get('was_running'),
               capture_mode=meta.get('capture_mode'),
               hints=(meta.get('framework_signals') or {}).get('hints'),
               frameworks=(meta.get('framework_signals') or {}).get('frameworks'),
               errors=meta.get('errors'),
               captures=meta.get('captures'),
               forced_capture=meta.get('forced_capture'),
               best_window=meta.get('best_window'),
               n_windows=len(load(os.path.join(p,'windows.json')) or []) if os.path.exists(os.path.join(p,'windows.json')) else None,
               )
    w = load(os.path.join(p,'windows.json'))
    if isinstance(w,list):
        rec['win_visible'] = sum(1 for x in w if x.get('visible'))
        rec['win_focused'] = sum(1 for x in w if x.get('is_focused'))
        rec['win_minimized'] = sum(1 for x in w if x.get('minimized'))
    for kind in ['skeleton','full','forced','forced_warm']:
        fp = os.path.join(p, kind+'.json')
        if os.path.exists(fp):
            doc = load(fp)
            rec[kind] = stats(doc) if doc else None
            if doc and not doc.get('ok'):
                rec[kind+'_err'] = doc.get('error') or doc
            if doc and rec.get(kind) is None:
                rec[kind+'_raw'] = doc
    sf = load(os.path.join(p,'surfaces.json'))
    if sf:
        rec['surfaces_ok'] = sf.get('ok')
        rec['surfaces_err'] = None if sf.get('ok') else sf.get('error')
        rec['n_surfaces'] = len(((sf.get('data') or {}).get('surfaces')) or []) if sf.get('ok') else None
    out[a] = rec

json.dump(out, open('/Users/harshit/Desktop/YC/Ax_analysis/codex/tmp/census.json','w'), indent=1)
print('apps:', len(out))
for a,r in out.items():
    f = r.get('full'); s = r.get('skeleton'); fo = r.get('forced')
    print('%-18s mode=%-10s run=%-5s hints=%-22s sk=%-5s full=%-5s forced=%-5s trunc(f)=%-3s'%(
        a, r.get('capture_mode'), r.get('was_running'), str(r.get('hints')),
        s['nodes'] if s else '-', f['nodes'] if f else '-', fo['nodes'] if fo else 'ERR',
        f['trunc'] if f else '-'))
