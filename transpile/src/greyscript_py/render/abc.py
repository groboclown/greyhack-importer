"""Abstract base classes."""

from ..util.source import Source


class ValueRenderVisitor:
    """Visits the construction of a statement.

    Intended to be used within a 'with' block.
    """

    def render_sub_value(self, source: Source) -> "ValueRenderVisitor":
        """Render a sub-value."""
        raise NotImplementedError

    def render_fragments(self, source: Source, *tokens: str) -> None:
        """Render a collection of tokens that make up part of this value."""
        raise NotImplementedError

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Render a block within the value.

        Currently used only for 'function' declarations.
        """
        raise NotImplementedError

    def render_string(self, source: Source, str_contents: str) -> None:
        """Constructs a constant string token."""
        raise NotImplementedError


class StatementRenderVisitor:
    """Visits the rendering section.

    The visitor must ast either a statement block, or a statement.
    """

    def render_statement(self, source: Source) -> ValueRenderVisitor:
        """Render a list of script tokens."""
        raise NotImplementedError

    def render_block(self, source: Source, kind: str) -> "BlockStartRenderVisitor":
        """Begin a block section statement.

        'kind' represents the first keyword of the block and the 'end *' keyword.
        """
        raise NotImplementedError


class BlockStatementRenderVisitor(StatementRenderVisitor):
    """Visits the start part of a block."""

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
        raise NotImplementedError


class BlockStartRenderVisitor(ValueRenderVisitor):
    """Visits the start part of a block."""

    def end_start(self, source: Source) -> BlockStatementRenderVisitor:
        """End the start section of the block.

        Rendering of the rest of the block continues with the returned value.
        """
        raise NotImplementedError
