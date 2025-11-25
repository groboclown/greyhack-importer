"""Mock renderer for testing."""

from types import TracebackType
from typing import NamedTuple

from greyscript_py.util.source import Source
from transpile.transform import RenderVisitor, StatementRenderVisitor


class CapturedToken(NamedTuple):
    """A token captured by the renderer."""

    tok: str
    src: Source


class CapturedStatement(NamedTuple):
    """A statement captured by the renderer."""

    indent: int
    src: Source
    tokens: list[CapturedToken]


class MockRenderVisitor(RenderVisitor):
    """Testable, top-level version of a ast visitor."""

    def __init__(self) -> None:
        self.statements: list[CapturedStatement] = []

    def simple(self) -> list[list[str]]:
        """Turn the rendered statements into a list of statements.

        Each statement consists of a list of token strings.
        """
        ret: list[list[str]] = []
        for stmt in self.statements:
            ret.append([t.tok for t in stmt.tokens])
        return ret

    def render_statement(self, source: Source) -> StatementRenderVisitor:
        """Render a list of script tokens."""
        return MockStatementRenderVisitor(
            indent=0,
            source=source,
            statements=self.statements,
        )

    def render_block(
        self,
        source: Source,
        start_tokens: list[str],
        end_tokens: list[str],
    ) -> "RenderVisitor":
        """Used in a 'with' statement to return a visitor for use within the block."""
        return MockBlockVisitor(
            indent=0,
            source=source,
            start=start_tokens,
            end=end_tokens,
            statements=self.statements,
        )


class MockBlockVisitor(RenderVisitor):
    """Inner block version of a visitor."""

    def __init__(
        self,
        *,
        indent: int,
        source: Source,
        start: list[str],
        end: list[str],
        statements: list[CapturedStatement],
    ) -> None:
        self._indent = indent
        self._start = CapturedStatement(
            indent=indent,
            src=source,
            tokens=[CapturedToken(tok=t, src=source) for t in start],
        )
        self._end = CapturedStatement(
            indent=indent,
            src=source,
            tokens=[CapturedToken(tok=t, src=source) for t in end],
        )
        self._statements = statements
        self._inner: list[CapturedStatement] = []

    def render_statement(self, source: Source) -> StatementRenderVisitor:
        """Render a list of script tokens."""
        return MockStatementRenderVisitor(
            indent=self._indent + 1,
            source=source,
            statements=self._inner,
        )

    def render_block(
        self,
        source: Source,
        start_tokens: list[str],
        end_tokens: list[str],
    ) -> "RenderVisitor":
        """Used in a 'with' statement to return a visitor for use within the block."""
        return MockBlockVisitor(
            indent=self._indent + 1,
            source=source,
            start=start_tokens,
            end=end_tokens,
            statements=self._inner,
        )

    def __enter__(self) -> "RenderVisitor":
        return self

    def __exit__(
        self,
        type_: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if value is not None:
            raise value
        self._statements.append(self._start)
        self._statements.extend(self._inner)
        self._statements.append(self._end)
        return None


class MockStatementRenderVisitor(StatementRenderVisitor):
    """A statement renderer visitor."""

    def __init__(
        self,
        *,
        indent: int,
        source: Source,
        statements: list[CapturedStatement],
    ) -> None:
        self._indent = indent
        self._source = source
        self._fragments: list[CapturedToken] = []
        self._statements = statements

    def render_fragments(self, source: Source, *tokens: str) -> None:
        """Render a collection of tokens that make up part of a statement."""
        self._fragments.extend([CapturedToken(tok=t, src=source) for t in tokens])

    def __enter__(self) -> "StatementRenderVisitor":
        return self

    def __exit__(
        self,
        type_: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if value:
            raise value
        self._statements.append(
            CapturedStatement(
                indent=self._indent,
                src=self._source,
                tokens=self._fragments,
            )
        )
        return None
