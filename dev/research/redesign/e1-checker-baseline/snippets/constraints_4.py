from tacit import Nullable

class Event(Schema):
    event_type: str                                    # not nullable (default)
    payload: Annotated[str, Nullable()]                # nullable
    priority: Annotated[int, Nullable(allow=False)]    # explicitly not nullable
