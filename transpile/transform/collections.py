"""Collection value types."""

from collections.abc import Callable
from typing import cast

from greyscript_py.ast.basic import GSElement
from .helpers import NodeListOwner
from .model import (
    ScriptNode,
    NodePtr,
    NodePath,
    NodePtrOwner,
    NodePathEntry,
)


class TFListValue(ScriptNode):
    """A list of values."""

    def __init__(
        self,
        *,
        src: GSElement,
        items: list[ScriptNode],
    ) -> None:
        self._ptr = NodePtrOwner(entry=None, node=self, parent=None)
        self._nodes: NodeListOwner[ScriptFragment] = NodeListOwner(
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

    def reparent(self, parent: NodePtr, entry: NodePathEntry) -> None:
        """Change the location."""
        self._ptr.move_to(parent, entry)


class GSMapEntry(ScriptNode):
    """The map key and value."""

    def __init__(
        self,
        src: Source,
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
        source: Source,
        items: list[GSMapEntry],
    ) -> None:
        self.source = source
        self.entries = items

    def src(self) -> Source:
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

    def render(self, visitor: StatementRenderVisitor) -> None:
        """Render this node."""
        visitor.render_fragments(self.source, "{")
        first = True
        for key, val, src in self.entries:
            if first:
                first = False
            else:
                visitor.render_fragments(src or self.source, ",")
            if isinstance(key, str):
                visitor.render_fragments(src or self.source, encode_gs_string(key))
            elif key is True:
                visitor.render_fragments(src or self.source, "1")
            elif key is False:
                visitor.render_fragments(src or self.source, "0")
            else:
                # int or float
                visitor.render_fragments(src or self.source, str(key))
            visitor.render_fragments(src or self.source, ":")
            val.render(visitor)
        visitor.render_fragments(self.source, "}")


GSValue = GSListValue | GSMapValue | GSConstantValue | GSReferenceValue
