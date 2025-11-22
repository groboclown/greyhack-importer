"""The basic elements of the GreyScript language."""

from collections.abc import Sequence
from typing import NamedTuple, Protocol, runtime_checkable

from ..util.source import Source


@runtime_checkable
class GSElement(Protocol):
    """All elements in the script must conform to this."""

    src: Source


class GSConstantString(NamedTuple):
    """A string value."""

    src: Source
    value: str


class GSConstantNumber(NamedTuple):
    """A number value.

    Also, can be a boolean ('true' = 1, 'false' = 0).
    """

    src: Source
    value: float | int


class GSNull(NamedTuple):
    """The 'null' value."""

    src: Source


class GSBlock(NamedTuple):
    """A list of statements."""

    src: Source
    statements: Sequence["GSStatement"]


class GSFunctionDef(NamedTuple):
    """A function definition.

    Formally, this defines a value.

    The parameter pairs allows for the parameter name and optional default value.
    """

    src: Source
    parameter_pairs: Sequence[tuple[str, "GSValue | None"]]
    statements: GSBlock


GSConstant = GSConstantNumber | GSConstantString | GSFunctionDef | GSNull


class GSFunctionRef(NamedTuple):
    """A variable reference to a function by value (not invoked)."""

    src: Source
    name: str


class GSTypeRef(NamedTuple):
    """A reference to a type name."""

    src: Source
    name: str


class GSVariableRef(NamedTuple):
    """A reference to a variable."""

    src: Source
    name: str


class GSList(NamedTuple):
    """A list of items.

    This does not declare a variable, but instead refers to a
    list construction with initial values.
    """

    src: Source
    items: GSBlock


class GSKeyPair(NamedTuple):
    """A map key/value pair."""

    src: Source
    key: "GSValue"
    value: "GSValue"


class GSMap(NamedTuple):
    """A list of key/value pairs.

    Can also be used as an object or class.
    """

    src: Source
    items: list[GSKeyPair]


class GSBinaryOperation(NamedTuple):
    """An operator with a left and right side.

    Includes standard operators as well as "member reference" ('.').
    """

    src: Source
    operator: str
    left: "GSValue"
    right: "GSValue"


class GSUnaryOperation(NamedTuple):
    """An operator with a value."""

    src: Source
    operator: str
    value: "GSValue"


class GSFunctionCall(NamedTuple):
    """A value reference for a function call, along with its parameters.

    Can be either a stand-alone statement, or used as a value construction.
    """

    src: Source
    func: "GSValue"
    parameters: list["GSValue"]


# GSValue: anything that evaluates to a single value.
GSValue = (
    GSMap
    | GSList
    | GSVariableRef
    | GSTypeRef
    | GSFunctionRef
    | GSVariableRef
    | GSConstant
    | GSFunctionCall
    | GSBinaryOperation
    | GSUnaryOperation
)
# assert isinstance(GSValue, GSElement)


class GSValueAssignment(NamedTuple):
    """Assign a variable to a value.

    A kind of statement.
    """

    src: Source
    name: str
    value: GSValue


class GSReturn(NamedTuple):
    """Return, optionally with a value."""

    src: Source
    value: GSValue | None


class GSBreak(NamedTuple):
    """Break out of a loop."""

    src: Source


class GSContinue(NamedTuple):
    """Go back to the start of a loop."""

    src: Source


class GSImport(NamedTuple):
    """Import another file.

    While technically a function, it has extremely limited capabilities and must be used
    precisely.
    """

    src: Source
    path: str


class GSConditionStatementsBlock(NamedTuple):
    """A condition + statements."""

    src: Source
    condition: GSValue
    statements: GSBlock


class GSWhileBlock(NamedTuple):
    """A while loop, which contains a conditional expression and statements."""

    src: Source
    block: GSConditionStatementsBlock


class GSForBlock(NamedTuple):
    """Loops through elements in a list.

    "name" references the newly minted variable, and "value"
    references the source list that it loops over.
    """

    src: Source
    name: str
    value: GSValue
    statements: GSBlock


class GSIfBlock(NamedTuple):
    """An if block.

    Contains 1 or more condition + statements, and 0 or more final 'else' statements.
    """

    src: Source
    if_blocks: Sequence[GSConditionStatementsBlock]
    else_statements: GSBlock


GSStatement = (
    GSValueAssignment
    | GSFunctionCall
    | GSReturn
    | GSBreak
    | GSContinue
    | GSImport
    | GSWhileBlock
    | GSForBlock
    | GSIfBlock
)
# assert isinstance(GSStatement, GSElement)
