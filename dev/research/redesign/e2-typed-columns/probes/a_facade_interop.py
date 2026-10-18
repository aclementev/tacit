"""A4 follow-up: facade columns are ir.*Value statically, not ir.Column. Where does ibis' API reject them?"""

from typing import reveal_type

import ibis

import proto.newtacit as tacit


class Iris(tacit.Frame):
    sepal_length: tacit.Float64
    species: tacit.String


def probe(iris: Iris) -> None:
    t = iris.t
    reveal_type(t.order_by(iris.sepal_length))  # order_by wants str | Column | Deferred
    reveal_type(t.order_by(iris.sepal_length.desc()))
    reveal_type(t.group_by(iris.species).agg(m=iris.sepal_length.mean()))
    reveal_type(t.select(iris.species, x=iris.sepal_length * 2))
    reveal_type(t.mutate(x=iris.sepal_length.round(1)))
    reveal_type(iris.sepal_length.get_name())
    reveal_type(iris.sepal_length.to_pandas())  # Column-only method, not on the facade
    reveal_type(iris.species.isin(["setosa"]))
    reveal_type(ibis.cases((iris.sepal_length > 5.0, "big"), else_="small"))


if __name__ == "__main__":
    iris = Iris.parse(ibis.duckdb.connect().read_csv("../../../../../examples/data/iris.csv").select("sepal_length", "species"))
    probe(iris)
