import json, os
from collections import Counter

BASE = "/Users/harshit/Desktop/YC/Ax_analysis"
dirs = [d for d in sorted(os.listdir(BASE)) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,"windows.json"))]

def load(p):
    with open(p) as f: return json.load(f)

print("=== ghost cluster properties (all apps pooled) ===")
clusters = {}
for d in dirs:
    for w in load(os.path.join(BASE,d,"windows.json")):
        b=w["bounds"]
        key=(b["width"],b["height"])
        clusters.setdefault(key,[]).append((d,w))

for key in [(2560.0,30.0),(1280.0,29.0),(500.0,500.0),(0.0,0.0),(1.0,1.0),(64.0,64.0)]:
    ws = clusters.get(key,[])
    xs = Counter((w["bounds"]["x"],w["bounds"]["y"]) for _,w in ws)
    vis = sum(1 for _,w in ws if w.get("visible"))
    foc = sum(1 for _,w in ws if w.get("is_focused"))
    teq = sum(1 for _,w in ws if (w.get("title") or "")==w["app_name"])
    print(f"{key}: n={len(ws)} visible={vis} focused={foc} title==app={teq} positions={dict(xs.most_common(6))}")

# small thumbnails
print("\nsmall odd windows (both dims < 200, not 0/1/64):")
for key,ws in sorted(clusters.items()):
    w_,h_=key
    if 1<w_<200 and 1<h_<200 and key!=(64.0,64.0):
        for d,w in ws:
            b=w["bounds"]
            print(f"  {d}: {w_}x{h_} at ({b['x']},{b['y']}) vis={w.get('visible')} foc={w.get('is_focused')} title={'<==app>' if (w.get('title') or '')==w['app_name'] else repr((w.get('title') or '')[:20])}")

print("\n=== per-app: candidate real window vs AX root bounds (full.json) ===")
def root_bounds(fp):
    try:
        t=load(fp)
    except Exception as e:
        return None
    # tree may be dict or list
    node = t
    if isinstance(t, dict) and "tree" in t: node=t["tree"]
    if isinstance(node, list):
        node = node[0] if node else None
    if not isinstance(node, dict): return None
    return node.get("bounds"), node.get("role"), len(node.get("children",[]) or [])

for d in dirs:
    wins = load(os.path.join(BASE,d,"windows.json"))
    fp = os.path.join(BASE,d,"full.json")
    rb = root_bounds(fp) if os.path.exists(fp) else None
    # heuristics
    focused = [w for w in wins if w.get("is_focused")]
    visible = [w for w in wins if w.get("visible")]
    def area(w): return w["bounds"]["width"]*w["bounds"]["height"]
    largest = max(wins,key=area) if wins else None
    print(f"\n{d}: root={rb}")
    if focused: b=focused[0]["bounds"]; print(f"  focused: {b['width']}x{b['height']} at ({b['x']},{b['y']}) title_eq={(focused[0].get('title') or '')==focused[0]['app_name']}")
    for w in visible:
        b=w["bounds"]; print(f"  visible: {b['width']}x{b['height']} at ({b['x']},{b['y']})")
    if largest: b=largest["bounds"]; print(f"  largest: {b['width']}x{b['height']} at ({b['x']},{b['y']}) vis={largest.get('visible')}")
