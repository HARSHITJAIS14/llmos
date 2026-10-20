import json, os, collections, statistics

BASE='/Users/harshit/Desktop/YC/Ax_analysis'
INTER={'button','link','textfield','switch','radiobutton','combobox','checkbox',
       'menubutton','slider','incrementor','disclosure','tab','menuitem','searchfield','popupbutton'}
STRUCT={'group','generic','unknown','layoutitem'}

# corrected source map
SRC={'music':'full.json'}
CLASSES={
 'appkit': ['calendar','finder','notes','reminders','textedit','safari','vlc','whatsapp','gemini','utm','music','keynote'],
 'chromium_browser': ['brave_browser','google_chrome'],
 'gecko': ['firefox'],
 'safari_webapp': ['yt_music'],
 'electron': ['antigravity_ide','claude','discord','notion'],
 'custom_cpp': ['microsoft_word','zoom_us'],
 'qt_cef': ['obs'],
}

def load(app):
    fn = SRC.get(app,'forced.json')
    p=os.path.join(BASE,app,fn)
    if not os.path.isfile(p): fn='full.json'; p=os.path.join(BASE,app,fn)
    d=json.load(open(p))['data']
    return fn,d['tree']

def walk(n,dep=0,inweb=None):
    yield n,dep,inweb
    nw = dep if n.get('role')=='webarea' else inweb
    for c in n.get('children') or []:
        yield from walk(c,dep+1,nw)

# Per-class aggregated interactive depth histogram + webarea-relative
for cls,apps in CLASSES.items():
    alldep=[]; relweb=[]; outsideweb=[]
    chain_lengths=[]
    noise_tot=0; node_tot=0
    for app in apps:
        try: fn,tree=load(app)
        except Exception: continue
        nodes=list(walk(tree))
        node_tot+=len(nodes)
        for n,dep,inweb in nodes:
            nm=n.get('name')
            if (nm is None or nm=='') and n.get('role') in STRUCT: noise_tot+=1
            if n.get('role') in INTER:
                alldep.append(dep)
                if inweb is not None: relweb.append(dep-inweb)
                else: outsideweb.append(dep)
        # chains
        def unnamed(n):
            nm=n.get('name'); return (nm is None or nm=='') and n.get('role') in STRUCT
        stack=[(tree,0)]
        while stack:
            node,run=stack.pop()
            kids=node.get('children') or []
            if unnamed(node) and len(kids)==1: stack.append((kids[0],run+1))
            else:
                if run>0: chain_lengths.append(run)
                for c in kids: stack.append((c,0))
    def stats(xs):
        if not xs: return 'n=0'
        xs=sorted(xs); n=len(xs)
        cum={}
        return f"n={n} min={xs[0]} p10={xs[n//10]} med={xs[n//2]} p90={xs[min(n-1,9*n//10)]} max={xs[-1]}"
    print(f"== {cls} (nodes={node_tot}, noise={noise_tot} = {100*noise_tot/max(1,node_tot):.1f}%)")
    print(f"   interactive abs depth: {stats(alldep)}")
    if relweb: print(f"   interactive depth REL to webarea: {stats(relweb)}")
    if outsideweb and relweb: print(f"   interactive OUTSIDE webarea (chrome UI): {stats(outsideweb)}")
    if chain_lengths:
        c=collections.Counter(chain_lengths)
        print(f"   wrapper chains: n={len(chain_lengths)} dist={dict(sorted(c.items()))}")
    print()

# coverage rule check: what depth band covers >=90% of interactives per class
for cls,apps in CLASSES.items():
    alldep=[]
    for app in apps:
        try: fn,tree=load(app)
        except Exception: continue
        for n,dep,inweb in walk(tree):
            if n.get('role') in INTER: alldep.append(dep)
    if not alldep: continue
    hist=collections.Counter(alldep)
    print(cls, 'interactive depth hist:', dict(sorted(hist.items())))
