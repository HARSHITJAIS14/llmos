import json, os, glob
from collections import Counter, defaultdict

BASE = "/Users/harshit/Desktop/YC/Ax_analysis"
dirs = [d for d in sorted(os.listdir(BASE)) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,"windows.json"))]

all_wins = {}
for d in dirs:
    with open(os.path.join(BASE,d,"windows.json")) as f:
        all_wins[d] = json.load(f)

print("=== per-app window counts & shapes ===")
dim_counter = Counter()
for d, wins in all_wins.items():
    shapes = Counter()
    for w in wins:
        b = w["bounds"]
        key = (b["width"], b["height"])
        shapes[key]+=1
        dim_counter[key]+=1
    foc = sum(1 for w in wins if w.get("is_focused"))
    vis = sum(1 for w in wins if w.get("visible"))
    title_eq = sum(1 for w in wins if (w.get("title") or "")==w.get("app_name"))
    empty_title = sum(1 for w in wins if not (w.get("title") or "").strip())
    print(f"{d}: n={len(wins)} focused={foc} visible={vis} title==appname={title_eq} emptytitle={empty_title}")
    for (wd,ht),c in sorted(shapes.items(), key=lambda x:-x[1]):
        print(f"    {wd}x{ht} x{c}")

print("\n=== global dimension clusters ===")
for (wd,ht),c in dim_counter.most_common(30):
    print(f"{wd}x{ht}: {c}")
