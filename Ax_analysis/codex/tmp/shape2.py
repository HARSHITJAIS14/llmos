import json, os, collections, statistics

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'
apps = [d for d in sorted(os.listdir(BASE)) if os.path.isfile(os.path.join(BASE, d, 'meta.json'))]

INTERACTIVE = {'button','link','textfield','switch','radiobutton','combobox','checkbox',
               'menubutton','slider','incrementor','disclosure','tab','menuitem','searchfield',
               'popupbutton'}
SELECTABLE = {'treeitem','cell','row'}
STRUCT = {'group','generic','unknown','layoutitem'}

FRAMEWORK = {
 'appkit': ['calendar','finder','music','notes','reminders','textedit','safari','keynote','telegram','utm','vlc','whatsapp','gemini'],
 'chromium_browser': ['brave_browser','google_chrome'],
 'gecko': ['firefox'],
 'safari_webapp': ['yt_music'],
 'electron': ['antigravity_ide','claude','discord','notion'],
 'qt_cef': ['obs'],
 'custom_cpp': ['microsoft_word','zoom_us'],
}
FW = {a:k for k,v in FRAMEWORK.items() for a in v}

def load(app):
    for fname in ('forced.json','full.json'):
        p = os.path.join(BASE, app, fname)
        if not os.path.isfile(p): continue
        try: d = json.load(open(p))
        except Exception: continue
        dd = d.get('data')
        if isinstance(dd, dict) and dd.get('tree'):
            return fname, dd
    return None, None

def walk(node, depth=0, parent=None):
    yield node, depth, parent
    for c in node.get('children') or []:
        yield from walk(c, depth+1, node)

def pct(xs, q):
    if not xs: return None
    xs = sorted(xs)
    i = min(len(xs)-1, int(q*len(xs)))
    return xs[i]

results = {}
for app in apps:
    fname, dd = load(app)
    if not dd:
        results[app] = None
        continue
    tree = dd['tree']
    nodes = list(walk(tree))
    total = len(nodes)
    depths = [d for _,d,_ in nodes]
    idepths = [d for n,d,_ in nodes if n.get('role') in INTERACTIVE]
    sdepths = [d for n,d,_ in nodes if n.get('role') in SELECTABLE]
    # branching
    kidcounts = [len(n.get('children') or []) for n,_,_ in nodes]
    nonleaf = [k for k in kidcounts if k>0]
    # unnamed struct noise
    def unnamed(n):
        nm = n.get('name')
        return (nm is None or nm=='') and n.get('role') in STRUCT
    noise = sum(1 for n,_,_ in nodes if unnamed(n))
    # wrapper chains: maximal runs of single-child unnamed-struct nodes
    chains = []
    def chainwalk(n):
        stack=[(n,0)]
        while stack:
            node,run = stack.pop()
            kids = node.get('children') or []
            if unnamed(node) and len(kids)==1:
                stack.append((kids[0], run+1))
            else:
                if run>0: chains.append(run)
                for c in kids: stack.append((c,0))
    chainwalk(tree)
    # webarea
    webareas = [(d, n) for n,d,_ in nodes if n.get('role')=='webarea']
    wa_info = []
    for d, wa in webareas:
        sub = sum(1 for _ in walk(wa))
        wa_info.append({'depth': d, 'subtree': sub})
    # truncation residuals
    trunc = [(n.get('role'), d, len(n.get('children') or [])) for n,d,_ in nodes if n.get('subtree_truncated')]
    results[app] = dict(
        src=fname, fw=FW.get(app,'?'), total=total, maxdepth=max(depths),
        complete=dd.get('complete'), truncated_flag=dd.get('truncated'),
        n_inter=len(idepths),
        i_min=min(idepths) if idepths else None, i_p10=pct(idepths,0.1),
        i_med=pct(idepths,0.5), i_p90=pct(idepths,0.9),
        i_max=max(idepths) if idepths else None,
        n_sel=len(sdepths), s_med=pct(sdepths,0.5), s_max=max(sdepths) if sdepths else None,
        bf_mean=round(statistics.mean(nonleaf),2) if nonleaf else 0,
        bf_max=max(kidcounts) if kidcounts else 0,
        noise=noise, noise_ratio=round(noise/total,3),
        chain_n=len(chains), chain_max=max(chains) if chains else 0,
        chain_mean=round(statistics.mean(chains),2) if chains else 0,
        webareas=wa_info,
        trunc_n=len(trunc), trunc_sample=trunc[:8],
    )

hdr = f"{'app':16}{'fw':16}{'src':8}{'N':>6}{'maxD':>5}{'nInt':>6}{'iMin':>5}{'iMed':>5}{'iP90':>5}{'iMax':>5}{'bfMu':>6}{'bfMx':>6}{'noise%':>7}{'chMx':>5}{'chMu':>6}{'trunc':>6}"
print(hdr)
for app, r in results.items():
    if not r: print(f"{app:16} NO TREE"); continue
    print(f"{app:16}{r['fw']:16}{r['src'][:6]:8}{r['total']:>6}{r['maxdepth']:>5}{r['n_inter']:>6}"
          f"{str(r['i_min']):>5}{str(r['i_med']):>5}{str(r['i_p90']):>5}{str(r['i_max']):>5}"
          f"{r['bf_mean']:>6}{r['bf_max']:>6}{r['noise_ratio']*100:>6.1f}%{r['chain_max']:>5}{r['chain_mean']:>6}{r['trunc_n']:>6}")

print()
print("WEBAREAS:")
for app, r in results.items():
    if r and r['webareas']:
        print(f"  {app}: {r['webareas']}  (total={r['total']})")
print()
print("TRUNCATION RESIDUALS (role, depth, kid_count):")
for app, r in results.items():
    if r and r['trunc_n']:
        print(f"  {app} ({r['src']}): n={r['trunc_n']} sample={r['trunc_sample']}")
print()
print("COMPLETE/TRUNCATED FLAGS:")
for app, r in results.items():
    if r:
        print(f"  {app}: complete={r['complete']} truncated={r['truncated_flag']} src={r['src']}")

json.dump(results, open('/Users/harshit/Desktop/YC/Ax_analysis/codex/tmp/shape_results.json','w'), indent=1)
