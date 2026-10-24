"""Re-plant the E6/E9 bug classes into the T2 ecommerce port: one bug per file in bugs/.

    uv run --frozen python e17-lean-typing/tools/make_bugs.py

Each planted line gets an `# E: [cat]` marker so tools/run_matrix.py scores it.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "examples" / "ecommerce_t2.py"

# name -> (category, old, new). `old` must occur exactly once.
BUGS: dict[str, tuple[str, str, str]] = {
    # (a) column typos (E6 a1-a3, E9 a)
    "a1_typo_join_view": ("typo-c", "order_count=o.order_id.count(),", "order_count=o.ordr_id.count(),"),
    "a2_typo_namespace": ("typo-c", "net_amount=k.amount - k.discount.fill_null(0)",
                          "net_amount=k.amount - k.discont.fill_null(0)"),
    "a3_typo_table_attr": ("typo-df", "kept = orders.filter(orders.c.status != \"cancelled\")",
                           "kept = orders.filter(orders.statsu != \"cancelled\")"),
    "a4_typo_deferred": ("typo-deferred", "share=_.revenue / _.revenue.sum()", "share=_.revenue / _.revenu.sum()"),
    # (b) wrong frame (E6 b, b2, b3; E9 b)
    "b1_raw_orders_into_step": ("wrong-frame", "stats = country_month_stats(cleaned, customers)",
                                "stats = country_month_stats(orders, customers)"),
    "b2_swapped_args": ("wrong-frame", "stats = country_month_stats(cleaned, customers)",
                        "stats = country_month_stats(customers, cleaned)"),
    "b3_forgot_conform": ("forgot-cast",
                          "return Order.extend(kept, NetAmount.build(net_amount=k.amount - k.discount.fill_null(0)))",
                          "return kept.mutate(net_amount=k.amount - k.discount.fill_null(0))"),
    # (c) forgot a column (E6 c, E9 c)
    "c1_missing_column": ("build-missing", "        avg_net=o.net_amount.mean(),\n", ""),
    # (d) count as float (E6 d, d2; E9 d)
    "d1_count_cast_float": ("int-float", "order_count=o.order_id.count(),", "order_count=o.order_id.count().cast(\"float64\"),"),
    "d2_sum_into_int": ("int-float", "order_count=o.order_id.count(),", "order_count=o.net_amount.sum(),"),
    # (f) nullable misuse (E9 f)
    "f1_nullable_into_nonnull": ("nullable", "net_amount=k.amount - k.discount.fill_null(0)",
                                 "net_amount=k.amount - k.discount"),
}


def main() -> None:
    out = HERE / "bugs"
    out.mkdir(exist_ok=True)
    for f in out.glob("b_*.py"):
        f.unlink()
    text = SRC.read_text()
    for name, (cat, old, new) in BUGS.items():
        assert text.count(old) == 1, (name, text.count(old))
        if new:
            line = next(ln for ln in new.splitlines() if ln.strip())
            src = text.replace(old, new)
            lines = src.splitlines()
            i = next(i for i, ln in enumerate(lines) if line.strip() in ln)
            lines[i] += f"  # E: [{cat}] {name}"
            src = "\n".join(lines) + "\n"
        else:  # deletion: mark the call that is now incomplete
            src = text.replace(old, new)
            src = src.replace("    return CountryMonthStats.build(", f"    return CountryMonthStats.build(  # E: [{cat}] {name}")
        assert f"# E: [{cat}]" in src, name
        (out / f"b_{name}.py").write_text(src)
    print(f"wrote {len(BUGS)} bug files to {out}")


if __name__ == "__main__":
    main()
