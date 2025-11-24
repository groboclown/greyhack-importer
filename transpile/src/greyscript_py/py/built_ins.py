"""Built in objects and values."""

import importlib.resources
import json

from . import value_context as vax
from ..ast import basic
from ..util.jdata import JsonData, DictJsonData
from ..util.source import Source


def create_base_context() -> vax.ValueContext:
    """Create the basic context."""
    ret = vax.ValueContext()
    for key, val in load_python_equivalent().contents.items():
        ret.add(key, val)
    return ret


def load_greyhack_module() -> vax.ObjectValue:
    """Load the built-in context items.

    For Python, this will come in as an import.
    """
    res = _load_from_resource("greyhack.json")
    return _load_builtin_object("greyhack", res)


def load_python_equivalent() -> vax.ObjectValue:
    """Load the built-in context items.

    For Python, this will come in as an import.
    """
    res = _load_from_resource("python.json")
    return _load_builtin_object("greyhack", res)


def _load_from_resource(resource: str) -> DictJsonData:
    data = importlib.resources.files(__name__) / resource
    with data.open("rt", encoding="utf-8") as inp:
        return json.load(inp)


def _load_builtin_object(source: str, raw: JsonData) -> vax.ObjectValue:
    """Load the JSON data as an object value."""
    if not isinstance(raw, dict):
        raise RuntimeError(f"bad format: {source} => {raw}")
    contents: dict[str, vax.ContextItem] = {}
    for key, item in raw.items():
        if key[0] == "$":
            continue
    return vax.ObjectValue(source, contents)


def _load_builtin_func(source: str, raw: JsonData) -> vax.FuncValue:
    """Load the JSON data as a callable value."""
    if not isinstance(raw, dict):
        raise RuntimeError("bad format")
    args = raw.get("args")
    if not isinstance(args, list):
        raise RuntimeError("bad format")
    params: list[vax.Argument] = []
    for arg in args:
        if not isinstance(arg, dict):
            raise RuntimeError("bad format")
        params.append(
            vax.Argument(name=arg.get("name", None), index=arg.get("index", None))
        )
    return vax.FuncValue(
        source_name=source,
        value=basic.GSFunctionRef(
            src=_builtin_src(),
            name=source,
        ),
        arguments=params,
    )


def _load_builtin_concat_func(source, raw: JsonData) -> vax.ConcatArgCallableValue:
    """Load the JSON data as a callable value."""
    if not isinstance(raw, dict):
        raise RuntimeError("bad format")
    oper = raw.get("operator")
    if not isinstance(oper, str):
        raise RuntimeError("bad format")
    return vax.ConcatArgCallableValue(
        source_name=source,
        value=basic.GSFunctionRef(
            src=_builtin_src(),
            name=source,
        ),
        operator=oper,
    )


def _load_builtin_item(source: str, raw: JsonData) -> vax.ContextItem:
    """Load the builtin item, discovering the type."""
    if not isinstance(raw, dict):
        raise RuntimeError("bad format")
    if "$kind" not in raw:
        raise RuntimeError("bad format")
    kind = raw["$kind"]
    if kind == "object":
        return _load_builtin_object(source, raw)
    if kind == "func":
        return _load_builtin_func(source, raw)
    if kind == "concat-func":
        return _load_builtin_concat_func(source, raw)
    raise RuntimeError("bad format")


def _builtin_src() -> Source:
    return Source.new("_built_in_", 0, 0, 0, 0)
