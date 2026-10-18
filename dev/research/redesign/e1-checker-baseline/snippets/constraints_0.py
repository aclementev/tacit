from typing import Annotated
from tacit import Check, Nullable, Schema


class SensorReading(Schema):
    timestamp: str
    device_id: Annotated[str, Check.str_matches(r"^DEV-\d{4}$")]
    temperature: Annotated[float, Check.between(-40, 85)]
    humidity: Annotated[float, Check.ge(0), Check.le(100)]
    status: Annotated[str, Check.isin(["ok", "warn", "error"])]
    error_msg: Annotated[str, Nullable()]
