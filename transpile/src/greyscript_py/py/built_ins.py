"""Built in objects and values."""

import importlib.resources
import json

from . import value_context as vax
from ..ast import basic
from ..util.jdata import JsonData, DictJsonData
from ..util.problems import Problems
from ..util.source import Source


def create_base_context() -> vax.ValueContext:
    """Create the basic context."""
    ret = vax.ValueContext()
    for key, val in load_python_equivalent().contents.items():
        ret.add(_builtin_src(), key, val, Problems())
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
    with data.open("r", encoding="utf-8") as inp:
        ret = json.load(inp)
    if not isinstance(ret, dict):
        raise ValueError("must be dict JSON object")
    return ret


def _load_builtin_object(source: str, raw: JsonData) -> vax.ObjectValue:
    """Load the JSON data as an object value."""
    if not isinstance(raw, dict):
        raise RuntimeError(f"bad format: {source} => {raw}")
    contents: dict[str, vax.ContextItem] = {}
    for key, item in raw.items():
        if key[0] == "$":
            continue
        contents[key] = _load_builtin_item(source, item)
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
            vax.Argument(
                name=arg.get("name", None),
                arg_index=arg.get("index", None),
                default=_load_value(arg.get("default", None)),
            )
        )
    return vax.FuncValue(
        source_name=source,
        value=basic.GSFunctionRef(
            src=_builtin_src(),
            name=source,
        ),
        arguments=params,
    )


def _load_builtin_concat_func(source: str, raw: JsonData) -> vax.ConcatArgCallableValue:
    """Load the JSON data as a callable value."""
    if not isinstance(raw, dict):
        raise RuntimeError("bad format")
    oper = raw.get("operator")
    if not isinstance(oper, str):
        raise RuntimeError("bad format")
    if "name" in raw and isinstance(raw["name"], str):
        source = raw["name"]
    return vax.ConcatArgCallableValue(
        source_name=source,
        value=basic.GSFunctionRef(
            src=_builtin_src(),
            name=source,
        ),
        operator=oper,
    )


def _load_builtin_variable(source: str, raw: JsonData) -> vax.VariableValue:
    """Load the JSON data as a variable value."""
    if not isinstance(raw, dict):
        raise RuntimeError("bad format")
    value_type = raw.get("type")
    if not isinstance(value_type, str | None):
        raise RuntimeError("bad format")
    if "name" in raw and isinstance(raw["name"], str):
        source = raw["name"]
    return vax.VariableValue(
        source_name=source,
        type_name=value_type,
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
    if kind == "variable":
        return _load_builtin_variable(source, raw)
    raise RuntimeError("bad format")


def _load_value(raw: JsonData) -> basic.GSValue:
    src = _builtin_src()
    if raw is None:
        return basic.GSNull(src=src)
    if isinstance(raw, str):
        if raw[0] == "@":
            return basic.GSFunctionRef(src=src, name=raw[1:])
        if raw[0] == "$":
            return basic.GSVariableRef(src=src, name=raw[1:])
        if raw[0] == "#":
            return basic.GSTypeRef(src=src, name=raw[1:])
        if "." in raw:
            r_pos = raw.rindex(".")
            return basic.GSMemberReference(
                src=src,
                value=_load_value(raw[:r_pos]),
                member=raw[r_pos + 1 :],
            )
        return basic.GSConstantString(src=src, value=raw)
    if isinstance(raw, bool):
        return basic.GSConstantNumber(src=src, value=1 if raw else 0)
    if isinstance(raw, int | float):
        return basic.GSConstantNumber(src=src, value=raw)
    if isinstance(raw, list | tuple):
        return basic.GSList(src=src, items=[_load_value(v) for v in raw])
    if isinstance(raw, dict):
        return basic.GSMap(
            src=src,
            items=[
                basic.GSKeyPair(
                    src=src,
                    key=basic.GSConstantString(src=src, value=k),
                    value=_load_value(v),
                )
                for k, v in raw.items()
            ],
        )
    # Not handling GSFunctionDef, GSFunctionCall, GSBinaryOperation, GSUnaryOperation
    raise ValueError(f"unknown value type {raw}")


def _builtin_src() -> Source:
    return Source.new("_built_in_", 0, 0, 0, 0)
