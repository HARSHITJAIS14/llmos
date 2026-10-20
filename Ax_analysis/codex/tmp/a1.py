import lib, collections, json, statistics

BAD = {('music','forced')}
VALID = [a for a in lib.apps() if lib.nodes(lib.load(a,'full'))]

def best(app):
    """deepest valid capture"""
    f = lib.load(app,'forced')
    if (app,'forced') not in BAD and f and f.get('ok') and lib.nodes(f):
        nf = lib.nodes(f); nu = lib.nodes(lib.load(app,'full'))
        if len(nf) >= len(nu): return 'forced', nf
    return 'full', lib.nodes(lib.load(app,'full'))

print(f"{'app':20}{'cls':17}{'src':7}{'N':>6}{'maxd':>5}  {'actionable':>10} {'act_d_median':>12} {'act_d_p10-p90':>14}  {'containers%':>11} {'unnamed_grp%':>12}")
rows={}
for a in VALID:
    src, ns = best(a)
    N=len(ns)
    act=[d for d,n,p,pa in ns if lib.has_action(n)]
    cont=[1 for d,n,p,pa in ns if (n.get('role') or '') in lib.CONTAINER_ROLES]
    ugrp=[1 for d,n,p,pa in ns if (n.get('role') or '') in lib.CONTAINER_ROLES and not n.get('name')]
    md = statistics.median(act) if act else -1
    if act:
        s=sorted(act); p10=s[int(.1*(len(s)-1))]; p90=s[int(.9*(len(s)-1))]
    else: p10=p90=-1
    rows[a]=dict(src=src,N=N,act=act,ns=ns)
    print(f"{a:20}{lib.CLASS.get(a,'?'):17}{src:7}{N:>6}{max(d for d,_,_,_ in ns):>5}  {len(act):>10} {md:>12} {str(p10)+'-'+str(p90):>14}  {100*len(cont)/N:>10.1f}% {100*len(ugrp)/N:>11.1f}%")

print()
print('=== depth histogram of ACTIONABLE nodes, per class (normalized) ===')
byc=collections.defaultdict(collections.Counter)
tot=collections.Counter()
for a in VALID:
    c=lib.CLASS.get(a,'?')
    for d in rows[a]['act']:
        byc[c][d]+=1; tot[c]+=1
for c in sorted(byc):
    h=byc[c]; t=tot[c]
    line=' '.join(f"{d}:{100*h[d]/t:.0f}%" for d in sorted(h) if h[d]/t>=0.02)
    print(f"{c:18} n={t:5}  {line}")
