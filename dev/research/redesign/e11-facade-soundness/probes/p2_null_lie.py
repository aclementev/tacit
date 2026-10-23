# ruff: noqa
"""Does a NULL_LIE reach a frame silently? (type-checks clean on all 4; runtime shows NULLs)"""
import ibis
import tacit_next as tc
from tacit_next import Column


class O(tc.Frame):
    k: Column[str]
    amount: Column[float]
    discount: Column[float | None]


class Flags(tc.Frame):
    k: Column[str]
    has_discount: Column[bool]          # declared NOT NULL
    disc_f: Column[float]               # declared NOT NULL


class Stats(tc.Frame):
    k: Column[str]
    max_disc: Column[float]             # declared NOT NULL
    sd_amount: Column[float]            # declared NOT NULL


def flags(o: O) -> Flags:
    return Flags(k=o.k, has_discount=o.discount > 0, disc_f=o.discount.cast("float64"))  # L1 nullable comparison + cast into NOT NULL


def stats(o: O) -> Stats:
    return Stats(k=o.k, max_disc=o.discount.max(), sd_amount=o.amount.std())  # L2 all-NULL group max + 1-row std into NOT NULL


if __name__ == "__main__":
    raw = ibis.memtable({"k": ["a", "a", "b"], "amount": [1.0, 2.0, 3.0], "discount": [0.5, None, None]},
                        schema={"k": "!string", "amount": "!float64", "discount": "float64"})
    o = O.parse(raw)
    f = flags(o)
    print(f.to_pyarrow())
    s = stats(o)
    print(s.to_pyarrow())
    try:
        Flags.parse(f.ibis); print("Flags.parse: accepted")
    except tc.ValidationError as e:
        print("Flags.parse caught it:", e)
