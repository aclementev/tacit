from ibis.backends import BaseBackend
from streamlit.connections import BaseConnection
from streamlit.runtime.caching import cache_data
from typing import Any

__all__ = ['IbisConnection']

class IbisConnection(BaseConnection[BaseBackend]):
    def __getattr__(self, name: str) -> Any: ...
    @cache_data
    def list_tables(_self, *args, **kwargs) -> list[str]: ...
