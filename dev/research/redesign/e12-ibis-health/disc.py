import json,subprocess,sys
q='''query{repository(owner:"ibis-project",name:"ibis"){discussions(first:100,orderBy:{field:CREATED_AT,direction:DESC}){nodes{number title createdAt author{login} body category{name} comments(first:30){nodes{author{login} createdAt body replies(first:10){nodes{author{login} createdAt body}}}}}}}}'''
d=json.loads(subprocess.check_output(['gh','api','graphql','-f','query='+q]))
json.dump(d,open('discussions.json','w'))
for n in d['data']['repository']['discussions']['nodes']:
    print(n['number'],n['createdAt'][:10],n['category']['name'],n['author']['login'] if n['author'] else '-',n['title'][:90],len(n['comments']['nodes']))
