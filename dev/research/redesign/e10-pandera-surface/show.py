"""Render results_tuned*.json as one markdown table. usage: uv run --frozen python show.py"""
import glob
import json

print("| dataset | config | queries | min wall s | cpu s | outcome |\n|---|---|---|---|---|---|")
for f in sorted(glob.glob("results_tuned*.json")):
    for r in json.load(open(f)):
        ds, cfg = r["label"].split(" | ")
        print(f"| {ds} | {cfg} | {r['queries']} | {r['min_s']} | {r['cpu_min_s']} | {r['outcome']} |")
