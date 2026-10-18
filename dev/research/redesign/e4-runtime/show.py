import sys, json
for f in sys.argv[1:]:
    print("##", f)
    for l in open(f):
        if l.startswith("{"):
            try: r = json.loads(l)
            except Exception: print("TRUNC"); continue
            print(f"{r['label'][:120]:120s} q={r['queries']:>2} wall={r['min_s']:>7} cpu={r['cpu_min_s']:>7} {r['outcome']}")
        else: print(l.rstrip()[:200])
