import lib, collections, statistics

BAD={('music','forced')}
VALID=[a for a in lib.apps() if lib.nodes(lib.load(a,'full'))]
def best(app):
    f=lib.load(app,'forced')
    if (app,'forced') not in BAD and f and f.get('ok') and lib.nodes(f):
        nf=lib.nodes(f)
        if len(nf)>=len(lib.nodes(lib.load(app,'full'))): return 'forced',nf,lib.tree_of(f)
    u=lib.load(app,'full'); return 'full',lib.nodes(u),lib.tree_of(u)

print('=== WRAPPER CHAINS: maximal runs of single-child unnamed container nodes ===')
print(f"{'app':20}{'cls':17}{'chains':>7}{'maxlen':>7}{'meanlen':>8}{'nodes_in_chains%':>18}{'longest_path'}")
for a in VALID:
    src,ns,t=best(a)
    if not t: continue
    chains=[]
    def rec(n,depth,run):
        c=n.get('children') or []
        wrap = ((n.get('role') or '') in lib.CONTAINER_ROLES) and not n.get('name') and len(c)==1
        if wrap: run=run+[n]
        else:
            if run: chains.append(list(run))
            run=[]
        for ch in c: rec(ch,depth+1,run if wrap else [])
        if wrap and not c and run: chains.append(list(run))
    # simpler: iterative over parent links
    chains=[]
    cur=[]
    def rec2(n):
        global cur
        c=n.get('children') or []
        wrap=((n.get('role') or '') in lib.CONTAINER_ROLES) and not n.get('name') and len(c)==1
        if wrap:
            cur=cur+[n]; saved=cur
            rec2(c[0])
        else:
            if cur: chains.append(cur)
            cur=[]
            for ch in c:
                cur=[]
                rec2(ch)
            if cur: chains.append(cur); cur=[]
    # do a clean recursive version
    chains=[]
    def rec3(n, run):
        c=n.get('children') or []
        wrap=((n.get('role') or '') in lib.CONTAINER_ROLES) and not n.get('name') and len(c)==1
        if wrap:
            rec3(c[0], run+1)
        else:
            if run: chains.append(run)
            for ch in c: rec3(ch, 0)
    rec3(t,0)
    if not chains:
        print(f"{a:20}{lib.CLASS.get(a,'?'):17}{0:>7}{0:>7}{0:>8.1f}{0:>17.1f}%")
        continue
    tot=sum(chains)
    print(f"{a:20}{lib.CLASS.get(a,'?'):17}{len(chains):>7}{max(chains):>7}{statistics.mean(chains):>8.1f}{100*tot/len(ns):>17.1f}%")

print()
print('=== BRANCHING: children-count distribution over nodes with >=1 child ===')
print(f"{'app':20}{'cls':17}{'internal':>9}{'leaf':>7}{'mean_bf':>8}{'median_bf':>10}{'max_bf':>7}{'pct_bf==1':>10}")
for a in VALID:
    src,ns,t=best(a)
    bf=[len(n.get('children') or []) for d,n,p,pa in ns if n.get('children')]
    leaf=len(ns)-len(bf)
    if not bf: continue
    print(f"{a:20}{lib.CLASS.get(a,'?'):17}{len(bf):>9}{leaf:>7}{statistics.mean(bf):>8.2f}{statistics.median(bf):>10.1f}{max(bf):>7}{100*sum(1 for x in bf if x==1)/len(bf):>9.1f}%")
