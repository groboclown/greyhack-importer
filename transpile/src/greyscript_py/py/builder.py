"""Builds GS elements from Python AST."""

from collections.abc import Callable, Sequence
from types import UnionType
from typing import Generic, TypeVar, cast

from .value_context import ValueContext, CallableValue, ContextItem
from ..ast import basic
from ..util.jdata import JsonData
from ..util.problems import Problems
from ..util.source import Source

T = TypeVar("T", bound=basic.GSElement, covariant=True)


class PyGsBuilder(Generic[T]):
    """Top-level handler for constructing a GSElement."""

    def build(self, problems: Problems) -> T | None:
        """Build the value."""
        raise NotImplementedError


class StaticBuilder(PyGsBuilder[T]):
    """Does not build, just returns the constructed value."""

    def __init__(self, value: T) -> None:
        self.value = value

    def build(self, problems: Problems) -> T | None:
        """Return the static value."""
        return self.value


class ErrorBuilder(PyGsBuilder[T]):
    """Just adds an error."""

    def __init__(self, __source: Source, __message_id: str, /, **kwargs: JsonData):
        self.src = __source
        self.message_id = __message_id
        self.kwargs = kwargs

    def build(self, problems: Problems) -> None:
        """Adds the problem and returns None."""
        problems.add_err(self.src, self.message_id, **self.kwargs)
        return None


class BlockBuilder(PyGsBuilder[basic.GSBlock]):
    """Builds each statement."""

    def __init__(
        self,
        src: Source,
        statements: Sequence[PyGsBuilder[basic.GSStatement | basic.GSValue]],
    ) -> None:
        self.src = src
        self.statements = list(statements)

    def build(self, problems: Problems) -> basic.GSBlock | None:
        """Builds the block."""
        ret: list[basic.GSStatement] = []
        is_ok = True
        for stmt_builder in self.statements:
            stmt = stmt_builder.build(problems)
            if stmt is None:
                is_ok = False
            elif not isinstance(stmt, basic.GSStatement):
                is_ok = False
                problems.add_err(
                    stmt.src,
                    "BAD-USAGE-expression-not-statement",
                    node=repr(stmt),
                )
            else:
                ret.append(stmt)
        if not is_ok:
            return None
        return basic.GSBlock(src=self.src, statements=ret)


class OneArgumentBuilder(PyGsBuilder[T]):
    """Build the value using one argument."""

    def __init__(
        self,
        src: Source,
        builder: Callable[[Source, basic.GSElement], T],
        argument_types: type | UnionType | None,
    ) -> None:
        self.src = src
        self.builder = builder
        self.argument: PyGsBuilder[basic.GSElement] | None = None
        self.argument_types = argument_types

    @staticmethod
    def new_import(src: Source) -> "OneArgumentBuilder[basic.GSImport]":
        """Create a GSImport builder."""
        return OneArgumentBuilder(
            src=src,
            builder=lambda s, e: basic.GSImport(
                src=s, path=cast(basic.GSConstantString, e).value
            ),
            argument_types=basic.GSConstantString,
        )

    @staticmethod
    def new_function_def(
        src: Source, parameters: Sequence[tuple[str, basic.GSValue | None]]
    ) -> "OneArgumentBuilder[basic.GSFunctionDef]":
        """Create a GSFunctionDef builder.

        Arguments are in the form (name, default_value)
        """
        return OneArgumentBuilder(
            src=src,
            builder=lambda s, e: basic.GSFunctionDef(
                src=s,
                parameter_pairs=parameters,
                statements=basic.GSBlock(src=s, statements=_as_block(e).statements),
            ),
            argument_types=basic.GSBlock,
        )

    @staticmethod
    def new_unary(
        src: Source, operator: str
    ) -> "OneArgumentBuilder[basic.GSUnaryOperation]":
        """Create a GSUnaryOperation builder."""
        return OneArgumentBuilder(
            src=src,
            builder=lambda s, e: basic.GSUnaryOperation(
                src=s, operator=operator, value=_as_value(e)
            ),
            argument_types=basic.GSValue,
        )

    @staticmethod
    def new_return_value(src: Source) -> "OneArgumentBuilder[basic.GSReturn]":
        """Create a GSReturn builder with a return value."""
        return OneArgumentBuilder(
            src=src,
            builder=lambda s, e: basic.GSReturn(src=s, value=_as_value(e)),
            argument_types=basic.GSValue,
        )

    def build(self, problems: Problems) -> T | None:
        """Return the static value."""
        if self.argument is None:
            problems.add_err(
                self.src,
                "SCRIPT-missing-argument",
            )
            return None
        argument = self.argument.build(problems)
        if argument is None:
            return None
        if self.argument_types is not None and not isinstance(
            argument, self.argument_types
        ):
            problems.add_err(
                self.src,
                "SCRIPT-wrong-argument-type",
                kind=str(argument.__class__),
            )
        return self.builder(self.src, argument)


