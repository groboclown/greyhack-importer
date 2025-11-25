"""JSON-like structure handlers."""

from collections.abc import Sequence

JsonData = (
    int | str | float | bool | None | Sequence["JsonData"] | dict[str, "JsonData"]
)
DictJsonData = dict[str, JsonData]
ListJsonData = Sequence[JsonData]
