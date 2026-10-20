import json, os
from collections import Counter

BASE = "/Users/harshit/Desktop/YC/Ax_analysis"
dirs = [d for d in sorted(os.listdir(BASE)) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,"windows.json"))]

def load(p):
    with open(p) as f: return json.load(f)

def bkey(b): return (b["x"],b["y"],b["width"],b["height"]) if b else None

# collect AXWindow-role nodes from full.json
def find_windows(node, out, depth=0):
    if not isinstance(node, dict): return
    r = node.get("role","")
    if r in ("AXWindow","window","Window") or "window" in r.lower():
        out.append(node)
    for c in node.get("children",[]) or []:
        find_windows(c, out, depth+1)

print("app | WS-real-window(s) | AX root bounds | AX window nodes (role,title,bounds)")
for d in dirs:
    wins = load(os.path.join(BASE,d,"windows.json"))
    fp = os.path.join(BASE,d,"full.json")
    if not os.path.exists(fp): 
        print(f"{d}: NO full.json"); continue
    data = load(fp).get("data",{})
    tree = data.get("tree",{})
    rb = tree.get("bounds")
    axw=[]; find_windows(tree,axw)
    # dedupe ax windows by bounds
    seen=set(); axu=[]
    for n in axw:
        k=bkey(n.get("bounds"))
        if k in seen: continue
        seen.add(k); axu.append(n)
    print(f"\n{d}: AXroot={bkey(rb)} rootrole={tree.get('role')} n_axwin={len(axw)}")
    for n in axu[:6]:
        print(f"   AXwin: role={n.get('role')} title={repr((n.get('title') or n.get('name') or '')[:30])} b={bkey(n.get('bounds'))}")
    # WS windows that are not obvious ghosts
    for w in wins:
        b=w["bounds"]
        wd,ht=b["width"],b["height"]
        ghost = (wd,ht) in [(2560,30),(1280,29),(500,500),(0,0),(1,1),(64,64)]
        if not ghost:
            print(f"   WSwin: {wd}x{ht} at ({b['x']},{b['y']}) vis={w.get('visible')} foc={w.get('is_focused')} title_eq_app={(w.get('title') or '')==w['app_name']}")
