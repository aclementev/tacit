"""Operation-level capability probe: each case in narwhals (v2) and, side by side, in ibis.

The reference is narwhals on eager polars. Every other backend's result is compared with it
(order-insensitive, floats rounded). usage:
    uv run python cap/ops.py nw <backend...>      # narwhals cases on narwhals backends
    uv run python cap/ops.py ibis <ibis-backend...>  # ibis cases on ibis backends
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

import ibis  # noqa: E402
import narwhals as nwm  # noqa: E402  (main, unstable namespace)
import narwhals.stable.v2 as nw  # noqa: E402
import narwhals.stable.v2.selectors as ncs  # noqa: E402
import polars as pl  # noqa: E402
from ibis import _  # noqa: E402

from common import collect_polars, example_frames, same, to_native  # noqa: E402

O = "orders"
C = "customers"
col = nw.col
Case = tuple[str, str, Callable[[dict[str, Any]], Any], Callable[[dict[str, Any]], Any] | None]
#            name, group, narwhals(frames)->frame, ibis(tables)->table


def _o(f: dict[str, Any]) -> Any:
    return f[O]


CASES: list[Case] = [
    # ---- windows
    ("rank_ordinal_over", "window",
     lambda f: _o(f).select("order_id", r=col("order_ts").rank("ordinal", descending=True).over("customer_id")),
     lambda t: t[O].select("order_id", r=ibis.row_number().over(group_by="customer_id", order_by=ibis.desc("order_ts")) + 1)),
    ("rank_dense_over", "window",
     lambda f: _o(f).select("order_id", r=col("amount").rank("dense", descending=True).over("customer_id")),
     lambda t: t[O].select("order_id", r=ibis.dense_rank().over(group_by="customer_id", order_by=ibis.desc("amount")) + 1)),
    ("rank_min_global", "window",
     lambda f: _o(f).select("order_id", r=col("amount").rank("min")),
     lambda t: t[O].select("order_id", r=ibis.rank().over(order_by="amount") + 1)),
    ("cum_sum_over_ordered", "window",
     lambda f: _o(f).select("order_id", s=col("amount").cum_sum().over("customer_id", order_by="order_ts")),
     lambda t: t[O].select("order_id", s=_.amount.cumsum(group_by="customer_id", order_by="order_ts"))),
    ("lag_over_ordered", "window",
     lambda f: _o(f).select("order_id", p=col("amount").shift(1).over("customer_id", order_by="order_ts")),
     lambda t: t[O].select("order_id", p=_.amount.lag().over(group_by="customer_id", order_by="order_ts"))),
    ("diff_over_ordered", "window",
     lambda f: _o(f).select("order_id", d=col("amount").diff().over("customer_id", order_by="order_ts")),
     lambda t: t[O].select("order_id", d=(_.amount - _.amount.lag()).over(group_by="customer_id", order_by="order_ts"))),
    ("rolling_mean_ordered", "window",
     lambda f: _o(f).select("order_id", m=col("amount").rolling_mean(window_size=3, min_samples=1).over(order_by="order_id")),
     lambda t: t[O].select("order_id", m=_.amount.mean().over(ibis.window(order_by="order_id", preceding=2, following=0)))),
    ("share_of_partition", "window",
     lambda f: _o(f).select("order_id", s=col("amount") / col("amount").sum().over("customer_id")),
     lambda t: t[O].select("order_id", s=_.amount / _.amount.sum().over(group_by="customer_id"))),
    ("row_index_ordered", "window",
     lambda f: _o(f).with_row_index("idx", order_by="order_ts").select("order_id", "idx"),
     lambda t: t[O].select("order_id", idx=ibis.row_number().over(order_by="order_ts"))),
    ("fill_null_forward_ordered", "window",
     lambda f: _o(f).select("order_id", d=col("discount").fill_null(strategy="forward").over(order_by="order_id")),
     lambda t: t[O].select("order_id", d=_.discount.last(include_null=False).over(ibis.window(order_by="order_id", preceding=None, following=0)))),
    ("is_first_distinct_ordered", "window",
     lambda f: _o(f).select("order_id", x=col("customer_id").is_first_distinct().over(order_by="order_ts")),
     None),
    # ---- dates
    ("dt_truncate_month", "date",
     lambda f: _o(f).select("order_id", m=col("order_ts").dt.truncate("1mo")),
     lambda t: t[O].select("order_id", m=_.order_ts.truncate("M"))),
    ("dt_truncate_week", "date",
     lambda f: _o(f).select("order_id", m=col("order_ts").dt.truncate("1w")),
     lambda t: t[O].select("order_id", m=_.order_ts.truncate("W"))),
    ("dt_truncate_hour", "date",
     lambda f: _o(f).select("order_id", m=col("order_ts").dt.truncate("1h")),
     lambda t: t[O].select("order_id", m=_.order_ts.truncate("h"))),
    ("dt_parts", "date",
     lambda f: _o(f).select("order_id", y=col("order_ts").dt.year(), mo=col("order_ts").dt.month(), wd=col("order_ts").dt.weekday(), h=col("order_ts").dt.hour()),
     lambda t: t[O].select("order_id", y=_.order_ts.year(), mo=_.order_ts.month(), wd=_.order_ts.day_of_week.index() + 1, h=_.order_ts.hour())),
    ("dt_date", "date",
     lambda f: _o(f).select("order_id", d=col("order_ts").dt.date()),
     lambda t: t[O].select("order_id", d=_.order_ts.date())),
    ("dt_diff_days", "date",
     lambda f: _o(f).select("order_id", d=((col("order_ts") - datetime(2024, 1, 1)).dt.total_seconds() // 86400).cast(nw.Int64)),
     lambda t: t[O].select("order_id", d=(_.order_ts.epoch_seconds() - ibis.timestamp(datetime(2024, 1, 1)).epoch_seconds()) // 86400)),
    ("dt_offset_by", "date",
     lambda f: _o(f).select("order_id", d=col("order_ts").dt.offset_by("1mo")),
     lambda t: t[O].select("order_id", d=_.order_ts + ibis.interval(months=1))),
    ("str_to_datetime", "date",
     lambda f: _o(f).select("order_id", d=col("order_ts").dt.to_string("%Y-%m-%d").str.to_datetime("%Y-%m-%d")),
     lambda t: t[O].select("order_id", d=_.order_ts.strftime("%Y-%m-%d").as_timestamp("%Y-%m-%d"))),
    ("date_filter_literal", "date",
     lambda f: _o(f).filter(col("order_ts") >= datetime(2024, 3, 1)).select("order_id"),
     lambda t: t[O].filter(_.order_ts >= datetime(2024, 3, 1)).select("order_id")),
    # ---- strings
    ("str_upper_lower", "string",
     lambda f: f[C].select("customer_id", u=col("name").str.to_uppercase(), l=col("email").str.to_lowercase()),
     lambda t: t[C].select("customer_id", u=_.name.upper(), l=_.email.lower())),
    ("str_contains_regex", "string",
     lambda f: f[C].select("customer_id", m=col("email").str.contains(r"^[a-z]+\d+@")),
     lambda t: t[C].select("customer_id", m=_.email.re_search(r"^[a-z]+\d+@"))),
    ("str_contains_literal", "string",
     lambda f: f[C].select("customer_id", m=col("email").str.contains(".", literal=True)),
     lambda t: t[C].select("customer_id", m=_.email.contains("."))),
    ("str_replace_all_regex", "string",
     lambda f: f[C].select("customer_id", r=col("email").str.replace_all(r"\d", "#")),
     lambda t: t[C].select("customer_id", r=_.email.re_replace(r"\d", "#"))),
    ("str_slice", "string",
     lambda f: f[C].select("customer_id", s=col("email").str.slice(0, 3)),
     lambda t: t[C].select("customer_id", s=_.email.substr(0, 3))),
    ("str_starts_ends", "string",
     lambda f: f[C].select("customer_id", a=col("name").str.starts_with("A"), b=col("email").str.ends_with(".com")),
     lambda t: t[C].select("customer_id", a=_.name.startswith("A"), b=_.email.endswith(".com"))),
    ("str_len_chars", "string",
     lambda f: f[C].select("customer_id", n=col("name").str.len_chars()),
     lambda t: t[C].select("customer_id", n=_.name.length())),
    ("str_strip_pad", "string",
     lambda f: f[C].select("customer_id", s=nw.concat_str(nw.lit("  "), col("country")).str.strip_chars(), p=col("country").str.zfill(4)),
     lambda t: t[C].select("customer_id", s=_.country.lpad(4, " ").strip(), p=_.country.lpad(4, "0"))),
    ("concat_str_sep", "string",
     lambda f: f[C].select("customer_id", s=nw.concat_str(col("name"), col("country"), separator="/")),
     lambda t: t[C].select("customer_id", s=_.name.concat("/", _.country))),
    ("str_split_list_len", "string",
     lambda f: f[C].select("customer_id", n=col("name").str.split(" ").list.len()),
     lambda t: t[C].select("customer_id", n=_.name.split(" ").length())),
    ("str_to_date", "string",
     lambda f: f[C].select("customer_id", d=col("signup_date").cast(nw.String).str.to_date("%Y-%m-%d")),
     lambda t: t[C].select("customer_id", d=_.signup_date.cast("string").as_date("%Y-%m-%d"))),
    # ---- conditionals / nulls
    ("when_then_otherwise", "cond",
     lambda f: _o(f).select("order_id", b=nw.when(col("amount") > 100).then(nw.lit("big")).when(col("amount") > 30).then(nw.lit("mid")).otherwise(nw.lit("small"))),
     lambda t: t[O].select("order_id", b=ibis.cases((_.amount > 100, "big"), (_.amount > 30, "mid"), else_="small"))),
    ("when_no_otherwise", "cond",
     lambda f: _o(f).select("order_id", b=nw.when(col("amount") > 100).then(col("amount"))),
     lambda t: t[O].select("order_id", b=ibis.cases((_.amount > 100, _.amount)))),
    ("coalesce", "cond",
     lambda f: _o(f).select("order_id", c=nw.coalesce(col("discount"), col("amount") * 0.1)),
     lambda t: t[O].select("order_id", c=ibis.coalesce(_.discount, _.amount * 0.1))),
    ("fill_null_value", "cond",
     lambda f: _o(f).select("order_id", c=col("discount").fill_null(0)),
     lambda t: t[O].select("order_id", c=_.discount.fill_null(0))),
    ("is_in", "cond",
     lambda f: _o(f).select("order_id", c=col("status").is_in(["shipped", "pending"])),
     lambda t: t[O].select("order_id", c=_.status.isin(["shipped", "pending"]))),
    ("is_between", "cond",
     lambda f: _o(f).select("order_id", c=col("amount").is_between(10, 50)),
     lambda t: t[O].select("order_id", c=_.amount.between(10, 50))),
    ("null_count_and_is_null", "cond",
     lambda f: _o(f).select(n=col("discount").is_null().cast(nw.Int64).sum(), m=col("discount").null_count()),
     lambda t: t[O].aggregate(n=_.discount.isnull().cast("int64").sum(), m=_.discount.isnull().cast("int64").sum())),
    ("bool_sum", "cond",
     lambda f: _o(f).select(n=(col("amount") > 50).sum()),
     lambda t: t[O].aggregate(n=(_.amount > 50).sum())),
    ("bool_any_all", "cond",
     lambda f: _o(f).select(a=(col("amount") > 50).any(), b=(col("amount") > 0).all()),
     lambda t: t[O].aggregate(a=(_.amount > 50).any(), b=(_.amount > 0).all())),
    # ---- numerics / casts
    ("cast_round_clip_abs", "numeric",
     lambda f: _o(f).select("order_id", a=col("amount").round(0).cast(nw.Int64), b=col("amount").clip(10, 50), c=(col("amount") - 50).abs()),
     lambda t: t[O].select("order_id", a=_.amount.round(0).cast("int64"), b=_.amount.clip(10, 50), c=(_.amount - 50).abs())),
    ("cast_int_to_str", "numeric",
     lambda f: _o(f).select("order_id", s=col("order_id").cast(nw.String)),
     lambda t: t[O].select("order_id", s=_.order_id.cast("string"))),
    ("horizontal_ops", "numeric",
     lambda f: _o(f).select("order_id", s=nw.sum_horizontal("amount", "discount"), m=nw.max_horizontal("amount", "discount"), a=nw.any_horizontal(col("amount") > 90, col("discount") > 9, ignore_nulls=True)),
     None),
    ("selectors_numeric", "numeric",
     lambda f: _o(f).select(ncs.numeric()),
     lambda t: t[O].select(ibis.selectors.numeric())),
    # ---- aggregation
    ("agg_basic", "agg",
     lambda f: _o(f).group_by("status").agg(n=nw.len(), s=col("amount").sum(), mi=col("amount").min(), ma=col("amount").max()),
     lambda t: t[O].group_by("status").aggregate(n=_.count(), s=_.amount.sum(), mi=_.amount.min(), ma=_.amount.max())),
    ("agg_stats", "agg",
     lambda f: _o(f).group_by("status").agg(md=col("amount").median(), sd=col("amount").std(), v=col("amount").var(), q=col("amount").quantile(0.5, "linear")),
     lambda t: t[O].group_by("status").aggregate(md=_.amount.median(), sd=_.amount.std(), v=_.amount.var(), q=_.amount.quantile(0.5))),
    ("agg_n_unique_with_nulls", "agg",
     lambda f: _o(f).group_by("status").agg(n=col("discount").n_unique()),
     lambda t: t[O].group_by("status").aggregate(n=_.discount.nunique() + _.discount.isnull().any().cast("int64"))),
    ("agg_filtered", "agg",
     lambda f: _o(f).group_by("customer_id").agg(s=col("amount").filter(col("status") == "shipped").sum()),
     lambda t: t[O].group_by("customer_id").aggregate(s=_.amount.sum(where=_.status == "shipped").fill_null(0))),
    ("agg_expr_key", "agg",
     lambda f: _o(f).group_by(col("order_ts").dt.month().alias("m")).agg(n=nw.len()),
     lambda t: t[O].group_by(m=_.order_ts.month()).aggregate(n=_.count())),
    ("agg_drop_null_keys", "agg",
     lambda f: _o(f).group_by("discount", drop_null_keys=True).agg(n=nw.len()),
     lambda t: t[O].filter(_.discount.notnull()).group_by("discount").aggregate(n=_.count())),
    ("agg_first_v2_unordered", "agg",
     lambda f: _o(f).sort("order_ts").group_by("customer_id").agg(x=col("amount").first()),
     lambda t: t[O].group_by("customer_id").aggregate(x=_.amount.first(order_by="order_ts"))),
    ("agg_first_ordered_main_ns", "agg",
     lambda f: nwm.from_native(nw.to_native(_o(f))).group_by("customer_id").agg(x=nwm.col("amount").first(order_by="order_ts")),
     lambda t: t[O].group_by("customer_id").aggregate(x=_.amount.first(order_by="order_ts"))),
    ("agg_global_broadcast", "agg",
     lambda f: _o(f).select("order_id", d=col("amount") - col("amount").mean()),
     lambda t: t[O].select("order_id", d=_.amount - _.amount.mean())),
    # ---- relational
    ("join_left", "relational",
     lambda f: _o(f).join(f[C], on="customer_id", how="left").select("order_id", "country"),
     lambda t: t[O].left_join(t[C], "customer_id").select("order_id", "country")),
    ("join_full", "relational",
     lambda f: _o(f).filter(col("customer_id") < 5).join(f[C].filter(col("customer_id") > 2), on="customer_id", how="full", suffix="_r").select("order_id", "country"),
     lambda t: t[O].filter(_.customer_id < 5).outer_join(t[C].filter(_.customer_id > 2), "customer_id").select("order_id", "country")),
    ("join_semi_anti", "relational",
     lambda f: f[C].join(_o(f).filter(col("amount") > 90), on="customer_id", how="anti").select("customer_id"),
     lambda t: t[C].anti_join(t[O].filter(_.amount > 90), "customer_id").select("customer_id")),
    ("join_left_on_right_on", "relational",
     lambda f: _o(f).join(f[C].rename({"customer_id": "cid"}), left_on="customer_id", right_on="cid").select("order_id", "country"),
     lambda t: (lambda r: t[O].join(r, t[O].customer_id == r.cid))(t[C].rename(cid="customer_id")).select("order_id", "country")),
    ("join_cross", "relational",
     lambda f: f[C].head(3).join(f[C].head(2).select(c2="country"), how="cross").select("customer_id", "c2"),
     lambda t: t[C].order_by("customer_id").limit(3).cross_join(t[C].order_by("customer_id").limit(2).select(c2="country")).select("customer_id", "c2")),
    ("join_asof", "relational",
     lambda f: _o(f).sort("order_ts").join_asof(_o(f).select(t2="order_ts", prev_id="order_id").sort("t2"), left_on="order_ts", right_on="t2", strategy="backward").select("order_id", "prev_id"),
     None),
    ("concat_vertical", "relational",
     lambda f: nw.concat([_o(f).select("order_id"), _o(f).select("order_id")]),
     lambda t: ibis.union(t[O].select("order_id"), t[O].select("order_id"), distinct=False)),
    ("unique_subset", "relational",
     lambda f: _o(f).unique(subset=["customer_id"], keep="any").select("customer_id"),
     lambda t: t[O].distinct(on="customer_id", keep="first").select("customer_id")),
    ("unique_keep_first_ordered", "relational",
     lambda f: _o(f).unique(subset=["customer_id"], keep="first", order_by=["order_ts"]).select("customer_id", "order_id"),
     None),
    ("sort_head", "relational",
     lambda f: _o(f).sort("amount", descending=True, nulls_last=True).head(5).select("order_id"),
     lambda t: t[O].order_by(ibis.desc("amount")).limit(5).select("order_id")),
    ("top_k", "relational",
     lambda f: _o(f).top_k(3, by="amount").select("order_id"),
     lambda t: t[O].order_by(ibis.desc("amount")).limit(3).select("order_id")),
    ("unpivot", "reshape",
     lambda f: _o(f).unpivot(["amount", "discount"], index="order_id"),
     lambda t: t[O].pivot_longer(ibis.selectors.cols("amount", "discount"), names_to="variable", values_to="value").select("order_id", "variable", "value")),
    ("explode", "reshape",
     lambda f: f[C].with_columns(p=col("name").str.split(" ")).explode("p").select("customer_id", "p"),
     lambda t: t[C].mutate(p=_.name.split(" ")).unnest("p").select("customer_id", "p")),
    ("pivot", "reshape",
     lambda f: _o(f).pivot("status", index="customer_id", values="amount", aggregate_function="sum"),
     lambda t: t[O].pivot_wider(id_cols="customer_id", names_from="status", values_from="amount", values_agg="sum")),
    ("drop_nulls_subset", "relational",
     lambda f: _o(f).drop_nulls(subset=["discount"]).select("order_id"),
     lambda t: t[O].drop_null("discount").select("order_id")),
    ("is_duplicated_expr", "relational",
     lambda f: _o(f).select("order_id", d=col("customer_id").is_duplicated()),
     lambda t: t[O].select("order_id", d=_.customer_id.count().over(group_by="customer_id") > 1)),
    # ---- schema / misc
    ("collect_schema", "schema",
     lambda f: nw.from_dict({"n": [len(_o(f).collect_schema())]}, backend="polars"),
     lambda t: ibis.memtable({"n": [len(t[O].schema())]})),
    ("cast_schema_dtypes", "schema",
     lambda f: _o(f).select(col("order_id").cast(nw.Int32), col("amount").cast(nw.Float32), col("order_ts").cast(nw.Date)),
     lambda t: t[O].select(_.order_id.cast("int32").name("order_id"), _.amount.cast("float32").name("amount"), _.order_ts.cast("date").name("order_ts"))),
    ("map_batches_udf", "udf",
     lambda f: _o(f).select("order_id", x=col("amount").map_batches(lambda s: s * 2, return_dtype=nw.Float64)),
     None),
]


NW_BACKENDS_ = ["polars-eager", "polars-lazy", "duckdb", "pyspark", "sqlframe-duckdb", "ibis-duckdb"]


def classify(e: Exception) -> str:
    msg = str(e).strip().splitlines()[0][:150] if str(e).strip() else ""
    kind = "UNSUP" if isinstance(e, NotImplementedError) or "not supported" in msg.lower() or "not implemented" in msg.lower() else "ERROR"
    return f"{kind} {type(e).__name__}: {msg}"


def run_nw(backend: str, ref: dict[str, pl.DataFrame] | None) -> dict[str, str]:
    fr = example_frames()
    f = {k: nw.from_native(to_native(backend, k, v)) for k, v in fr.items() if k in (O, C)}
    out: dict[str, str] = {}
    for name, _g, fn, _i in CASES:
        if ref is not None and isinstance(ref[name], str) and backend == "polars-eager":
            out[name] = ref[name]
            continue
        try:
            got = collect_polars(fn(f))
        except Exception as e:  # noqa: BLE001
            out[name] = classify(e)
            if backend == "sqlframe-postgres":  # a failed statement aborts the transaction
                from common import sqlframe_session

                sqlframe_session("postgres")._conn.rollback()
            continue
        if ref is None or isinstance(ref[name], str):
            out[name] = "OK (no polars reference)"
            continue
        ok, why = same(ref[name], got)
        out[name] = "OK" if ok else f"DIFF {why}"
    return out


def run_ibis(backend: str, ref: dict[str, pl.DataFrame]) -> dict[str, str]:
    fr = example_frames()
    t = {k: to_native(backend, k, v) for k, v in fr.items() if k in (O, C)}
    out: dict[str, str] = {}
    for name, _g, _fn, ifn in CASES:
        if ifn is None:
            out[name] = "n/a (no direct ibis spelling)"
            continue
        if isinstance(ref[name], str):
            ref_name = None
        else:
            ref_name = ref[name]
        try:
            got = pl.from_arrow(ifn(t).to_pyarrow())
            if ref_name is None:
                out[name] = "OK (no polars reference)"
                continue
        except Exception as e:  # noqa: BLE001
            out[name] = classify(e)
            continue
        ok, why = same(ref[name], got)  # type: ignore[arg-type]
        out[name] = "OK" if ok else f"DIFF {why}"
    return out


def reference() -> dict[str, pl.DataFrame]:
    fr = example_frames()
    f = {k: nw.from_native(v) for k, v in fr.items() if k in (O, C)}
    ref: dict[str, Any] = {}
    for name, _g, fn, _i in CASES:
        try:
            ref[name] = collect_polars(fn(f))
        except Exception as e:  # noqa: BLE001
            ref[name] = classify(e)  # narwhals itself rejects the op (even on polars)
    return ref


if __name__ == "__main__":
    mode, backends = sys.argv[1], sys.argv[2:]
    ref = reference()
    res = {}
    for b in backends:
        res[b] = run_ibis(b, ref) if mode == "ibis" else run_nw(b, ref)
        bad = {k: v for k, v in res[b].items() if v != "OK"}
        print(f"== {mode}:{b}  ok {len(res[b]) - len(bad)}/{len(res[b])}")
        for k, v in bad.items():
            print(f"   {k:28s} {v[:230]}")
        sys.stdout.flush()
    out = HERE.parent / "out" / f"ops_{mode}_{'_'.join(backends)}.json"
    out.write_text(json.dumps(res, indent=1))
    _ = (date, os)