class TwoArgumentBuilder(PyGsBuilder[T]):
    """Build the value using one argument."""

    def __init__(
        self,
        src: Source,
        builder: Callable[[Source, basic.GSElement, basic.GSElement], T],
        left_types: type | UnionType | None,
        right_types: type | UnionType | None,
    ) -> None:
        self.src = src
        self.builder = builder
        self.left: PyGsBuilder[basic.GSElement] | None = None
        self.right: PyGsBuilder[basic.GSElement] | None = None
        self.left_types = left_types
        self.right_types = right_types

    @staticmethod
    def new_member_ref(src: Source) -> "TwoArgumentBuilder[basic.GSMemberReference]":
        """Create a new GSMemberReference builder."""
        return TwoArgumentBuilder(
            src=src,
            builder=lambda s, l, r: basic.GSMemberReference(
                src=s, value=_as_value(l), member=cast(basic.GSConstantString, r).value
            ),
            left_types=basic.GSValue,
            right_types=basic.GSConstantString,
        )

    @staticmethod
    def new_binary(
        src: Source, operator: str
    ) -> "TwoArgumentBuilder[basic.GSBinaryOperation]":
        """Create a new GSBinaryOperation builder."""
        return TwoArgumentBuilder(
            src=src,
            builder=lambda s, l, r: basic.GSBinaryOperation(
                src=s,
                operator=operator,
                left=_as_value(l),
                right=_as_value(r),
            ),
            left_types=basic.GSValue,
            right_types=basic.GSValue,
        )

    @staticmethod
    def new_assign(src: Source) -> "TwoArgumentBuilder[basic.GSValueAssignment]":
        return TwoArgumentBuilder(
            src=src,
            builder=lambda s, l, r: basic.GSValueAssignment(
                src=s,
                name=_get_name(l),
                value=_as_value(r),
            ),
            left_types=basic.GSVariableValue,
            right_types=basic.GSValue,
        )

    def build(self, problems: Problems) -> T | None:
        """Return the built value."""
        if self.left is None or self.right is None:
            problems.add_err(
                self.src,
                "SCRIPT-missing-argument",
                left=repr(self.left),
                right=repr(self.right),
            )
            return None
        left = self.left.build(problems)
        right = self.right.build(problems)
        if left is None or right is None:
            return None
        if self.left_types is not None and not isinstance(left, self.left_types):
            problems.add_err(
                self.src,
                "SCRIPT-wrong-argument-type",
                kind=str(self.left.__class__),
            )
        if self.right_types is not None and not isinstance(right, self.right_types):
            problems.add_err(
                self.src,
                "SCRIPT-wrong-argument-type",
                kind=str(self.right.__class__),
            )
        return self.builder(self.src, left, right)


class CallBuilder(PyGsBuilder[basic.GSFunctionCall]):
    """Creates a GSFunctionCall value."""

    def __init__(
        self,
        src: Source,
        context: ValueContext,
    ) -> None:
        self.src = src
        # should be GSCallableValue, but this needs to perform lookups to possibly translate the value.
        self.func: PyGsBuilder[basic.GSValue] | None = None
        self.position_arguments: list[PyGsBuilder[basic.GSValue]] = []
        self.named_arguments: dict[str, PyGsBuilder[basic.GSValue]] = {}
        self.context = context

    def build(self, problems: Problems) -> basic.GSFunctionCall | None:
        """Return the built value."""
        is_ok = True
        func: basic.GSCallableValue | None = None
        if self.func is not None:
            raw_func = self.func.build(problems)
            if isinstance(raw_func, basic.GSCallableValue):
                func = raw_func
            elif isinstance(raw_func, basic.GSVariableRef):
                # This is fine.  It means a possible function reference was assigned to a variable.
                func = basic.GSFunctionRef(src=raw_func.src, name=raw_func.name)
            else:
                problems.add_warn(
                    self.src,
                    "USAGE-bad-type-as-function-name",
                    func=repr(raw_func),
                )
        if func is None:
            is_ok = False
        position: list[basic.GSValue] = []
        for arg_builder in self.position_arguments:
            arg = arg_builder.build(problems)
            if arg is None:
                is_ok = False
            else:
                position.append(arg)
        named: dict[str, basic.GSValue] = {}
        for name, arg_builder in self.named_arguments.items():
            arg = arg_builder.build(problems)
            if arg is None:
                is_ok = False
            else:
                named[name] = arg
        if not is_ok:
            return None

        if self.context:
            context: ContextItem | None = None
            if isinstance(func, basic.GSVariableRef | basic.GSFunctionRef):
                context = self.context.get_named(func, problems)
            elif isinstance(func, basic.GSMemberReference):
                context = self.context.get_member(func, problems)
            # else a basic.GSFunctionCall, which we can't derive anything from.

            if isinstance(context, CallableValue):
                ret, probs = context.as_invocation(
                    source=self.src,
                    position_arguments=position,
                    named_arguments=named,
                )
                problems.add_from(probs)
                return ret
            # Else didn't match up, but allow it.

        # Else not a known function.
        # This can't use named arguments.
        if self.named_arguments:
            problems.add_err(
                self.src,
                "ERROR-no-named-arguments",
                func=func,
            )
        assert func is not None  # nosec  # for mypy
        return basic.GSFunctionCall(
            src=self.src,
            func=func,
            parameters=position,
        )


