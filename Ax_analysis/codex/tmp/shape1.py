import json, os, collections, statistics

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'
apps = [d for d in sorted(os.listdir(BASE)) if os.path.isfile(os.path.join(BASE, d, 'meta.json'))]

def load_tree(app, fname):
    p = os.path.join(BASE, app, fname)
    if not os.path.isfile(p):
        return None
    try:
        d = json.load(open(p))
    except Exception:
        return None
    dd = d.get('data') if isinstance(d, dict) else None
    if isinstance(dd, dict):
        return dd.get('tree'), dd
    return None

def walk(node, depth=0):
    yield node, depth
    for c in node.get('children', []) or []:
        yield from walk(c, depth + 1)

role_census = collections.Counter()
for app in apps:
    for fname in ('forced.json', 'full.json'):
        r = load_tree(app, fname)
        if r and r[0]:
            tree, dd = r
            for n, dep in walk(tree):
                role_census[n.get('role', '?')] += 1
            break

for role, ct in role_census.most_common(60):
    print(role, ct)
