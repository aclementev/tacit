import json,statistics as st,collections
from datetime import datetime as D
d=json.load(open('issues_since2024.json'))
t=lambda s:D.fromisoformat(s.replace('Z','+00:00'))
team={'cpcloud','gforsyth','NickCrews','deepyaman','jcrist','kszucs','tswast','lostmygithubaccount','mesejo','ncclementi','IndexSeek'}
def isbot(l):return l is None or 'bot' in l.lower() or 'github-actions' in l
rows=collections.defaultdict(list)
for i in d:
    a=(i['author'] or {}).get('login')
    if isbot(a):continue
    # first response by someone other than author, non-bot
    resp=[t(c['createdAt']) for c in i['comments']['nodes'] if c['author'] and c['author']['login']!=a and not isbot(c['author']['login'])]
    teamresp=[t(c['createdAt']) for c in i['comments']['nodes'] if c['author'] and c['author']['login'] in team]
    r=(min(resp)-t(i['createdAt'])).total_seconds()/86400 if resp else None
    tr=(min(teamresp)-t(i['createdAt'])).total_seconds()/86400 if teamresp else None
    q=i['createdAt'][:4]+'H'+('1' if int(i['createdAt'][5:7])<=6 else '2')
    if i['createdAt']>='2026-07':q='2026Q3+'
    rows[q].append((r,tr,i))
print('period  n  any_resp%  team_resp%  median_days_to_team_resp  team_resp_within7d%  closed%  stale_open')
for q in sorted(rows):
    L=rows[q];n=len(L)
    anyr=sum(1 for r,tr,i in L if r is not None);tm=[tr for r,tr,i in L if tr is not None]
    print(q,n,f'{100*anyr/n:.0f}',f'{100*len(tm)/n:.0f}',f'{st.median(tm):.1f}' if tm else '-',f'{100*sum(1 for x in tm if x<=7)/n:.0f}',f'{100*sum(1 for r,tr,i in L if i["state"]=="CLOSED")/n:.0f}',sum(1 for r,tr,i in L if i['state']=='OPEN'))
