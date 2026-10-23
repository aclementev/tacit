from ibis.formats.pandas import PandasData as PandasData

class SQLitePandasData(PandasData):
    @classmethod
    def convert_Timestamp(cls, s, dtype, pandas_type): ...
