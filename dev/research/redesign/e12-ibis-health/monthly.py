import collections,sys
bots=('renovate','dependabot','pre-commit-ci','semantic-release','github-actions','ibis-docs-bot','ibis-project-bot')
rows=[l.rstrip('\n').split('|',3) for l in open(sys.argv[1])]
def isbot(a,e,s): 
    t=(a+e).lower()
    return any(b in t for b in bots)
m=collections.defaultdict(lambda:[0,0,collections.Counter()])
for d,a,e,s in rows:
    if isbot(a,e,s): m[d][1]+=1
    else: m[d][0]+=1; m[d][2][a]+=1
tot=0
for d in sorted(m):
    if d>='2024-01':print(d,'human',m[d][0],'bot',m[d][1],' top:',', '.join(f'{a}:{n}' for a,n in m[d][2].most_common(3)))
def span(a,b):
    return sum(v[0] for d,v in m.items() if a<=d<=b)
print('human 2025-02..2026-01',span('2025-02','2026-01'))
print('human 2026-02..2026-10',span('2026-02','2026-10'))
print('human 2025-10..2026-02 incl',span('2025-10','2026-02'))
print('human 2024',span('2024-01','2024-12'),'2025',span('2025-01','2025-12'),'2026ytd',span('2026-01','2026-10'))
