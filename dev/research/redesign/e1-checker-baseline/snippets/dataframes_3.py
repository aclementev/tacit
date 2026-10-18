def needs_features(df: tacit.DataFrame[IrisFeatures]) -> ...:
    ...

iris = Iris.parse(table)
needs_features(iris)  # type error — DataFrame[Iris] ≠ DataFrame[IrisFeatures]
