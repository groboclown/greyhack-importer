"""Helper tools for the implementations."""

from typing import TypeVar

from greyscript_py.ast.basic import GSElement
from .model import (
    NodePath,
    ScriptNode,
    NodePtr,
    NodePtrOwner,
    NodePathEntry,
    VariableDecl,
)


def is_path_substr(current: NodePath, check: NodePath) -> bool:
    """Check if the 'check' is a child or equal to 'current'."""
    return path_match_depth(current, check) >= len(current)


def path_match_depth(top: NodePath, under: NodePath) -> int:
    """Return how deep under 'top' the 'under' goes."""
    top_len = len(top)
    under_len = len(under)
    for i in range(top_len):
        if under_len <= i or under[i] != top[i]:
            return i - 1
    return top_len


class SimpleScriptNode(ScriptNode):
    """A simple script node that has no children."""

    def __init__(self, source: GSElement) -> None:
        self._src = source
        self._ptr = NodePtrOwner(entry=None, node=self, parent=None)

    def src(self) -> GSElement:
        """Source for the node."""
        return self._src

    def active(self) -> bool:
        """Return True if this still belongs to the tree."""
        return self._ptr.parent is not None

    def ptr(self) -> NodePtr:
        """The reference to this node."""
        return self._ptr.ptr

    def find(self, path: NodePath) -> NodePtr | None:
        """Find a child node at the given absolute path."""
        return None

    def nodes(self) -> list[NodePtr]:
        """Return the directly contained nodes."""
        return []

    def context(self) -> dict[str, VariableDecl]:
        """Return the references to the current context's variables."""
        parent = self._ptr.parent.node
        if parent:
            return parent.context()
        return {}

    def references(self) -> set[str]:
        """Return the set of context variables referenced by this node."""
        return set()

    def assigns(self) -> set[str]:
        """Return the set of context variables assigned by this node."""
        return set()

    def reparent(self, parent: NodePtr, entry: NodePathEntry) -> None:
        """Re-parent this node to a different location."""
        self._ptr.move_to(parent, entry)

    def remove(self) -> None:
        """Remove this node from its parents."""
        self._ptr.remove()

    def gen(self) -> GSElement:
        """Turn this back into a source element."""
        raise NotImplementedError


NodeType = TypeVar("NodeType", bound=ScriptNode)


class NodeListOwner[NodeType]:
    """Handles a list of child node entries."""

    __slots__ = ("src", "ptr", "nodes")

    def __init__(
        self,
        *,
        src: GSElement,
        ptr: NodePtr,
        nodes: list[NodeType],
    ) -> None:
        self.src = src
        self.ptr = ptr
        self.nodes: list[NodeType] = []
        idx = 0
        for kid in nodes:
            if not isinstance(kid, ScriptNode):
                raise RuntimeError("nodes must be a script node")
            kid.reparent(parent=self.ptr, entry=("", idx))
            self.nodes.append(kid)
            idx += 1

    def swap(self, src_idx: int, tgt_idx: int) -> None:
        """Move the node at the source index to the target index."""
        n_len = len(self.nodes)
        if 0 <= src_idx < n_len and 0 <= tgt_idx < n_len:
            src = self.nodes[src_idx]
            tgt = self.nodes[tgt_idx]
            self.nodes[tgt_idx] = src
            self.nodes[src_idx] = tgt
            src.reparent(parent=self.ptr, entry=("", tgt_idx))
            tgt.reparent(parent=self.ptr, entry=("", src_idx))
            return

        raise IndexError(f"{src_idx}->{tgt_idx} / {n_len}")

    def insert(self, at: int, node: NodeType) -> None:
        """Insert the node at the given index."""
        if not isinstance(node, ScriptNode):
            raise RuntimeError("nodes must be a script node")
        n_len = len(self.nodes)
        if at == n_len:
            node.reparent(parent=self.ptr, entry=("", at))
            self.nodes.append(node)
            return
        if 0 <= at < n_len:
            # at least 1 node in the list.
            self.nodes.append(self.nodes[n_len - 1])
            pos = n_len
            while pos > at:
                self.nodes[pos] = self.nodes[pos - 1]
                self.nodes[pos].reparent(parent=self.ptr, entry=("", pos))
                pos -= 1
            self.nodes[at] = node
            return
        raise IndexError(f"{at} / {n_len}")

    def append(self, node: NodeType) -> None:
        """Append the node to the end of the list."""
        if not isinstance(node, ScriptNode):
            raise RuntimeError("nodes must be a script node")
        node.reparent(parent=self.ptr, entry=("", len(self.nodes)))
        self.nodes.append(node)

    def remove(self, idx: int) -> tuple[NodeType, NodePtrOwner] | None:
        """Remove the node at the index."""
        if 0 <= idx < len(self.nodes):
            ret = self.nodes[idx]
            ret.reparent(None, None)
            del self.nodes[idx]
            for pos in range(idx, len(self.nodes)):
                self.nodes[pos].reparent(parent=self.ptr, entry=("", pos))
            return ret

    def find(self, path: NodePath) -> NodePtr | None:
        """Find a child node at the given absolute path."""
        ptr_path = self.ptr.path
        p_len = len(ptr_path)
        depth = path_match_depth(ptr_path, path)
        if depth < p_len:
            return None
        if depth == p_len:
            return self.ptr
        pos = ptr_path[p_len]
        if pos[0] == "" and 0 <= pos[1] < len(self.nodes):
            node = self.nodes[pos[1]]
            if p_len == depth + 1:
                return node.ptr()
            return node.find(path)
        return None

    def children(self) -> list[ScriptNode]:
        """The directly contained nodes."""
        return list(self.nodes)

    def children_ptr(self) -> list[NodePtr]:
        """The directly contained nodes, as pointers."""
        return [s.ptr() for s in self.nodes]
