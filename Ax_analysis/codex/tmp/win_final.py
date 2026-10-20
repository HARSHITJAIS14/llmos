import json, os
BASE="/Users/harshit/Desktop/YC/Ax_analysis"
dirs=[d for d in sorted(os.listdir(BASE)) if os.path.isdir(os.path.join(BASE,d)) and os.path.exists(os.path.join(BASE,d,"windows.json")) and os.path.exists(os.path.join(BASE,d,"full.json"))]
def load(p):
    with open(p) as f: return json.load(f)
exact=0; tol5=0
strip_counts={}
vis_breakdown={"real_full":0,"thumb":0,"other":0}
for d in dirs:
    wins=load(os.path.join(BASE,d,"windows.json"))
    rb=load(os.path.join(BASE,d,"full.json"))["data"]["tree"]["bounds"]
    m0=any(all(w["bounds"][k]==rb[k] for k in rb) for w in wins)
    m5=any(all(abs(w["bounds"][k]-rb[k])<=5 for k in rb) for w in wins)
    exact+=m0; tol5+=m5
    if m5 and not m0: print(f"{d}: tol5 but not exact")
    s1=sum(1 for w in wins if w["bounds"]["width"]==2560 and w["bounds"]["height"]==30)
    s2=sum(1 for w in wins if w["bounds"]["width"]==1280 and w["bounds"]["height"]==29)
    if s1 or s2: strip_counts[d]=(s1,s2)
    for w in wins:
        if w.get("visible"):
            b=w["bounds"]
            if b["width"]<=200 and b["height"]<=200: vis_breakdown["thumb"]+=1
            elif all(abs(b[k]-rb[k])<=5 for k in rb): vis_breakdown["real_full"]+=1
            else: vis_breakdown["other"]+=1; print(f"visible-other in {d}: {b}")
print(f"apps with exact WS==AXroot match: {exact}/{len(dirs)}; tol5: {tol5}")
print("strip counts per app (2560x30, 1280x29):", strip_counts)
print("visible=True breakdown:", vis_breakdown)
# focused windows: ever a ghost or thumb?
for d in dirs:
    for w in load(os.path.join(BASE,d,"windows.json")):
        if w.get("is_focused"):
            b=w["bounds"]
            print(f"focused {d}: {b['width']}x{b['height']} vis={w.get('visible')}")
# x-coordinate range / negative / display2
xs=[]
for d in dirs:
    for w in load(os.path.join(BASE,d,"windows.json")):
        xs.append(w["bounds"]["x"])
print("x range:", min(xs), max(xs), "negative-x windows:", sum(1 for x in xs if x<0))
