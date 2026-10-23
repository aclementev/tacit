import json,statistics as st,collections
from datetime import datetime as D
d=json.load(open('prs_since2024.json'))
def t(s):return D.fromisoformat(s.replace('Z','+00:00')) if s else None
bots=('renovate','dependabot','pre-commit-ci','github-actions','ibis-squawk','copilot')
def isbot(p):
    a=p.get('author') or {}
    return a.get('__typename')=='Bot' or any(b in (a.get('login') or '').lower() for b in bots)
print('total PRs',len(d))
by=collections.defaultdict(list)
for p in d:
    if isbot(p):continue
    by[p['createdAt'][:7]].append(p)
members={'cpcloud','gforsyth','NickCrews','deepyaman','jcrist','kszucs','tswast','lostmygithubaccount','mesejo','ncclementi','IndexSeek'}
print('month  opened merged  merged_by_top  ext_opened ext_merged ext_med_h  ext_merge_rate')
for m in sorted(by):
    if m<'2024-01':continue
    ps=by[m];mg=[p for p in ps if p['mergedAt']]
    ext=[p for p in ps if p['author']['login'] not in members] if True else []
    emg=[p for p in ext if p['mergedAt']]
    hrs=[(t(p['mergedAt'])-t(p['createdAt'])).total_seconds()/3600 for p in emg]
    mb=collections.Counter((p['mergedBy'] or {}).get('login') for p in mg).most_common(2)
    print(m,len(ps),len(mg),mb,len(ext),len(emg),f'{st.median(hrs):.0f}' if hrs else '-',f'{len(emg)/len(ext):.2f}' if ext else '-')
# merged per month (by mergedAt), human authors and merged-by distribution 2026
mm=collections.Counter(); mbm=collections.defaultdict(collections.Counter)
for p in d:
    if p['mergedAt'] and not isbot(p):
        mm[p['mergedAt'][:7]]+=1; mbm[p['mergedAt'][:7]][(p['mergedBy'] or {}).get('login')]+=1
print('\nmerged human PRs by merge month, merger')
for m in sorted(mm):
    if m>='2025-06':print(m,mm[m],dict(mbm[m]))
# 2026 small external PR TTM
ext26=[p for p in d if not isbot(p) and p['author']['login'] not in members and p['createdAt']>='2026-02-08']
mg=[p for p in ext26 if p['mergedAt']]
hrs=[(t(p['mergedAt'])-t(p['createdAt'])).total_seconds()/86400 for p in mg]
print('\next PRs created since 2026-02-08:',len(ext26),'merged',len(mg),'median days',st.median(hrs),'p75',st.quantiles(hrs,n=4)[2], 'closed unmerged',sum(1 for p in ext26 if p['state']=='CLOSED' and not p['mergedAt']),'open',sum(1 for p in ext26 if p['state']=='OPEN'))
small=[p for p in mg if p['additions']+p['deletions']<=50]
h2=[(t(p['mergedAt'])-t(p['createdAt'])).total_seconds()/86400 for p in small]
print('small (<=50 lines) ext merged',len(small),'median days',st.median(h2) if h2 else None)
# all external PRs 2025-02..2026-02-07 for comparison
ext25=[p for p in d if not isbot(p) and p['author']['login'] not in members and '2025-02-07'<=p['createdAt']<'2026-02-08']
mg5=[p for p in ext25 if p['mergedAt']]
print('ext PRs 2025-02-07..2026-02-07:',len(ext25),'merged',len(mg5),'median days',st.median([(t(p['mergedAt'])-t(p['createdAt'])).total_seconds()/86400 for p in mg5]))
# open PR stock
print('open PRs (created>=2024) now:',sum(1 for p in d if p['state']=='OPEN'), ' drafts',sum(1 for p in d if p['state']=='OPEN' and p['isDraft']))
# first-response for ext PRs 2026: first review or comment from someone other than author
def first_resp(p):
    c=[]
    for r in (p['reviews']['nodes'] or []):
        if r['author'] and r['author']['login']!=p['author']['login']: c.append(t(r['createdAt']))
    for r in (p['comments']['nodes'] or []):
        if r['author'] and r['author']['login']!=p['author']['login'] and 'bot' not in r['author']['login'].lower(): c.append(t(r['createdAt']))
    return min(c) if c else None
for lab,sel in (('2025-02-07..2026-02-07',ext25),('since 2026-02-08',ext26)):
    fr=[(first_resp(p)-t(p['createdAt'])).total_seconds()/86400 for p in sel if first_resp(p)]
    print('ext PR first human response',lab,'n',len(fr),'of',len(sel),'median days',round(st.median(fr),2),'no response',sum(1 for p in sel if not first_resp(p)))
