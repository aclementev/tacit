"""Task 1: facade coverage of ibis 12's public column/scalar API per value family.

python coverage.py API.json FACADE.pyi  -> out/coverage.txt + out/coverage.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from facade_parse import parse

FAM = {  # ibis family -> facade element type (None: no Column[T] for it)
    "Integer": "int", "Floating": "float", "Decimal": "Decimal", "String": "str", "Boolean": "bool",
    "Timestamp": "datetime", "Date": "date", "Time": "time",
    "Interval": None, "Array": None, "Struct": None, "Map": None, "JSON": None,
}
# Expression plumbing, not column operations a pipeline author types against.
INFRA = {
    "compile", "execute", "to_pandas", "to_polars", "to_pyarrow", "to_pyarrow_batches", "to_csv",
    "to_parquet", "to_delta", "to_json", "to_torch", "to_list", "to_sql", "visualize", "pipe", "op",
    "equals", "get_backend", "unbind", "has_name", "get_name", "type", "as_table", "as_scalar",
    "preview", "to_parquet_dir", "to_xlsx", "to_pandas_batches", "to_geo", "to_array", "to_frame",
}


def main(api_path: str, pyi: str, out_dir: str) -> None:
    api = json.load(open(api_path))["classes"]
    facade = parse(Path(pyi))
    value_names = set(api["Value"]["members"])
    rows, data = [], {}
    rows.append(f"ibis {json.load(open(api_path))['ibis']}; facade {pyi}")
    rows.append("")
    hdr = f"{'family':<10} {'kind':<6} {'ibis pub':>8} {'infra':>5} {'ops':>4} {'typed':>5} {'via Value':>9} {'unreach':>7}"
    rows.append(hdr)
    for fam, el in FAM.items():
        for kind in ("Column", "Scalar"):
            cls = api.get(f"{fam}{kind}")
            if cls is None:
                continue
            mem = cls["members"]
            names = sorted(n for n in mem if mem[n]["kind"] != "attr" or True)
            ops = [n for n in names if n.startswith("__")]
            infra = [n for n in names if n in INFRA]
            meths = [n for n in names if not n.startswith("__") and n not in INFRA]
            fmeths = facade[kind]
            typed, via_value, unreach = [], [], []
            for n in meths + ops:
                ok = el is not None and n in fmeths and any(f == el for f, _ in fmeths[n])
                if ok:
                    typed.append(n)
                elif n in value_names:
                    via_value.append(n)  # inherited from ir.Value: ibis-typed, element type lost
                else:
                    unreach.append(n)  # static attribute/operator error on Column[T]
            data[f"{fam}{kind}"] = dict(typed=typed, via_value=via_value, unreachable=unreach, infra=infra,
                                        n_methods=len(meths), n_ops=len(ops))
            rows.append(f"{fam:<10} {kind:<6} {len(meths):>8} {len(infra):>5} {len(ops):>4} {len(typed):>5} {len(via_value):>9} {len(unreach):>7}")
    rows.append("")
    for k, d in data.items():
        rows.append(f"== {k}: typed {len(d['typed'])}; via ir.Value {len(d['via_value'])}; unreachable {len(d['unreachable'])}")
        rows.append(f"   unreachable: {' '.join(d['unreachable'])}")
        rows.append(f"   via Value:   {' '.join(d['via_value'])}")
    # facade-declared names not on the ibis class (declared but nonexistent)
    rows.append("")
    for fam, el in FAM.items():
        if el is None:
            continue
        for kind in ("Column", "Scalar"):
            mem = api[f"{fam}{kind}"]["members"]
            ghost = sorted(n for n, fs in facade[kind].items() if any(f == el for f, _ in fs)
                           and n not in mem and n not in ("__get__", "__set__"))
            if ghost:
                rows.append(f"declared on facade for {kind}[{el}] but absent on ibis {fam}{kind}: {ghost}")
    Path(out_dir, "coverage.txt").write_text("\n".join(rows) + "\n")
    Path(out_dir, "coverage.json").write_text(json.dumps(data, indent=1))
    print("\n".join(rows))


if __name__ == "__main__":
    main(*sys.argv[1:4])
