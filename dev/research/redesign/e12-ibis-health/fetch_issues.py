import json,subprocess,sys
def q(cursor, search):
    after = f', after:"{cursor}"' if cursor else ''
    query = '''query { search(query:"%s", type:ISSUE, first:50%s){ pageInfo{hasNextPage endCursor} nodes{ ... on Issue{ number title createdAt closedAt state stateReason authorAssociation author{login}
      comments(first:6){nodes{author{login} createdAt authorAssociation}} } } } }''' % (search, after)
    return json.loads(subprocess.check_output(['gh','api','graphql','-f','query='+query]))
out=[]
y,m=2024,1
while (y,m)<=(2026,10):
    ny,nm=(y,m+1) if m<12 else (y+1,1)
    a,b=f'{y}-{m:02d}-01',f'{ny}-{nm:02d}-01';y,m=ny,nm
    cur=None
    while True:
        r=q(cur,f'repo:ibis-project/ibis is:issue created:{a}..{b}')['data']['search']
        out+=[n for n in r['nodes'] if n]
        if not r['pageInfo']['hasNextPage']:break
        cur=r['pageInfo']['endCursor']
json.dump(out,open('issues_since2024.json','w'));print(len(out))
