"""Single (no child) script nodes."""

from collections.abc import Callable
from typing import Literal, cast

from greyscript_py.ast import basic
from .helpers import SimpleScriptNode, NodeListOwner
from .model import (
    ScriptNode,
    NodePtr,
    NodePath,
    NodePtrOwner,
    NodePathEntry,
)

TFConstantType = Literal["string", "number", "null"]


class TFConstantValue(SimpleScriptNode):
    """A simple, constant value.

    A hard-coded value inserted into the script.

    'type' values (such as 'string' and 'number') encode the name in the
    'value' field as a string.
    """

    @staticmethod
    def for_str(source: basic.GSConstantString) -> "TFConstantValue":
        """Create a string value."""
        return TFConstantValue(source=source, gs_type="string", value=source.value)

    @staticmethod
    def for_number(source: basic.GSConstantNumber) -> "TFConstantValue":
        """Create an integer or float value."""
        return TFConstantValue(source=source, gs_type="number", value=source.value)

    @staticmethod
    def for_null(source: basic.GSNull) -> "TFConstantValue":
        """Create a null value."""
        return TFConstantValue(source=source, gs_type="null", value=None)

    def __init__(
        self,
        *,
        source: basic.GSElement,
        gs_type: TFConstantType,
        value: int | float | str | None,
    ) -> None:
        SimpleScriptNode.__init__(self, source)
        self.gs_type = gs_type
        self.value = value

    def gen(self) -> basic.GSElement:
        """Turn this back into a source element."""
        return self.src()


class GSReferenceValue(SimpleScriptNode):
    """A named value (variable or similar type).

    These allow for renaming the value across all shared references.

    'type' values (such as 'string' and 'number') encode the name in the
    'value' field as a string.
    """

    def __init__(
        self,
        *,
        source: basic.GSElement,
        name: str,
        gs_type: GSRefType,
    ) -> None:
        SimpleScriptNode.__init__(self, source)
        self.name = name
        self.gs_type: GSType = gs_type

    def is_type(self) -> bool:
        """Return True if this value references a type."""
        return self.gs_type == "type"

    def is_function(self) -> bool:
        """Return True if this value references a function as a value."""
        return self.gs_type == "function"

    def is_variable(self) -> bool:
        """Return True if this value references a variable."""
        return self.gs_type == "variable"

    def render(self, visitor: StatementRenderVisitor) -> None:
        """Render this node."""
        if self.gs_type == "function":
            # Function reference
            visitor.render_fragments(self._src, f"@{self.name}")
        else:
            # Variable and type names are just the name.
            visitor.render_fragments(self._src, str(self.name))


def value_node_paths(node: ScriptNode, value_type: GSRefType) -> list[NodePtr]:
    """Find all contained nodes of the given value type."""
    remaining = [node.ptr()]
    ret = []
    while remaining:
        kid = remaining.pop()
        kid_n = kid.node
        if isinstance(kid_n, GSReferenceValue) and kid_n.gs_type == value_type:
            ret.append(kid)
        remaining.extend(kid_n.nodes())
    return ret


class GSListValue(ScriptNode):
    """A list of values."""

    def __init__(
        self,
        *,
        src: basic.GSElement,
        items: list[ScriptNode],
    ) -> None:
        self._ptr = NodePtrOwner(entry=None, node=self, parent=None)
        self._nodes: NodeListOwner[ScriptNode] = NodeListOwner(
            src=src, ptr=self._ptr.ptr, nodes=items
        )
        self.gs_type: GSType = "list"

    def src(self) -> Source:
        """Source for the node."""
        return self._nodes.src

    def ptr(self) -> NodePtr:
        """The reference to this node."""
        return self._nodes.ptr

    def find(self, path: NodePath) -> NodePtr | None:
        """Find a child node at the given absolute path."""
        return self._nodes.find(path)

    def nodes(self) -> list[NodePtr]:
        """The directly contained nodes."""
        return self._nodes.children_ptr()

    def reparent(self, parent: NodePtr | None, entry: NodePathEntry | None) -> None:
        """Change the location."""
        self._ptr.move_to(parent, entry)

    def render(self, visitor: StatementRenderVisitor) -> None:
        """Render this node."""
        visitor.render_fragments(self._nodes.src, "[")
        first = True
        for entry in self._nodes.nodes:
            if first:
                first = False
            else:
                visitor.render_fragments(self._nodes.src, ",")
            entry.render(visitor)
        visitor.render_fragments(self._nodes.src, "]")


class GSMapEntry(ScriptFragment):
    """The map key and value."""

    def __init__(
        self,
        src: basic.GSElement,
        key: ScriptFragment,
        value: ScriptFragment,
    ) -> None:
        self._src = src
        self._ptr = NodePtrOwner(entry=None, node=self, parent=None)
        self._key = key
        self._value = value

    def get_key(self) -> ScriptFragment:
        """Get the key fragment."""
        return self._key

    def set_key(self, key: ScriptFragment) -> None:
        """Set the key fragment."""
        self._key.reparent(parent=None, entry=None)
        key.reparent(parent=self._ptr.ptr, entry=("key", 0))
        self._key = key

    key = property(
        cast(Callable[["GSMapEntry"], ScriptFragment], get_key),
        cast(Callable[["GSMapEntry", ScriptFragment], None], set_key),
        None,
        "The key fragment.",
    )

    def get_value(self) -> ScriptFragment:
        """Get the value fragment."""
        return self._value

    def set_value(self, value: ScriptFragment) -> None:
        """Set the value fragment."""
        self._value.reparent(parent=None, entry=None)
        value.reparent(parent=self._ptr.ptr, entry=("value", 0))
        self._value = value

    value = property(
        cast(Callable[["GSMapEntry"], ScriptFragment], get_value),
        cast(Callable[["GSMapEntry", ScriptFragment], None], set_value),
        None,
        "The value fragment.",
    )

    def src(self) -> Source:
        """Source for the node."""
        return self._src

    def ptr(self) -> NodePtr:
        """The reference to this node."""
        return self._ptr.ptr

    def find(self, path: NodePath) -> NodePtr | None:
        """Find a child node at the given absolute path."""
        if path == self._ptr.ptr.path:
            return self._ptr.ptr
        ret = self._key.find(path)
        if ret:
            return ret
        return self._value.find(path)

    def nodes(self) -> list[NodePtr]:
        """The directly contained nodes."""
        return [self._key.ptr(), self._value.ptr()]

    def render(self, visitor: StatementRenderVisitor) -> None:
        """Render this node."""
        self._key.render(visitor)
        visitor.render_fragments(self._src, ":")
        self._value.render(visitor)


class GSMapValue(ScriptFragment):
    """A map of keys to values.

    Keys may be only numbers or strings; booleans are turned into
    numbers.  It maintains a "source" for each key.  Note that
    sources may be set as a computed value.
    """

    def __init__(
        self,
        *,
        source: basic.GSElement,
        items: list[GSMapEntry],
    ) -> None:
        self.source = source
        self.entries = items

    def src(self) -> basic.GSElement:
        """Source for the node."""
        raise NotImplementedError

    def ptr(self) -> NodePtr:
        """The reference to this node."""
        raise NotImplementedError

    def find(self, path: NodePath) -> NodePtr | None:
        """Find a child node at the given absolute path."""
        raise NotImplementedError

    def nodes(self) -> list[NodePtr]:
        """The directly contained nodes."""
        raise NotImplementedError
