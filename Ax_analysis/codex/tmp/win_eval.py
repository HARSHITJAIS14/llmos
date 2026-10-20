import json, os

BASE = "/Users/harshit/Desktop/YC/Ax_analysis"
dirs = [d for d in sorted(os.listdir(BASE)) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,"windows.json"))]
def load(p):
    with open(p) as f: return json.load(f)

GHOST_DIMS = {(2560.0,30.0),(1280.0,29.0),(500.0,500.0),(0.0,0.0),(1.0,1.0),(64.0,64.0)}
def is_strip(b): return b["height"]<=30 and b["width"]>=1000
def ghost(w):
    b=w["bounds"]
    if w.get("visible") or w.get("is_focused"): return False
    if (w.get("title") or "") != w["app_name"]: return False
    return (b["width"],b["height"]) in GHOST_DIMS or is_strip(b)

def close(b1,b2,tol=5):
    return all(abs(b1[k]-b2[k])<=tol for k in ("x","y","width","height"))

stats = dict(n=0, focused_ok=0, focused_present=0, vis_ok=0, vis_present=0,
             largest_ok=0, algo_ok=0, unwinnable=[], thumb_apps=[], ghost_total=0, win_total=0)
rows=[]
for d in dirs:
    wins = load(os.path.join(BASE,d,"windows.json"))
    fp = os.path.join(BASE,d,"full.json")
    if not os.path.exists(fp): continue
    tree = load(fp)["data"]["tree"]
    rb = tree.get("bounds"); rtitle = tree.get("title") or tree.get("name") or ""
    stats["n"]+=1
    stats["win_total"]+=len(wins)
    ghosts=[w for w in wins if ghost(w)]
    stats["ghost_total"]+=len(ghosts)
    real=[w for w in wins if not ghost(w)]
    # false-ghost check: any ghost matching AX root?
    for g in ghosts:
        if close(g["bounds"],rb,5): print(f"!! FALSE GHOST in {d}: {g['bounds']}")
    winnable = any(close(w["bounds"],rb,5) for w in wins)
    if not winnable: stats["unwinnable"].append(d)
    # thumbnail detection: visible, both dims<=200
    thumbs=[w for w in real if w.get("visible") and w["bounds"]["width"]<=200 and w["bounds"]["height"]<=200]
    for t in thumbs:
        tt=(t.get("title") or "")
        title_match = bool(tt) and (rtitle.startswith(tt[:15]) or tt.startswith(rtitle[:15]) or tt[:15] in rtitle)
        stats["thumb_apps"].append((d, tt[:12]+"...", rtitle[:12]+"...", title_match))
    def area(w): return w["bounds"]["width"]*w["bounds"]["height"]
    focused=[w for w in wins if w.get("is_focused")]
    if focused:
        stats["focused_present"]+=1
        if close(focused[0]["bounds"],rb): stats["focused_ok"]+=1
    visible=[w for w in real if w.get("visible")]
    if visible:
        stats["vis_present"]+=1
        pick=max(visible,key=area)
        if close(pick["bounds"],rb): stats["vis_ok"]+=1
    largest = max(real,key=area) if real else None
    if largest and close(largest["bounds"],rb): stats["largest_ok"]+=1
    # combined algorithm: ghosts out; focused > largest visible non-thumb > largest non-thumb > largest
    def algo():
        if focused: return focused[0]
        nonthumb=[w for w in real if not (w["bounds"]["width"]<=200 and w["bounds"]["height"]<=200)]
        visnt=[w for w in nonthumb if w.get("visible")]
        if visnt: return max(visnt,key=area)
        if nonthumb: return max(nonthumb,key=area)
        return max(real,key=area) if real else None
    a=algo()
    ok = a is not None and close(a["bounds"],rb)
    if ok: stats["algo_ok"]+=1
    rows.append((d, len(wins), len(ghosts), bool(focused), ok, winnable))

for r in rows: print(r)
print(json.dumps({k:v for k,v in stats.items()}, indent=1, default=str))
