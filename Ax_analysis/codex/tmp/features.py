#!/usr/bin/env python3
"""Extract tree-only features per app for framework fingerprinting."""
import json, os, re, collections

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'
APPS = ['antigravity_ide','brave_browser','calendar','claude','discord','finder',
        'firefox','gemini','google_chrome','keynote','microsoft_word','music',
        'notes','notion','obs','reminders','safari','telegram','textedit','utm',
        'vlc','whatsapp','yt_music','zoom_us']

def load_tree(app):
    # prefer forced (deepest), then full, then skeleton
    order = ['forced_warm.json','forced.json','full.json','skeleton.json']
    for f in order:
        p = os.path.join(BASE, app, f)
        if os.path.exists(p):
            try:
                d = json.load(open(p))
            except Exception:
                continue
            if isinstance(d, dict) and d.get('ok') and 'data' in d and 'tree' in d['data']:
                return f, d['data']['tree'], d['data']
    return None, None, None

def walk(n, depth=0):
    yield n, depth
    for c in n.get('children', []):
        yield from walk(c, depth+1)

def features(app):
    src, tree, data = load_tree(app)
    if tree is None:
        return None
    roles = collections.Counter()
    native_kinds = collections.Counter()
    actions = collections.Counter()
    n_nodes = 0
    max_depth = 0
    webareas = []          # (depth, n_descendants)
    ax_dom = 0             # native_id containing ax_dom / dom identifier style
    native_samples = collections.Counter()
    truncated = 0
    group_runs = 0         # count of group whose only child is group (wrapper chains)
    groups_with_single_group_child = 0
    named_groups = 0
    states_seen = collections.Counter()
    for n, d in walk(tree):
        n_nodes += 1
        max_depth = max(max_depth, d)
        r = n.get('role')
        roles[r] += 1
        if n.get('subtree_truncated'):
            truncated += 1
        for a in n.get('available_actions', []):
            actions[a] += 1
        for s in n.get('states', []):
            states_seen[s] += 1
        nid = n.get('native_id')
        if nid is not None:
            nid = str(nid)
            native_samples[nid[:40]] += 0  # keep memory low
            if re.fullmatch(r'\d+', nid):
                native_kinds['int'] += 1
            elif re.match(r'^[0-9a-fA-F-]{8,}$', nid):
                native_kinds['uuid'] += 1
            else:
                native_kinds['other'] += 1
                native_samples[nid[:60]] += 1
        if r == 'webarea':
            nd = sum(1 for _ in walk(n)) - 1
            webareas.append((d, nd))
        if r == 'group':
            if n.get('name'):
                named_groups += 1
            ch = n.get('children', [])
            if len(ch) == 1 and ch[0].get('role') == 'group':
                groups_with_single_group_child += 1
    return {
        'app': app, 'src': src, 'n_nodes': n_nodes, 'max_depth': max_depth,
        'complete': data.get('complete'), 'roles': dict(roles),
        'actions': dict(actions), 'native_kinds': dict(native_kinds),
        'native_samples': {k: v for k, v in native_samples.most_common(8) if v},
        'webareas': webareas, 'truncated_nodes': truncated,
        'group_chain': groups_with_single_group_child, 'named_groups': named_groups,
        'states': dict(states_seen),
    }

if __name__ == '__main__':
    out = {}
    for a in APPS:
        f = features(a)
        out[a] = f
    json.dump(out, open(os.path.join(BASE, 'codex/tmp/feat.json'), 'w'), indent=1)
    # compact table
    for a, f in out.items():
        if not f:
            print(f'{a}: NO TREE')
            continue
        wa = len(f['webareas'])
        top_roles = sorted(f['roles'].items(), key=lambda x: -x[1])[:6]
        print(f"{a:18s} src={f['src']:16s} n={f['n_nodes']:6d} depth={f['max_depth']:2d} webareas={wa} nid={f['native_kinds']} roles={top_roles}")
