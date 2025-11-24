"""Maintains value context within the Python visitors."""

from typing import NamedTuple, Sequence

from greyscript_py.ast import basic
from greyscript_py.util.problems import Problems
from greyscript_py.util.source import Source


class ContextItem:
    """A value maintained within a context."""

    def __init__(self, source_name: str | None) -> None:
        self.source_name = source_name


class Argument(NamedTuple):
    """Callable argument.

    The name and index relate to the Python version of the argument.  The location
    within the owning array indicates the GS position.
    """

    name: str | None
    index: int | None
    default: basic.GSValue | None


class CallableValue(ContextItem):
    """A kind of value that can be called."""

    def as_invocation(
        self,
        source: Source,
        position_arguments: list[basic.GSValue],
        named_arguments: dict[str, basic.GSValue],
    ) -> tuple[basic.GSFunctionCall | None, Problems]:
        """Construct the invocation."""
        raise NotImplementedError


class FuncValue(CallableValue):
    """A kind of value that can be called.

    Allows for positional and named arguments.
    """

    def __init__(
        self,
        source_name: str,
        value: basic.GSCallableValue,
        arguments: list[Argument],
    ) -> None:
        ContextItem.__init__(self, source_name)
        self.value = value
        self.arguments = arguments

    def as_invocation(
        self,
        source: Source,
        position_arguments: list[basic.GSValue],
        named_arguments: dict[str, basic.GSValue],
    ) -> tuple[basic.GSFunctionCall, Problems]:
        """Construct the invocation."""
        params: list[basic.GSValue] = []
        problems = Problems()
        for pos in range(len(self.arguments)):
            arg = self.arguments[pos]
            if arg.index is not None:
                if 0 <= arg.index < len(position_arguments):
                    params.append(position_arguments[arg.index])
                else:
                    problems.add_err(
                        source,
                        "USAGE-bad-call-position-arg",
                        func=self.source_name,
                        index=arg.index,
                    )
            elif arg.name is not None:
                if arg.name in named_arguments:
                    params.append(named_arguments[arg.name])
                else:
                    problems.add_err(
                        source,
                        "USAGE-bad-call-named-arg",
                        func=self.source_name,
                        key=arg.name,
                    )
            elif pos < len(position_arguments):
                params.append(position_arguments[pos])
            else:
                problems.add_err(
                    source,
                    "USAGE-bad-call-position-arg",
                    func=self.source_name,
                    index=pos,
                )
        return (
            basic.GSFunctionCall(
                src=source,
                func=self.value,
                parameters=params,
            ),
            problems,
        )


class ConcatArgCallableValue(CallableValue):
    """Callable where the arguments are concatenated together."""

    def __init__(
        self,
        source_name: str,
        value: basic.GSCallableValue,
        operator: str,
    ) -> None:
        ContextItem.__init__(self, source_name)
        self.value = value
        self.operator = operator

    def as_invocation(
        self,
        source: Source,
        position_arguments: list[basic.GSValue],
        named_arguments: dict[str, basic.GSValue],
    ) -> tuple[basic.GSFunctionCall, Problems]:
        """Construct the invocation."""
        problems = Problems()
        if named_arguments:
            problems.add_err(
                source,
                "USAGE-bad-call-named-arg",
                func=self.source_name,
                key=list(named_arguments.keys())[0],
            )
        args: list[basic.GSValue] = []
        if position_arguments:
            first = position_arguments[0]
            for second in position_arguments[1:]:
                combined = basic.GSBinaryOperation(
                    src=first.src,
                    operator=self.operator,
                    left=first,
                    right=second,
                )
                first = combined
            args.append(first)
        return (
            basic.GSFunctionCall(
                src=source,
                func=self.value,
                parameters=args,
            ),
            problems,
        )


class VariableValue(ContextItem):
    """A variable which can be assigned to a value."""

    def __init__(self, source_name: str, type_name: str | None) -> None:
        ContextItem.__init__(self, source_name)
        self.type_name = type_name


class ObjectValue(ContextItem):
    """A value which contains string-indexed values."""

    def __init__(
        self, source_name: str | None, contents: dict[str, ContextItem]
    ) -> None:
        ContextItem.__init__(self, source_name)
        self.contents = contents


class ValueContext:
    """Container for maintaining the values within the current context.

    Allows for proper invocation execution and translation.  This allows
    for importing "as", and for understanding which value is addressed.
    """

    def __init__(self) -> None:
        self._values: dict[str, ContextItem] = {}

    def add(
        self, src: Source, named_as: str, value: ContextItem, problems: Problems
    ) -> None:
        """Mark a value in the context."""
        existing = self._values.get(value.source_name)
        if existing is not None:
            if not isinstance(existing, value.__class__):
                problems.add_warn(
                    src,
                    "WARN-changed-value-cat",
                    existing=existing.__class__.__name__,
                    new=value.__class__.__name__,
                )
            elif (
                isinstance(existing, VariableValue)
                and isinstance(value, VariableValue)
                and existing.type_name != value.type_name
            ):
                problems.add_warn(
                    src,
                    "WARN-changed-value-type",
                    existing=existing.type_name,
                    new=value.type_name,
                )
        self._values[named_as] = value

    def get_named(
        self, named: basic.GSVariableRef | basic.GSFunctionRef, problems: Problems
    ) -> ContextItem | None:
        """Get the context item using the named value."""
        return self.get((named.name,), problems)

    def get_member(
        self, ref: basic.GSMemberReference, problems: Problems
    ) -> ContextItem | None:
        """Get the member."""
        named_path: list[str] = [ref.member]
        parent: basic.GSValue | None = ref.value
        while parent is not None:
            if isinstance(parent, basic.GSVariableRef | basic.GSFunctionRef):
                named_path.insert(0, parent.name)
                parent = None
            elif isinstance(parent, basic.GSMemberReference):
                named_path.insert(0, parent.member)
                parent = parent.value
            else:
                # Don't know how to look this up.
                return None
        return self.get(named_path, problems)

    def get(self, name_path: Sequence[str], problems: Problems) -> ContextItem | None:
        """Find the item in the path of names."""
        ret, probs = get(self._values, name_path)
        problems.add_from(probs)
        return ret

    def enter(self) -> "ValueContext":
        """Enter a child context."""
        ret = ValueContext()
        ret._values = dict(self._values)
        return ret


def get(
    base: dict[str, ContextItem], name_path: Sequence[str]
) -> tuple[ContextItem | None, Problems]:
    """Find the item in the path of names."""
    ctx: ContextItem | None = ObjectValue(
        source_name="",
        contents=base,
    )
    problems = Problems()
    bad_path: list[str] = []
    for name in name_path:
        if isinstance(ctx, ObjectValue):
            ctx = ctx.contents.get(name)
        else:
            bad_path.append(name)
            ctx = None
    if bad_path:
        problems.add_err(
            Source.new("block context", 0, 0, 0, 0),
            "USAGE-bad-name-path",
            path=name_path,
            bad_path=bad_path,
        )
    return (ctx, problems)
