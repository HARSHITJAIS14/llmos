import json, os
from collections import Counter, defaultdict

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
FW = {
 'antigravity_ide':'electron','claude':'electron','discord':'electron','notion':'electron',
 'brave_browser':'chromium-browser','google_chrome':'chromium-browser',
 'firefox':'gecko','safari':'webkit-native','yt_music':'webkit-native',
 'gemini':'catalyst-or-swift','whatsapp':'catalyst-or-swift','telegram':'swift-appkit',
 'calendar':'appkit','finder':'appkit','notes':'appkit','reminders':'appkit','textedit':'appkit','music':'appkit','vlc':'appkit','utm':'appkit',
 'keynote':'custom-iwork','microsoft_word':'custom-cpp','zoom_us':'custom-cpp','obs':'qt-cef',
}

def iter_nodes(tree):
    stack=[tree]
    while stack:
        n=stack.pop()
        if not isinstance(n,dict): continue
        yield n
        stack.extend(n.get('children') or [])

def load(app, fname):
    p=os.path.join(BASE,app,fname)
    if not os.path.isfile(p): return None
    try: j=json.load(open(p))
    except Exception: return None
    d=j.get('data') or {}
    t=d.get('tree')
    return t

apps=sorted(FW)
# per app: role hist, actions per role, states hist, merged over full+forced (dedupe by capture: count separately)
report={}
role_action=defaultdict(lambda: defaultdict(Counter))  # fwclass -> role -> action counter
role_hist_fw=defaultdict(Counter)
role_hist_app=defaultdict(Counter)
states_app=defaultdict(Counter)
role_nodes_fw=defaultdict(Counter)  # denominators per role per fw
focused_per_app={}
action_presence=defaultdict(lambda: defaultdict(Counter))  # fw -> role -> counter of nodes with actions field

CAPS={'music':['full.json'],'obs':['full.json']}
for app in apps:
    files=CAPS.get(app,['full.json','forced.json'])
    fw=FW[app]
    seen_caps=[]
    for f in files:
        t=load(app,f)
        if t is None: continue
        seen_caps.append(f)
        nf=0; tot=0
        for n in iter_nodes(t):
            r=n.get('role','<none>')
            tot+=1
            role_hist_app[app][r]+=1
            role_hist_fw[fw][r]+=1
            role_nodes_fw[fw][r]+=1
            for a in n.get('available_actions') or []:
                role_action[fw][r][a]+=1
            st=n.get('states') or []
            for s in st: states_app[app][s]+=1
            if 'focused' in st: nf+=1
        focused_per_app.setdefault(app,[0,0])
        focused_per_app[app][0]+=nf; focused_per_app[app][1]+=tot
    report[app]=dict(caps=seen_caps)

out={
 'role_hist_app':{a:dict(c.most_common()) for a,c in role_hist_app.items()},
 'role_hist_fw':{a:dict(c.most_common()) for a,c in role_hist_fw.items()},
 'states_app':{a:dict(c.most_common()) for a,c in states_app.items()},
 'focused':{a:{'focused':v[0],'total':v[1],'pct':round(100*v[0]/max(v[1],1),1)} for a,v in focused_per_app.items()},
 'role_action':{fw:{r:dict(c.most_common()) for r,c in d.items()} for fw,d in role_action.items()},
}
json.dump(out, open('/Users/harshit/Desktop/YC/Ax_analysis/codex/tmp/roles_out.json','w'), indent=1)

# quick prints
print("=== focused noise ===")
for a,v in sorted(focused_per_app.items(), key=lambda kv:-kv[1][0]):
    print(f"{a:18s} focused={v[0]:5d} / {v[1]:6d} ({100*v[0]/max(v[1],1):5.1f}%)")
print("\n=== states per app (top) ===")
for a in apps:
    print(a, dict(states_app[a].most_common(8)))
