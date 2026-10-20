import json, os, glob, collections, re

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'
APPS = ['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox',
        'gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs',
        'reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']

def load(app, name):
    p = os.path.join(BASE, app, name)
    if not os.path.exists(p): return None
    try:
        return json.load(open(p))
    except Exception as e:
        return {'_parse_error': str(e)}

def tree_of(doc):
    if not doc: return None
    if isinstance(doc, list):
        return {'role': '_synthetic_root', 'children': [x for x in doc if isinstance(x, dict)]}
    d = doc.get('data') or {}
    if isinstance(d, list):
        return {'role': '_synthetic_root', 'children': [x for x in d if isinstance(x, dict)]}
    t = d.get('tree')
    if t is None and d.get('trees'):
        return {'role': '_synthetic_root', 'children': d['trees']}
    return t

def walk(node, depth=0):
    if not isinstance(node, dict): return
    yield node, depth
    for c in node.get('children') or []:
        yield from walk(c, depth+1)

def stats(tree):
    if not tree: return None
    roles = collections.Counter()
    acts = collections.Counter()
    nid_kinds = collections.Counter()
    nid_vals = collections.Counter()
    states = collections.Counter()
    n = 0; maxd = 0; trunc = 0; leaves=0
    named = 0
    for node, d in walk(tree):
        n += 1; maxd = max(maxd, d)
        roles[node.get('role')] += 1
        for a in node.get('available_actions') or []: acts[a]+=1
        for s in node.get('states') or []: states[s]+=1
        nid = node.get('native_id')
        if isinstance(nid, dict):
            nid_kinds[nid.get('kind')] += 1
            nid_vals[nid.get('value')] += 1
        if node.get('subtree_truncated'): trunc += 1
        if not (node.get('children') or []): leaves += 1
        if node.get('name'): named += 1
    return dict(n=n, maxd=maxd, roles=roles, acts=acts, nid_kinds=nid_kinds,
                nid_vals=nid_vals, states=states, trunc=trunc, leaves=leaves, named=named)

FEATS = {}
for app in APPS:
    meta = load(app, 'meta.json')
    rec = {'app': app,
           'bundle': meta.get('bundle_id'),
           'hints': meta.get('framework_signals',{}).get('hints',[]),
           'fw': meta.get('framework_signals',{}).get('frameworks',[]),
           'exe': meta.get('framework_signals',{}).get('exe',''),
           'capture_mode': meta.get('capture_mode')}
    for fname in ['skeleton.json','full.json','forced.json','surfaces.json','windows.json']:
        doc = load(app, fname)
        key = fname.split('.')[0]
        rec[key+'_doc'] = doc
        rec[key] = stats(tree_of(doc))
    FEATS[app] = rec

if __name__ == '__main__':
    for app in APPS:
        r = FEATS[app]
        for k in ['skeleton','full','forced']:
            s = r[k]
            print(f"{app:20s} {k:9s} n={s['n'] if s else 'NA':>5} d={s['maxd'] if s else '-':>3} "
                  f"trunc={s['trunc'] if s else '-':>3} nidkinds={dict(s['nid_kinds']) if s else '-'}")
        print()
