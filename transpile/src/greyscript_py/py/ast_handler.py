"""Handle a Python AST."""

import ast
import os
from typing import NamedTuple

from .visitor import ModuleVisitor
from ..ast import basic
from ..util.problems import Problems
from ..util.source import SrcFactory, Source


class ScriptFile(NamedTuple):
    """The parsed script."""

    root: basic.GSBlock
    problems: Problems


def visit_parsed_file(filename: str, code: ast.AST) -> ScriptFile:
    """Visit a single Python file."""
    problems = Problems()
    src = SrcFactory(filename)
    statements: list[basic.GSStatement] = []

    print(f"Parsing {code}")

    if isinstance(code, ast.Module):
        assert isinstance(code, ast.AST)  # nosec  # for mypy
        base_name = os.path.basename(filename)
        if "." in base_name:
            base_name = base_name[:base_name.rindex(".")]
        vis = ModuleVisitor(
            src=src.from_ast(code),
            problems=problems,
            module_name=base_name,
        )
        for item in code.body:
            print(f"Visiting {item}")
            vis.visit(item)
        statements.extend(vis.statements)
        print(f"Added {len(statements)} statements")
    else:
        problems.add_err(src.from_ast(code), "BUG-parse-file", ast_type=str(type(code)))

    root = basic.GSBlock(
        src=Source.from_ast(filename, code),
        statements=statements,
    )
    return ScriptFile(root=root, problems=problems)


def visit_file(filename: str) -> ScriptFile:
    """Visit the Python file."""

    with open(filename, "r", encoding="utf-8") as fis:
        return visit_parsed_file(
            filename,
            ast.parse(
                source=fis.read(),
                filename=filename,
                mode="exec",
            ),
        )
