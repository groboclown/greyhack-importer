"""Generate a verbose script file from the AST."""
from collections.abc import Iterable

from .abc import StatementRenderVisitor, ValueRenderVisitor, BlockStartRenderVisitor, BlockStatementRenderVisitor
from .string import encode_gs_string
from ..util.source import Source


class _Renders:
    def parts(self) -> Iterable["_Renders | str"]:
        """Generate the text from the visited statements."""
        raise NotImplementedError


class _ListRenders(_Renders):
    def __init__(self, src: Source) -> None:
        self.src = src
        self.order: list[_Renders | str] = []

    def parts(self) -> Iterable[_Renders | str]:
        """Generate the text from the visited statements."""
        return self.order


class VerboseRenderer(StatementRenderVisitor, _ListRenders):
    """Renders a script."""
    def __init__(self, src: Source, indent: int = 0) -> None:
        _ListRenders.__init__(self, src)
        self._indent = indent
        str_indent = _mk_indent(self._indent)
        self.order.append(f"\n{str_indent}// {_render_source(self.src)}\n")

    def text(self) -> str:
        """Generate the text from the visited statements."""
        return _join(self.parts())

    def render_statement(self, source: Source) -> ValueRenderVisitor:
        """Render a list of script tokens."""
        ret = _VerboseValueRenderVisitor(source, self._indent, self)
        self.order.append(ret)
        self.order.append("\n")
        return ret

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Begin a block section statement.

        'kind' represents the first keyword of the block and the 'end *' keyword.
        """
        ret = _VerboseBlockStartRenderVisitor(source, kind, self._indent, self)
        self.order.append(ret)
        self.order.append("\n")
        return ret


class _VerboseValueRenderVisitor(ValueRenderVisitor, _ListRenders):
    def __init__(self, src: Source, indent: int, parent: StatementRenderVisitor) -> None:
        _ListRenders.__init__(self, src)
        self._indent = indent
        self._parent = parent

    def render_sub_value(self, source: Source) -> "ValueRenderVisitor":
        """Render a sub-value."""
        self.order.append(" (")
        self.order.append(_eol(source, _mk_indent(self._indent + 1)))
        ret = _VerboseValueRenderVisitor(source, self._indent + 1, self._parent)
        self.order.append(ret)
        self.order.append(_eol(source, _mk_indent(self._indent)))
        self.order.append(")")
        return ret

    def render_fragments(self, source: Source, *tokens: str) -> None:
        """Render a collection of tokens that make up part of this value."""
        if tokens and not tokens[0].startswith(" "):
            self.order.append(" ")
        self.order.extend(tokens)

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Render a block within the value.

        Currently used only for 'function' declarations.
        """
        ret = _VerboseBlockStartRenderVisitor(source, kind, self._indent, self._parent)
        self.order.append(ret)
        return ret

    def render_string(self, source: Source, str_contents: str) -> None:
        """Constructs a constant string token."""
        self.order.append(encode_gs_string(str_contents))


class _VerboseBlockStartRenderVisitor(BlockStartRenderVisitor, _ListRenders):
    def __init__(self, src: Source, kind: str, indent: int, parent: StatementRenderVisitor) -> None:
        _ListRenders.__init__(self, src)
        self._kind = kind
        self._indent = indent
        self._parent = parent
        str_indent = _mk_indent(self._indent)
        self.order.append(f"\n{str_indent}// {_render_source(self.src)}\n{str_indent}{self._kind}")

    def render_sub_value(self, source: Source) -> "ValueRenderVisitor":
        """Render a sub-value."""
        raise NotImplementedError

    def render_fragments(self, source: Source, *tokens: str) -> None:
        """Render a collection of tokens that make up part of this value."""
        self.order.extend(tokens)

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Render a block within the value.

        Currently used only for 'function' declarations.
        """
        return _VerboseBlockStartRenderVisitor(source, kind, self._indent + 1, self._parent)

    def render_string(self, source: Source, str_contents: str) -> None:
        """Constructs a constant string token."""
        self.order.append(encode_gs_string(str_contents))

    def end_start(self, source: Source) -> BlockStatementRenderVisitor:
        """End the start section of the block.

        Rendering of the rest of the block continues with the returned value.
        """
        self.order.append("\n")
        ret = _VerboseBlockStatementRenderVisitor(source, self._kind, self._indent, self._parent)
        self.order.append(ret)
        return ret


class _VerboseBlockStatementRenderVisitor(BlockStatementRenderVisitor, _ListRenders):
    def __init__(self, src: Source, kind: str, indent: int, parent: StatementRenderVisitor) -> None:
        _ListRenders.__init__(self, src)
        self._kind = kind
        self._indent = indent
        self._parent = parent

    def render_statement(self, source: Source) -> ValueRenderVisitor:
        """Render a list of script tokens."""
        ret = _VerboseValueRenderVisitor(source, self._indent + 1, self._parent)
        self.order.append(ret)
        return ret

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Begin a block section statement.

        'kind' represents the first keyword of the block and the 'end *' keyword.
        """
        ret = _VerboseBlockStartRenderVisitor(source, kind, self._indent + 1, self._parent)
        self.order.append(ret)
        return ret

    def continue_block(
        self, source: Source, *fragments: str
    ) -> "BlockStartRenderVisitor":
        """Render the 'else' or 'else if' continuation block start.

        If an 'else if' section, then the 'render_sub_value' must be called on the
        condition.
        """
        indent = _mk_indent(self._indent)
        if fragments:
            self.order.append(f"\n{indent}")
            self.order.extend(fragments)
        return _VerboseBlockStartRenderVisitor(source, self._kind, self._indent, self._parent)

    def end_block(self, source: Source) -> StatementRenderVisitor:
        """End the block rendering.

        The parent StatementRenderVisitor should continue use, returned
        by this end call.
        """
        indent = _mk_indent(self._indent)
        self.order.append(f"\n{indent}end {self._kind}\n")
        return self._parent


def _eol(src: Source, indent: str) -> str:
    """Create an EOL text bit."""
    return f"  // {_render_source(src)}\n{indent}"


def _render_source(source: Source) -> str:
    """Create the comment text (without comment wrappers) for the source location."""
    location = ""
    if source.start:
        location = f"@{repr(source.start)}"
        if source.end:
            location += f"-{repr(source.end)}"
    return f"({source.filename}{location})"


def _mk_indent(count: int) -> str:
    return "  " * count if count > 0 else ""


def _join(items: Iterable[_Renders | str]) -> str:
    """Join parts of the render and """
    stack: list[_Renders | str] = list(items)
    ret = ""
    last_was_space = True
    while stack:
        item = stack.pop(0)
        if isinstance(item, str):
            if last_was_space and item.startswith(" "):
                item = item.lstrip(" ")
            ret += item
        elif isinstance(item, _Renders):
            stack = [*item.parts(), *stack]
    return ret
