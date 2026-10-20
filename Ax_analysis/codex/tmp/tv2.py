import tv_lib as L, collections

def ne(v): return isinstance(v,str) and v.strip()!=''

print('=== name/value relationship where BOTH present ===')
print('app                role         both  n==v  v_startswith_n  distinct')
for a in L.APPS:
    ns,_=L.best(a)
    per=collections.defaultdict(lambda: collections.Counter())
    for n,_,_ in ns:
        nm,va=n.get('name'),n.get('value')
        if ne(nm) and ne(va):
            c=per[n.get('role')]; c['both']+=1
            if nm==va: c['eq']+=1
            elif va.startswith(nm) or nm.startswith(va): c['pre']+=1
            else: c['dis']+=1
    for r,c in sorted(per.items(), key=lambda kv:-kv[1]['both']):
        if c['both']<2: continue
        print(f"{a:18s} {r:12s} {c['both']:5d} {c['eq']:5d} {c['pre']:14d} {c['dis']:8d}")

print()
print('=== value-only nodes (value present, name absent) by app/role ===')
for a in L.APPS:
    ns,_=L.best(a)
    per=collections.Counter()
    for n,_,_ in ns:
        if ne(n.get('value')) and not ne(n.get('name')): per[n.get('role')]+=1
    if per: print(f'{a:18s}', dict(per))

print()
print('=== name-only nodes (name present, value absent) totals ===')
for a in L.APPS:
    ns,_=L.best(a)
    no=sum(1 for n,_,_ in ns if ne(n.get('name')) and not ne(n.get('value')))
    vo=sum(1 for n,_,_ in ns if ne(n.get('value')) and not ne(n.get('name')))
    bo=sum(1 for n,_,_ in ns if ne(n.get('value')) and ne(n.get('name')))
    de=sum(1 for n,_,_ in ns if ne(n.get('description')))
    print(f'{a:18s} nameonly={no:5d} valonly={vo:5d} both={bo:5d} desc={de:4d} total={len(ns)}')
