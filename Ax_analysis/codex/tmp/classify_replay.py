import json,os
B='/Users/harshit/Desktop/YC/Ax_analysis'
apps="antigravity_ide brave_browser calendar claude discord finder firefox gemini google_chrome keynote microsoft_word music notes notion obs reminders safari telegram textedit utm vlc whatsapp yt_music zoom_us".split()
truth={'antigravity_ide':'chromium-family','claude':'chromium-family','discord':'chromium-family','notion':'chromium-family','brave_browser':'chromium-family','google_chrome':'chromium-family','firefox':'gecko','yt_music':'wkwebview','telegram':'opaque','obs':'qt','microsoft_word':'custom','zoom_us':'hybrid'}
def load(a,f):
    p=f'{B}/{a}/{f}'
    if not os.path.exists(p): return None
    try: d=json.load(open(p))
    except: return None
    if not d.get('ok'): return None
    return d['data']
def walk(n,d=0,path=()):
    yield n,d,path
    for c in n.get('children') or []:
        yield from walk(c,d+1,path+(n,))
STRUCT={'group','generic','unknown','layoutitem'}
def feats(t):
    nodes=list(walk(t)); n=len(nodes)
    web=[(x,d,p) for x,d,p in nodes if x.get('role')=='webarea']
    path=None
    if web:
        x,d,p=min(web,key=lambda z:z[1]); path=[q.get('role') for q in p[1:]]
    noise=sum(1 for x,_,_ in nodes if x.get('role') in STRUCT and not x.get('name'))/n
    roles={}
    for x,_,_ in nodes: roles[x.get('role')]=roles.get(x.get('role'),0)+1
    ids=[x['native_id']['value'] for x,_,_ in nodes if x.get('native_id') and x['native_id'].get('kind')=='ax_identifier']
    dotted=sum(1 for v in ids if v.count('.')>=2 and ' ' not in v)
    return dict(ids=len(ids),dotted=dotted,n=n,path=path,noise=noise,roles=roles,maxd=max(d for _,d,_ in nodes),
                opaque=(n==1 and t.get('subtree_truncated')))
def classify(sk,tr,refs):
    # C0 opaque
    if tr['n']==1 and tr['opaque'] and refs==0: return 'opaque'
    # C1 skeleton fingerprint
    if sk and sk['n']==7 and len(sk_root.get('children') or [])==4: return 'chromium-family'
    p=tr['path']
    if p is not None:
        if 'tabpanel' in p: return 'gecko'
        if 'tablist' in p: return 'wkwebview'
        if all(r=='group' for r in p): return 'chromium-family'
        return 'hybrid'
    r=tr['roles']; n=tr['n']
    if tr['ids']/n>=0.7 and tr['dotted']/tr['ids']>=0.5: return 'qt'
    if r.get('row',0)>=5 : return 'custom'
    return 'native'
ok=0;tot=0
for a in apps:
    skd=load(a,'skeleton.json'); fd=load(a,'full.json')
    fo=load(a,'forced.json') if a!='music' else None
    use=fd
    sk=feats(skd['tree']) if skd else None
    global sk_root
    sk_root=skd['tree'] if skd else {}
    # classify from default full; path requires the webarea which exists at depth<=10
    tr=feats(use['tree'])
    c=classify(sk,tr,use.get('ref_count',1))
    t=truth.get(a,'native'); tot+=1; ok+=(c==t)
    print(f"{a:16} n={tr['n']:5} noise={tr['noise']:.2f} path={tr['path']} -> {c:16} truth={t} {'OK' if c==t else 'MISS'}  btn%={tr['roles'].get('button',0)/tr['n']:.2f} rows={tr['roles'].get('row',0)}")
print(ok,'/',tot)
