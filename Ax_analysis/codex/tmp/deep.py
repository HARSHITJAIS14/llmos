#!/usr/bin/env python3
import json, os, re, collections

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'
APPS = ['antigravity_ide','brave_browser','calendar','claude','discord','finder',
        'firefox','gemini','google_chrome','keynote','microsoft_word','music',
        'notes','notion','obs','reminders','safari','telegram','textedit','utm',
        'vlc','whatsapp','yt_music','zoom_us']

def load(app, fname):
    p = os.path.join(BASE, app, fname)
    if not os.path.exists(p): return None
    try: d = json.load(open(p))
    except Exception: return None
    if isinstance(d, dict) and d.get('ok') and 'tree' in d.get('data', {}):
        return d['data']
    return None

def best(app):
    # music/forced.json is contaminated (captured YT Music) -> use full
    if app == 'music': return 'full.json', load(app, 'full.json')
    for f in ['forced_warm.json','forced.json','full.json','skeleton.json']:
        d = load(app, f)
        if d: return f, d
    return None, None

def walk(n, depth=0, inweb=False):
    yield n, depth, inweb
    w = inweb or n.get('role') == 'webarea'
    for c in n.get('children', []):
        yield from walk(c, depth+1, w)

def nid_val(n):
    nid = n.get('native_id')
    if isinstance(nid, dict):
        return nid.get('kind'), str(nid.get('value',''))
    if nid is None: return None, None
    return 'raw', str(nid)

rows = {}
for app in APPS:
    src, data = best(app)
    tree = data['tree']
    f = collections.Counter()
    actions_shell = collections.Counter(); actions_web = collections.Counter()
    roles = collections.Counter()
    dom_vals = []; ax_vals = []
    web_depths = []
    n = 0; maxd = 0
    values_seen = 0
    for node, d, inweb in walk(tree):
        n += 1; maxd = max(maxd, d)
        r = node.get('role'); roles[r] += 1
        if r == 'webarea': web_depths.append(d)
        k, v = nid_val(node)
        if k == 'ax_dom_identifier':
            f['dom_id'] += 1; dom_vals.append((v, inweb or r=='webarea'))
        elif k == 'ax_identifier':
            f['ax_id'] += 1; ax_vals.append(v)
        acts = node.get('available_actions', [])
        tgt = actions_web if inweb else actions_shell
        for a in acts: tgt[a] += 1
        if 'value' in node: values_seen += 1
    # patterns
    view_n = sum(1 for v,_ in dom_vals if re.fullmatch(r'view_\d+', v))
    dom_outside_web = sum(1 for v,iw in dom_vals if not iw)
    uuid_ax = sum(1 for v in ax_vals if re.fullmatch(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}', v))
    ns_ax = sum(1 for v in ax_vals if v.startswith('_NS:'))
    dotted_ax = sum(1 for v in ax_vals if re.fullmatch(r'\w+(\.\w+){2,}', v) and not re.search(r'(circle|fill|square)', v))
    sfsym_ax = sum(1 for v in ax_vals if re.fullmatch(r'[a-z0-9]+(\.[a-z0-9]+)+', v))
    rows[app] = dict(src=src, n=n, maxd=maxd, roles=dict(roles),
        web_depths=web_depths, dom_id=f['dom_id'], ax_id=f['ax_id'],
        view_n=view_n, dom_outside_web=dom_outside_web, uuid_ax=uuid_ax,
        ns_ax=ns_ax, dotted_ax=dotted_ax, sfsym_ax=sfsym_ax,
        actions_shell=dict(actions_shell), actions_web=dict(actions_web),
        unknown_role=roles.get('unknown',0), values=values_seen)
    # husk metric: skeleton vs forced sizes
    sk = load(app,'skeleton.json'); fu = load(app,'full.json')
    def count(d):
        return sum(1 for _ in walk(d['tree'])) if d else None
    rows[app]['n_skeleton'] = count(sk); rows[app]['n_full'] = count(fu)

json.dump(rows, open(BASE+'/codex/tmp/deep.json','w'), indent=1)
hdr = f"{'app':17s} {'src':13s} {'n':>5s} {'webd':>5s} {'dom':>4s} {'out':>4s} {'view#':>5s} {'axid':>4s} {'NS':>4s} {'uuid':>4s} {'dot':>3s} {'sf':>3s} {'unk':>3s} {'nSk':>5s} {'nFull':>5s}"
print(hdr)
for a, r in rows.items():
    wd = str(r['web_depths'][:2]) if r['web_depths'] else '-'
    print(f"{a:17s} {r['src'][:12]:13s} {r['n']:5d} {wd:>5s} {r['dom_id']:4d} {r['dom_outside_web']:4d} {r['view_n']:5d} {r['ax_id']:4d} {r['ns_ax']:4d} {r['uuid_ax']:4d} {r['dotted_ax']:3d} {r['sfsym_ax']:3d} {r['unknown_role']:3d} {str(r['n_skeleton']):>5s} {str(r['n_full']):>5s}")
print()
print('ACTION VOCAB (shell // web):')
for a, r in rows.items():
    print(f"{a:17s} shell={sorted(r['actions_shell'])} web={sorted(r['actions_web'])}")
