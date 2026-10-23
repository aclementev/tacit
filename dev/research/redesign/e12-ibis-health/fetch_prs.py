import json,subprocess,sys
def q(cursor, search):
    after = f', after:"{cursor}"' if cursor else ''
    query = '''query { search(query:"%s", type:ISSUE, first:50%s){ pageInfo{hasNextPage endCursor} nodes{ ... on PullRequest{ number title createdAt mergedAt closedAt state isDraft authorAssociation additions deletions
      author{login __typename} mergedBy{login} reviews(first:5){nodes{author{login} createdAt state}} comments(first:3){nodes{author{login} createdAt}} } } } }''' % (search, after)
    return json.loads(subprocess.check_output(['gh','api','graphql','-f','query='+query]))
out=[]
import datetime
# search caps at 1000 results per query -> split by month
months=[]
y,m=2024,1
while (y,m)<=(2026,10):
    ny,nm=(y,m+1) if m<12 else (y+1,1)
    months.append((f'{y}-{m:02d}-01',f'{ny}-{nm:02d}-01'));y,m=ny,nm
for a,b in months:
    search=f'repo:ibis-project/ibis is:pr created:{a}..{b}'
    cur=None
    while True:
        r=q(cur,search)['data']['search']
        out+= [n for n in r['nodes'] if n]
        if not r['pageInfo']['hasNextPage']:break
        cur=r['pageInfo']['endCursor']
    print(a,len(out),file=sys.stderr)
json.dump(out,open('prs_since2024.json','w'))
