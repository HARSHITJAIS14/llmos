import tv_lib as L, collections, json

VR = ['textfield','textarea','statictext','cell','row','treeitem','link','heading','button','image','combobox','checkbox','switch','slider','menubutton','radiobutton','list','group','outline','tablist','webarea']

def ne(v):
    return isinstance(v,str) and v.strip() != ''

rows=[]
for a in L.APPS:
    ns,src=L.best(a)
    per=collections.defaultdict(lambda: collections.Counter())
    for n,_,_ in ns:
        r=n.get('role'); c=per[r]
        c['n']+=1
        if ne(n.get('name')): c['name']+=1
        if ne(n.get('value')): c['value']+=1
        if ne(n.get('description')): c['desc']+=1
        if not ne(n.get('name')) and not ne(n.get('value')) and not ne(n.get('description')): c['blank']+=1
    for r,c in sorted(per.items(), key=lambda kv:-kv[1]['n']):
        if c['n']<2: continue
        rows.append((a,src,r,c['n'],c['name'],c['value'],c['desc'],c['blank']))

print('app                role             n  name%  val% desc% blank%')
for a,src,r,n,nm,va,de,bl in rows:
    if r not in VR: continue
    print(f'{a:18s} {r:12s} {n:5d} {100*nm/n:6.0f} {100*va/n:6.0f} {100*de/n:6.0f} {100*bl/n:7.0f}')
