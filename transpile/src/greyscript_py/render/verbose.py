"""Generate a verbose script file from the AST."""

from .abc import StatementRenderVisitor, ValueRenderVisitor, BlockStartRenderVisitor, BlockStatementRenderVisitor
from .string import encode_gs_string
from ..util.source import Source


class _Renders:
    def text(self) -> str:
        """Generate the text from the visited statements."""
        raise NotImplementedError


class _ListRenders(_Renders):
    def __init__(self, src: Source) -> None:
        self.src = src
        self.order: list[_Renders] = []


class VerboseRenderer(StatementRenderVisitor, _ListRenders):
    """Renders a script."""
    def __init__(self, src: Source, indent: int = 0) -> None:
        _ListRenders.__init__(self, src)
        self._indent = indent

    def text(self) -> str:
        """Generate the text from the visited statements."""
        indent = _mk_indent(self._indent)
        ret = f"\n{indent}// {_render_source(self.src)}\n"
        for item in self.order:
            ret += item.text() + "\n"
        return ret

    def render_statement(self, source: Source) -> ValueRenderVisitor:
        """Render a list of script tokens."""
        ret = _VerboseValueRenderVisitor(source, self._indent, self)
        self.order.append(ret)
        return ret

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Begin a block section statement.

        'kind' represents the first keyword of the block and the 'end *' keyword.
        """
        ret = _VerboseBlockStartRenderVisitor(source, kind, self._indent, self)
        self.order.append(ret)
        return ret


class _VerboseValueRenderVisitor(ValueRenderVisitor, _ListRenders):
    def __init__(self, src: Source, indent: int, parent: StatementRenderVisitor) -> None:
        _ListRenders.__init__(self, src)
        self._indent = indent
        self._parent = parent

    def text(self) -> str:
        """Generate the text from the visited statements."""
        ret = ""
        for bit in self.order:
            ret += bit.text()
        return ret

    def render_sub_value(self, source: Source) -> "ValueRenderVisitor":
        """Render a sub-value."""
        self.order.append(_TextRenderer(" ("))
        self.order.append(_TextRenderer.new_eol(source, _mk_indent(self._indent + 1)))
        ret = _VerboseValueRenderVisitor(source, self._indent + 1, self._parent)
        self.order.append(ret)
        self.order.append(_TextRenderer.new_eol(source, _mk_indent(self._indent)))
        self.order.append(_TextRenderer(")"))
        return ret

    def render_fragments(self, source: Source, *tokens: str) -> None:
        """Render a collection of tokens that make up part of this value."""
        self.order.extend(
            [
                _TextRenderer(t)
                for t in tokens
            ]
        )

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Render a block within the value.

        Currently used only for 'function' declarations.
        """
        ret = _VerboseBlockStartRenderVisitor(source, kind, self._indent, self._parent)
        self.order.append(ret)
        return ret

    def render_string(self, source: Source, str_contents: str) -> None:
        """Constructs a constant string token."""
        self.order.append(_TextRenderer(encode_gs_string(str_contents)))


class _VerboseBlockStartRenderVisitor(BlockStartRenderVisitor, _ListRenders):
    def __init__(self, src: Source, kind: str, indent: int, parent: StatementRenderVisitor) -> None:
        _ListRenders.__init__(self, src)
        self._kind = kind
        self._indent = indent
        self._parent = parent

    def text(self) -> str:
        """Generate the text from the visited statements."""
        str_indent = _mk_indent(self._indent)
        ret = f"\n{str_indent}// {_render_source(self.src)}\n{str_indent}{self._kind}"
        for bit in self.order:
            ret += bit.text()
        ret += f"\n{str_indent}end {self._kind}\n"
        return ret

    def render_sub_value(self, source: Source) -> "ValueRenderVisitor":
        """Render a sub-value."""
        raise NotImplementedError

    def render_fragments(self, source: Source, *tokens: str) -> None:
        """Render a collection of tokens that make up part of this value."""
        self.order.extend([
            _TextRenderer(t)
            for t in tokens
        ])

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Render a block within the value.

        Currently used only for 'function' declarations.
        """
        raise NotImplementedError

    def render_string(self, source: Source, str_contents: str) -> None:
        """Constructs a constant string token."""
        raise NotImplementedError

    def end_start(self, source: Source) -> BlockStatementRenderVisitor:
        """End the start section of the block.

        Rendering of the rest of the block continues with the returned value.
        """
        self.order.append(_TextRenderer("\n"))
        ret = _VerboseBlockStatementRenderVisitor(source, self._indent + 1, self._parent)
        self.order.append(ret)
        return ret


class _VerboseBlockStatementRenderVisitor(BlockStatementRenderVisitor, _ListRenders):
    def __init__(self, src: Source, indent: int, parent: StatementRenderVisitor) -> None:
        _ListRenders.__init__(self, src)
        self._indent = indent
        self._parent = parent

    def text(self) -> str:
        """Generate the text from the visited statements."""
        ret = ""
        for item in self.order:
            ret += item.text()
        return ret

    def render_statement(self, source: Source) -> ValueRenderVisitor:
        """Render a list of script tokens."""
        ret = _VerboseValueRenderVisitor(source, self._indent, self._parent)
        self.order.append(ret)
        return ret

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Begin a block section statement.

        'kind' represents the first keyword of the block and the 'end *' keyword.
        """
        ret = _VerboseBlockStartRenderVisitor(source, kind, self._indent, self._parent)
        self.order.append(ret)
        return ret

    def continue_block(
        self, source: Source, *fragments: str
    ) -> "BlockStartRenderVisitor":
        """Render the 'else' or 'else if' continuation block start.

        If an 'else if' section, then the 'render_sub_value' must be called on the
        condition.
        """
        raise NotImplementedError

    def end_block(self, source: Source) -> StatementRenderVisitor:
        """End the block rendering.

        The parent StatementRenderVisitor should continue use, returned
        by this end call.
        """
        return self._parent


class _TextRenderer(_Renders):
    @staticmethod
    def new_eol(src: Source, indent: str) -> "_TextRenderer":
        """Create an EOL text bit."""
        return _TextRenderer(
            f"  // {_render_source(src)}\n{indent}"
        )

    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        """Render as text"""
        return self._text


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
