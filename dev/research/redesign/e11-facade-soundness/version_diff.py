"""Task 4: public column-API diff between ibis versions, and which facade entries each change touches.

python version_diff.py versions/api_10.json versions/api_11.json versions/api_12.0.0.json versions/api_main.json
"""
import json
import sys
from pathlib import Path

from facade_parse import parse

FAMS = {"Integer": "int", "Floating": "float", "Decimal": "Decimal", "String": "str", "Boolean": "bool",
        "Timestamp": "datetime", "Date": "date", "Time": "time", "Interval": None, "Array": None,
        "Struct": None, "Map": None, "JSON": None}
INFRA = {"compile", "execute", "to_pandas", "to_polars", "to_pyarrow", "to_pyarrow_batches", "to_csv", "to_parquet",
         "to_delta", "to_json", "to_torch", "to_list", "to_sql", "visualize", "pipe", "op", "equals", "get_backend",
         "unbind", "has_name", "get_name", "type", "as_table", "as_scalar", "preview", "to_parquet_dir", "to_xlsx",
         "to_pandas_batches"}
E8 = parse(Path(__file__).resolve().parent.parent / "e8-prototype/src/tacit_next/_column.pyi")


def shape(sig: str | None) -> str | None:
    """Parameter names / kinds / defaults only (annotations stripped)."""
    if sig is None:
        return None
    import re
    body = sig.split(") ->")[0]
    body = re.sub(r":\s*('[^']*'|\"[^\"]*\"|[^,=)]*)", "", body)
    return body


def load(p):
    j = json.load(open(p))
    return j["ibis"], j["classes"]


def main(paths):
    vers = [load(p) for p in paths]
    labels = [Path(p).stem.replace("api_", "") for p in paths]
    out = []
    for (va, a), (vb, b), la, lb in zip(vers, vers[1:], labels, labels[1:]):
        out.append(f"===== {la} ({va}) -> {lb} ({vb})")
        tot = {"added": 0, "removed": 0, "sig": 0, "e8": 0}
        names_changed: dict[str, set[str]] = {"added": set(), "removed": set(), "sig": set()}
        for fam, el in FAMS.items():
            for kind in ("Column", "Scalar"):
                cn = f"{fam}{kind}"
                if cn not in a or cn not in b:
                    out.append(f"  {cn}: class {'added' if cn in b else 'removed'}")
                    continue
                ma, mb = a[cn]["members"], b[cn]["members"]
                pub = lambda m: {n for n in m if n not in INFRA}
                added = sorted(pub(mb) - pub(ma))
                removed = sorted(pub(ma) - pub(mb))
                sig = sorted(n for n in pub(ma) & pub(mb) if ma[n]["sig"] != mb[n]["sig"])
                fac = E8[kind]
                touch = sorted(n for n in set(removed) | set(sig)
                               if el is not None and n in fac and any(f == el for f, _ in fac[n]))
                shape_ch = [n for n in sig if shape(ma[n]["sig"]) != shape(mb[n]["sig"])]
                tot.setdefault("shape", 0)
                tot["shape"] += len(shape_ch)
                names_changed.setdefault("shape", set()).update(shape_ch)
                tot["added"] += len(added); tot["removed"] += len(removed); tot["sig"] += len(sig); tot["e8"] += len(touch)
                for k, v in (("added", added), ("removed", removed), ("sig", sig)):
                    names_changed[k] |= set(v)
                if added or removed or sig:
                    out.append(f"  {cn:<17} +{len(added):<3} -{len(removed):<3} ~{len(sig):<3} E8-entries-touched={touch}")
                    if added:
                        out.append(f"      added:   {' '.join(added)}")
                    if removed:
                        out.append(f"      removed: {' '.join(removed)}")
                    for n in sig:
                        tag = "SHAPE" if n in shape_ch else "ann"
                        out.append(f"      {tag} {n}: {ma[n]['sig']}  ->  {mb[n]['sig']}")
        out.append(f"  TOTAL (family-class rows): +{tot['added']} -{tot['removed']} ~{tot['sig']}; "
                   f"distinct names: +{len(names_changed['added'])} -{len(names_changed['removed'])} ~{len(names_changed['sig'])} "
                   f"(of which params/kinds/defaults changed: {sorted(names_changed.get('shape', set()))}); "
                   f"E8 facade (family,method) entries touched by removals/signature changes: {tot['e8']}")
        out.append("")
    text = "\n".join(out)
    Path(Path(__file__).resolve().parent, "out", "version_diff.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
