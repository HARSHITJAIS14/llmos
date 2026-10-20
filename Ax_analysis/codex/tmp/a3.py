import lib, collections
BAD={('music','forced')}
VALID=[a for a in lib.apps() if lib.nodes(lib.load(a,'full'))]
def best(app):
    f=lib.load(app,'forced')
    if (app,'forced') not in BAD and f and f.get('ok') and lib.nodes(f):
        nf=lib.nodes(f)
        if len(nf)>=len(lib.nodes(lib.load(app,'full'))): return 'forced',nf,lib.tree_of(f)
    u=lib.load(app,'full'); return 'full',lib.nodes(u),lib.tree_of(u)

print('=== role distribution (top 8) per app ===')
for a in VALID:
    src,ns,t=best(a)
    c=collections.Counter((n.get('role') or '?') for d,n,p,pa in ns)
    top=' '.join(f"{r}:{v}" for r,v in c.most_common(8))
    print(f"{a:20}{lib.CLASS.get(a,'?'):17} {top}")

print()
print('=== single-child-parent role -> child role, most common pairs (structural pass-through) ===')
for a in VALID:
    src,ns,t=best(a)
    pairs=collections.Counter()
    for d,n,p,pa in ns:
        ch=n.get('children') or []
        if len(ch)==1:
            pairs[( (n.get('role') or '?')+('*' if n.get('name') else ''), ch[0].get('role') or '?')]+=1
    tot=sum(pairs.values())
    if not tot: continue
    top=' | '.join(f"{k[0]}>{k[1]}:{v}" for k,v in pairs.most_common(4))
    print(f"{a:20}{tot:>5} {top}")
