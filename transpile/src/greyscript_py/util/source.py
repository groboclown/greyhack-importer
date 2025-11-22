"""Tracks the source."""

import ast
from typing import NamedTuple


class FilePos(NamedTuple):
    """Location within a file.

    Line and column are 1 based.
    Line MUST be >= 1, column can be 0 if not known.
    """

    line: int
    col: int

    @staticmethod
    def new(line: int, col: int) -> "FilePos":
        """Create a valid, new object."""
        if line <= 0 or col < 0:
            raise ValueError(f"line and column must be > 0 ({line}, {col})")
        return FilePos(line=line, col=col)

    @staticmethod
    def opt(line: int, col: int) -> "FilePos | None":
        """Create a new object, or None if the line or column are invalid."""
        if line <= 0 or col < 0:
            return None
        return FilePos(line=line, col=col+1)

    def __repr__(self) -> str:
        if self.col > 0:
            return f"{self.line},{self.col}"
        return str(self.line)


class Source(NamedTuple):
    """The source of an AST node."""

    filename: str
    start: FilePos | None
    end: FilePos | None

    @staticmethod
    def new(
        filename: str, start_line: int, start_col: int, end_line: int, end_col: int
    ) -> "Source":
        """Create a new source."""
        print(f"Parsing source ({filename}@({start_line},{start_col}):({end_line},{end_col})")
        start = FilePos.opt(start_line, start_col)
        end = FilePos.opt(end_line, end_col)
        if start:
            if end:
                if (start.line == end.line and start.col <= end.col) or (
                    start.line < end.line
                ):
                    return Source(filename=filename, start=start, end=end)
                raise ValueError(
                    f"Invalid source construction ({filename}, {start}, {end})"
                )
            return Source(filename=filename, start=start, end=None)
        if end:
            # Just an end, but no start.
            return Source(filename=filename, start=end, end=None)
        return Source(filename=filename, start=None, end=None)

    @staticmethod
    def from_ast(filename: str, node: ast.AST) -> "Source":
        """Create a new source object."""
        return Source.new(
            filename=filename,
            start_line=getattr(node, "lineno", 0),
            start_col=getattr(node, "col_offset", 0),
            end_line=getattr(node, "end_lineno", 0),
            end_col=getattr(node, "end_col_offset", 0),
        )

    def child_ast(self, node: ast.AST) -> "Source":
        """Create a new source object as a child of this one."""
        return Source.from_ast(self.filename, node)

    def __str__(self) -> str:
        if self.start:
            if self.end:
                return f"{self.filename}@[({self.start}), ({self.end})]"
            return f"{self.filename}@{self.start}"
        return self.filename


class SrcFactory:
    """Handles generating sources."""

    def __init__(self, filename: str) -> None:
        self._filename = filename

    def from_ast(self, node: ast.AST) -> Source:
        """Create a source from a node."""
        return Source.from_ast(self._filename, node)