class VariableBuilder(PyGsBuilder[basic.GSVariableRef | basic.GSFunctionRef]):
    """Determines the kind of variable referenced."""

    def __init__(self, src: Source, name: str, context: ValueContext) -> None:
        self.src = src
        self.name = name
        self.context = context

    def build(
        self, problems: Problems
    ) -> basic.GSVariableRef | basic.GSFunctionRef | None:
        """Return the built value."""
        entry = self.context.get((self.name,), Problems())
        if isinstance(entry, CallableValue):
            # It's a reference to a function.
            return basic.GSFunctionRef(src=self.src, name=self.name)
        if entry is None:
            # If entry is None, then it's not known, and probably a bug.
            problems.add_warn(self.src, "WARN-ref-unknown-value", name=self.name)
        return basic.GSVariableRef(src=self.src, name=self.name)


class ConditionBuilder:
    """Builds a GSConditionStatementsBlock.

    Not a formal PyGsBuilder.
    """

    def __init__(self, src: Source) -> None:
        self.src = src
        self.condition: PyGsBuilder[basic.GSValue] | None = None
        self.statements: list[PyGsBuilder[basic.GSStatement]] = []
        self.block: PyGsBuilder[basic.GSBlock] | None = None

    def build(self, problems: Problems) -> basic.GSConditionStatementsBlock | None:
        """Return the built value."""
        if self.condition is None:
            problems.add_err(self.src, "ERROR-no-condition")
            return None
        condition = self.condition.build(problems)
        if condition is None:
            return None
        is_ok = True
        statements: list[basic.GSStatement] = []
        for stmt_builder in self.statements:
            stmt = stmt_builder.build(problems)
            if stmt is None:
                is_ok = False
            else:
                statements.append(stmt)
        if self.block is not None:
            block = self.block.build(problems)
            if block is None:
                is_ok = False
            else:
                statements.extend(block.statements)
        if not is_ok:
            return None
        return basic.GSConditionStatementsBlock(
            src=self.src,
            condition=condition,
            statements=basic.GSBlock(src=self.src, statements=statements),
        )


class IfBuilder(PyGsBuilder[basic.GSIfBlock]):
    """Determines the kind of if block."""

    def __init__(self, src: Source) -> None:
        self.src = src
        self.if_blocks: list[ConditionBuilder] = []
        self.else_block: PyGsBuilder[basic.GSBlock] | None = None

    def build(self, problems: Problems) -> basic.GSIfBlock | None:
        """Return the built value."""
        if not self.if_blocks:
            problems.add_err(self.src, "ERROR-no-if")
            return None
        if_blocks: list[basic.GSConditionStatementsBlock] = []
        is_ok = True
        for cond in self.if_blocks:
            if_block = cond.build(problems)
            if if_block is None:
                is_ok = False
            else:
                if_blocks.append(if_block)
        else_block: basic.GSBlock
        if self.else_block is None:
            else_block = basic.GSBlock(src=self.src, statements=[])
        else:
            block = self.else_block.build(problems)
            if block is None:
                return None
            else:
                else_block = block

        if not is_ok:
            return None
        return basic.GSIfBlock(
            src=self.src,
            if_blocks=if_blocks,
            else_statements=else_block,
        )


def _get_name(val: basic.GSElement) -> str:
    if isinstance(val, basic.GSVariableRef | basic.GSFunctionRef | basic.GSTypeRef):
        return val.name
    if isinstance(val, basic.GSMemberReference):
        return val.member
    raise RuntimeError(f"BUG: bad use of {val} for value name")


def _as_block(item: basic.GSElement) -> basic.GSBlock:
    if not isinstance(item, basic.GSBlock):
        raise RuntimeError(f"BUG: bad use of {item} for block")
    return item


def _as_value(item: basic.GSElement) -> basic.GSValue:
    if not isinstance(item, basic.GSValue):
        raise RuntimeError(f"BUG: bad use of {item} for value")
    return item
