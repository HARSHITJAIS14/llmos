import pickle,collections
rows=pickle.load(open('rows.pkl','rb'))
sel=pickle.load(open('sel.pkl','rb'))
R=[r for r in rows if sel[r['app']][0]==r['src']]
FWO=['appkit_apple','appkit_iwork','appkit_swift3p','appkit_3p','custom_kit','electron','chromium_browser','webkit_browser','webkit_webapp','gecko','qt_cef']
# role x framework
byfw=collections.defaultdict(collections.Counter)
apps_by_role=collections.defaultdict(set)
for r in R:
    byfw[r['fw']][r['role']]+=1
    apps_by_role[r['role']].add(r['app'])
roles=sorted({r['role'] for r in R}, key=lambda x:-sum(byfw[f][x] for f in byfw))
print(f"{'role':22s}"+''.join(f'{f[:9]:>10s}' for f in FWO)+'  napps')
for ro in roles:
    print(f'{ro:22s}'+''.join(('%10s'%(byfw[f][ro] or '')) for f in FWO)+f'  {len(apps_by_role[ro])}')
print()
print('=== ACTION VOCAB per framework ===')
for f in FWO:
    ac=collections.Counter()
    tot=0
    for r in R:
        if r['fw']!=f: continue
        tot+=1
        for a in r['acts']: ac[a]+=1
    apps=sorted({r['app'] for r in R if r['fw']==f})
    print(f'\n-- {f} (n={tot}) apps={apps}')
    for k,v in ac.most_common(): print(f'    {k:16s} {v:6d}  {100*v/tot:5.1f}%')
