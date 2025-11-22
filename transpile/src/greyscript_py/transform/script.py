"""A GreyHack script AST."""

from .helpers import NodeListOwner
from .model import (
    ScriptNode,
    NodePtrOwner,
    NodePtr,
    NodePath,
    VariableDecl,
    NodePathEntry,
)
from ..ast.basic import GSElement, GSStatement, GSBlock
from ..util.problems import Problems


class GreyHackScript(ScriptNode):
    """A GreyHack script.

    The root of the script nodes.
    """

    def __init__(self, name: str, source: GSElement) -> None:
        self.name = name
        self._problems = Problems()
        self._ptr = NodePtrOwner(entry=None, node=self, parent=None)
        self._statements = NodeListOwner(
            src=source,
            ptr=self._ptr.ptr,
            nodes=[],
        )

    @property
    def problems(self) -> Problems:
        """Get the problem set for this script."""
        return self._problems

    def src(self) -> GSElement:
        """The source element for this node."""
        return self._statements.src

    def active(self) -> bool:
        """Return True if this still belongs to the tree."""
        return True

    def ptr(self) -> NodePtr:
        """The reference to this node."""
        return self._ptr.ptr

    def find(self, path: NodePath) -> NodePtr | None:
        """Find a child node at the given absolute path."""
        return self._statements.find(path)

    def nodes(self) -> list[NodePtr]:
        """The directly contained nodes."""
        return self._statements.children_ptr()

    def context(self) -> dict[str, VariableDecl]:
        """Return the references to the current context's variables."""
        raise NotImplementedError

    def references(self) -> set[str]:
        """Return the set of context variables referenced by this node."""
        ret = set()
        for child in self._statements.children():
            ret.union(child.references())
        return ret

    def assigns(self) -> set[str]:
        """Return the set of context variables assigned by this node."""
        ret = set()
        for child in self._statements.children():
            ret.union(child.assigns())
        return ret

    def reparent(self, parent: NodePtr, entry: NodePathEntry) -> None:
        """Re-parent this node to a different location.

        This causes the pointer to update its references.
        """
        # A script cannot reparent itself.
        raise NotImplementedError

    def remove(self) -> None:
        """Remove this node from its parents.

        This call should trigger the node to clean itself up, and all its children.
        """
        # A script cannot remove itself.
        raise NotImplementedError

    def gen(self) -> GSElement:
        """Turn this back into a source element."""
        statements: list[GSStatement] = []
        for stmt in self._statements.children():
            statements.append(stmt.gen())
        return GSBlock(src=self._statements.src.src, statements=statements)
