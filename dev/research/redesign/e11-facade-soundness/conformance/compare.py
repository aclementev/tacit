"""Join static (checker) and runtime (ibis) results; classify every disagreement.

python compare.py STATIC.json RUNTIME.json OUT_PREFIX [checker=pyright]

Categories (severity):
  NULL_LIE      HIGH  declared non-null, executing it yields NULL (tacit constructors don't check nulls)
  KIND_LIE      MED   declared Column vs runtime Scalar (or vice versa / Table)
  FAMILY_LIE    MED   declared element family differs from ibis's dtype family
  ACCEPT_ERROR  MED   statically accepted, ibis raises while building the expression
  ACCEPT_BACKEND MED  statically accepted, ibis builds it but the backend rejects it as a type error
  EMPTY_NULL    LOW   declared non-null reduction is NULL only on empty input (global aggregate)
  WIDER         LOW   declared float, runtime int (int <: float) / declared Any / ibis-typed fallback
  FALSE_POS     LOW   statically rejected, runtime fine
  ok            agreement
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cases import all_cases  # noqa: E402

BACKEND_TYPE_ERR = re.compile(r"Binder Error|Unimplemented type for cast|Unsupported cast|Cannot compare|Cannot mix|"
                              r"Parser Error|No function matches|SignatureValidationError|Not implemented|Could not"
                              r" choose a best candidate")
DATA_ERR = re.compile(r"Could not convert string|invalid timestamp field|Rescaling Decimal|out of range|"
                      r"Conversion Error: .*(?:can't be cast|could not)", re.I)


def parse_decl(t: str | None) -> tuple[str, str | None, bool | None]:
    """'Column[int | None]' -> ('Column', 'int', True); 'Table' -> ('Table', None, None)."""
    if t is None:
        return ("?", None, None)
    m = re.fullmatch(r"(Column|Scalar)\[(.*)\]", t)
    if not m:
        return (t, None, None)
    parts = [p.strip() for p in m.group(2).split("|")]
    nullable = "None" in parts
    el = [p for p in parts if p != "None"]
    fam = el[0] if len(el) == 1 else " | ".join(el)
    fam = fam.rstrip("*")
    if fam.startswith("Literal["):
        fam = {"1": "int", '"': "str"}.get(fam[8], fam)
    return (m.group(1), fam, nullable)


def classify(c, st: dict | None, rt: dict) -> tuple[str, str]:
    rejected = bool(st and st["rejected"])
    rerr = rt.get("error")
    xerr = rt.get("exec_error", "")
    backend_type_err = bool(xerr) and bool(BACKEND_TYPE_ERR.search(xerr)) and rt.get("kind") != "Column" or (
        bool(xerr) and bool(BACKEND_TYPE_ERR.search(xerr)) and "SignatureValidationError" not in xerr)
    if "SignatureValidationError" in xerr:  # asc()/desc(): sort keys can't be projected; not a type error
        backend_type_err = False
    runtime_ok = rerr is None and not backend_type_err
    if rejected:
        return ("ok", "rejected both") if not runtime_ok else ("FALSE_POS", (st["errors"][0] if st else "")[:90])
    if rerr is not None:
        return ("ACCEPT_ERROR", rerr[:110])
    if backend_type_err:
        return ("ACCEPT_BACKEND", xerr[:110])
    kind, fam, nullable = parse_decl(st["reveal"] if st else None)
    rk, rf = rt.get("kind"), rt.get("fam")
    if kind in ("Value", "BooleanValue", "Any", "bool", "str", "?", "Unknown"):
        return ("WIDER", f"declared {kind} (fallback), runtime {rk}[{rf}]")
    if kind != rk:
        return ("KIND_LIE", f"declared {st['reveal']}, runtime {rk}[{rt.get('dtype')}]")
    if kind == "Table":
        return ("ok", "")
    if fam != rf:
        if fam == "Any":
            return ("WIDER", f"declared {st['reveal']}, runtime {rt.get('dtype')}")
        if fam == "float" and rf == "int":
            return ("WIDER", f"declared {st['reveal']}, runtime {rt.get('dtype')}")
        return ("FAMILY_LIE", f"declared {st['reveal']}, runtime {rt.get('dtype')}")
    if nullable is False and rt.get("nulls"):
        return ("NULL_LIE", f"declared {st['reveal']}, {rt['nulls']} NULL(s) at runtime")
    if nullable is False and rt.get("empty_null") and not (c.container == "Scalar" and not c.nullable):
        # (a non-null Scalar receiver is itself a reduction, NULL on empty input: harness artifact)
        return ("EMPTY_NULL", f"declared {st['reveal']}, NULL on empty input")
    return ("ok", "")


def main(static_path: str, runtime_path: str, prefix: str, checker: str = "pyright") -> None:
    static = json.load(open(static_path))
    rtj = json.load(open(runtime_path))
    runtime = rtj["cases"]
    cases = all_cases()
    rows = []
    for c in cases:
        cat, detail = classify(c, static[checker].get(c.id), runtime[c.id])
        rows.append((c, cat, detail))
    counts = Counter(cat for _, cat, _ in rows)
    # ibis dtype-nullability agreement (informational: ibis marks most results nullable)
    nn_agree = Counter()
    for c, cat, _ in rows:
        st, rt = static[checker].get(c.id), runtime[c.id]
        if cat == "ok" and st and not st["rejected"] and "dtype_nullable" in rt:
            k, f, n = parse_decl(st["reveal"])
            if n is not None:
                nn_agree[(n, rt["dtype_nullable"])] += 1
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for c, cat, detail in rows:
        if cat == "ok":
            continue
        detail_g = re.sub(r"\d+ NULL", "N NULL", detail)
        if cat in ("ACCEPT_ERROR", "ACCEPT_BACKEND", "FALSE_POS"):
            detail_g = re.sub(r"(Max\()?\b(c|n|d|dn)_\w+\)?", "<col>", detail_g)
            detail_g = re.sub(r"Literal\([^)]*\)", "<lit>", detail_g)
            detail_g = re.sub(r"!?\b(u?int\d+|float\d+|boolean|string|timestamp(\(\d\))?|date|time|decimal(\(\d+, \d+\))?)\b", "<T>", detail_g)
            detail_g = re.sub(r"\b(BOOLEAN|BIGINT|DOUBLE|DECIMAL\(\d+,\d+\)|VARCHAR|TIMESTAMP|DATE|TIME_NS|TIME|INTERVAL)\b", "<T>", detail_g)
            detail_g = re.sub(r'"[A-Za-z_]+\[[^"]*\]"', '"<F>"', detail_g)
            detail_g = re.sub(r"'?\b(Boolean|Integer|Floating|Decimal|String|Timestamp|Date|Time)(Column|Scalar)'?", r"<F>\2", detail_g)
            detail_g = re.sub(r"\(12, 2\)", "", detail_g)
            detail_g = detail_g[:80]
        groups[(cat, c.template, detail_g)].append(f"{c.container[0]}:{c.fam}{'?' if c.nullable else ''}")
    lines = [f"checker={checker} ibis={rtj['ibis']} cases={len(rows)}", "",
             "category counts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), "",
             "declared-nullable vs ibis dtype.nullable on agreeing cases (declared, ibis): "
             + ", ".join(f"{k}={v}" for k, v in sorted(nn_agree.items())), ""]
    order = ["NULL_LIE", "KIND_LIE", "FAMILY_LIE", "ACCEPT_ERROR", "ACCEPT_BACKEND", "EMPTY_NULL", "WIDER", "FALSE_POS"]
    for cat in order:
        gs = [(k, v) for k, v in groups.items() if k[0] == cat]
        lines.append(f"===== {cat}: {sum(len(v) for _, v in gs)} cases in {len(gs)} groups")
        for (c_, tpl, detail), who in sorted(gs, key=lambda kv: kv[0][1]):
            lines.append(f"  {tpl:<28} [{' '.join(who)}]  {detail}")
        lines.append("")
    Path(prefix + ".txt").write_text("\n".join(lines))
    Path(prefix + ".json").write_text(json.dumps(
        [{"id": c.id, "tpl": c.template, "fam": c.fam, "nullable": c.nullable, "container": c.container,
          "cat": cat, "detail": d} for c, cat, d in rows], indent=0))
    print("\n".join(lines[:6]))


if __name__ == "__main__":
    main(*sys.argv[1:])
