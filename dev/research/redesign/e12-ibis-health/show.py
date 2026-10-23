import json,subprocess,sys
def g(p):return json.loads(subprocess.check_output(['gh','api','--paginate',p]) )
for n in sys.argv[1:]:
    i=g(f'repos/ibis-project/ibis/issues/{n}')
    print('\n=====',n,i['title'],i['state'],i['user']['login'],i['created_at'][:10],i['closed_at'],i.get('state_reason'),'PR' if i.get('pull_request') else '')
    print((i['body'] or '')[:1800])
    try:
        cs=subprocess.check_output(['gh','api','--paginate',f'repos/ibis-project/ibis/issues/{n}/comments'])
        import re
        # paginate may concatenate arrays
        txt=cs.decode().replace('][',',')
        for c in json.loads(txt):print('--- %s %s\n%s'%(c['user']['login'],c['created_at'][:10],c['body'][:1500]))
    except Exception as e:print('ERR',e)
