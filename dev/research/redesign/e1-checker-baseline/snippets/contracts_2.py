@tacit.contract(validate=True)
def ingest_iris(raw: tacit.DataFrame[RawIris]) -> tacit.DataFrame[Iris]:
    return raw.mutate(...)
