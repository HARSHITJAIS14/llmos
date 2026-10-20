import json,os,collections,pickle
BASE='/Users/harshit/Desktop/YC/Ax_analysis'
APPS=[d for d in sorted(os.listdir(BASE)) if os.path.isfile(os.path.join(BASE,d,'meta.json'))]
def load(app,f):
    p=os.path.join(BASE,app,f+'.json')
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except Exception: return None
def tree_of(doc):
    if not doc or not doc.get('ok'): return None
    return (doc.get('data') or {}).get('tree')
def walk(node,depth=0,parent=None):
    if not isinstance(node,dict): return
    yield node,depth,parent
    for c in (node.get('children') or []):
        yield from walk(c,depth+1,node)
FW={
 'antigravity_ide':'electron','claude':'electron','discord':'electron','notion':'electron',
 'brave_browser':'chromium_browser','google_chrome':'chromium_browser',
 'obs':'qt_cef',
 'safari':'webkit_browser','yt_music':'webkit_webapp','gemini':'webkit_webapp',
 'firefox':'gecko',
 'calendar':'appkit_apple','finder':'appkit_apple','music':'appkit_apple','notes':'appkit_apple',
 'reminders':'appkit_apple','textedit':'appkit_apple','keynote':'appkit_iwork',
 'telegram':'appkit_swift3p','whatsapp':'appkit_swift3p','vlc':'appkit_3p','utm':'appkit_3p',
 'microsoft_word':'custom_kit','zoom_us':'custom_kit',
}
rows=[]
for app in APPS:
    if app not in FW: continue
    for src in ('full','forced'):
        t=tree_of(load(app,src))
        if t is None: continue
        for n,d,par in walk(t):
            st=n.get('states')
            rows.append(dict(app=app,fw=FW[app],src=src,depth=d,
                role=n.get('role'),sub=n.get('subrole'),
                acts=tuple(sorted(n.get('available_actions') or [])),
                states=tuple(sorted(st)) if isinstance(st,list) else (st if st is None else str(st)),
                name=n.get('name'),value=n.get('value'),desc=n.get('description'),
                trunc=bool(n.get('subtree_truncated')),nkids=len(n.get('children') or []),
                keys=tuple(sorted(n.keys())),bounds=n.get('bounds'),
                prole=(par or {}).get('role')))
pickle.dump(rows,open(BASE+'/codex/tmp/roleact/rows.pkl','wb'))
print('rows',len(rows))
ak=collections.Counter()
for r in rows: ak.update(r['keys'])
for k,v in ak.most_common(): print(f'  {k:24s} {v}')
print('apps with data:',sorted({(r['app'],r['src']) for r in rows}))
