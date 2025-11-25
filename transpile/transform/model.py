"""Basic data model for allowing transformations of the AST."""

from greyscript_py.ast.basic import GSElement

NodePathEntry = tuple[str, int]
NodePath = list[NodePathEntry]


class NodePtr:
    """A pointer to a node.

    The node location may change, but this will continue to point to it,
    unless it's removed.
    """

    __slots__ = ("_entry", "_node", "_parent")

    def __init__(
        self,
        entry: list[NodePathEntry],
        node: list["ScriptNode | None"],
        parent: list["NodePtr | None"],
    ) -> None:
        assert len(entry) == 1  # nosec  # for dev
        assert len(node) == 1  # nosec  # for dev
        assert len(parent) == 1  # nosec  # for dev
        self._entry = entry
        self._node = node
        self._parent = parent

    @property
    def path(self) -> NodePath:
        """Return the location of the path in the tree."""
        ret = []
        if self._parent[0]:
            ret.extend(self._parent[0].path)
        ret.append(self._entry[0])
        return ret

    @property
    def valid(self) -> bool:
        """Return True if the pointed-to node still exists."""
        return self._node[0] is not None

    @property
    def node(self) -> "ScriptNode | None":
        """Return the referenced node."""
        return self._node[0]

    @property
    def parent(self) -> "NodePtr | None":
        """Return the node parent."""
        return self._parent[0]


class NodePtrOwner:
    """The owner of the node pointer.

    Used for managing a node that controls a child node.
    """

    __slots__ = ("_entry", "_node", "_parent", "_ptr")

    def __init__(
        self,
        entry: NodePathEntry | None,
        node: "ScriptNode | None",
        parent: NodePtr | None,
    ) -> None:
        self._entry = [entry]
        self._node = [node]
        self._parent = [parent]
        self._ptr = NodePtr(entry=self._entry, node=self._node, parent=self._parent)

    @property
    def ptr(self) -> NodePtr:
        """Get the node pointer."""
        return self._ptr

    @property
    def entry(self) -> NodePathEntry | None:
        """Get the entry for this node."""
        return self._entry[0]

    @property
    def parent(self) -> NodePtr | None:
        """Get the parent pointer."""
        return self._parent[0]

    def move_to(self, new_parent: NodePtr | None, new_entry: NodePathEntry) -> None:
        """Move the node to a new location."""
        self._parent[0] = new_parent
        self._entry[0] = new_entry

    def remove(self) -> None:
        """Remove this node."""
        self._parent[0] = None
        self._entry[0] = None
        self._node[0] = None


class VariableDecl:
    """Declaration of a variable.

    This either comes from a variable assignment or a parameter definition.
    On a rare occasion, a 'globals.X = Y' can cause this.
    """

    def __init__(self, name: str, owning_block: NodePtr | None) -> None:
        self._name = name
        self._owning_block = owning_block
        self.read_at: list[NodePtr] = []
        self.write_at: list[NodePtr] = []

    def name(self) -> str:
        """Get the variable name."""
        return self._name

    def owning_block(self) -> NodePtr | None:
        """Get the block that declares the variable, or None if global."""
        return self._owning_block


class ScriptNode:
    """A basic script element."""

    def src(self) -> GSElement:
        """Source for the node."""
        raise NotImplementedError

    def active(self) -> bool:
        """Return True if this still belongs to the tree."""
        raise NotImplementedError

    def ptr(self) -> NodePtr:
        """The reference to this node."""
        raise NotImplementedError

    def find(self, path: NodePath) -> NodePtr | None:
        """Find a child node at the given absolute path."""
        raise NotImplementedError

    def nodes(self) -> list[NodePtr]:
        """Return the directly contained nodes."""
        raise NotImplementedError

    def context(self) -> dict[str, VariableDecl]:
        """Return the references to the current context's variables."""
        raise NotImplementedError

    def references(self) -> set[str]:
        """Return the set of context variables referenced by this node."""
        raise NotImplementedError

    def assigns(self) -> set[str]:
        """Return the set of context variables assigned by this node."""
        raise NotImplementedError

    def reparent(self, parent: NodePtr, entry: NodePathEntry) -> None:
        """Re-parent this node to a different location.

        This causes the pointer to update its references.
        """
        raise NotImplementedError

    def remove(self) -> None:
        """Remove this node from its parents.

        This call should trigger the node to clean itself up, and all its children.
        """
        raise NotImplementedError

    def gen(self) -> GSElement:
        """Turn this back into a source element."""
        raise NotImplementedError
