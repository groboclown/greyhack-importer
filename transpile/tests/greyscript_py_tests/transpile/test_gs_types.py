"""Module tests."""

import unittest

from greyscript_py.util.source import Source
from .renderer import MockRenderVisitor


class GsTypesTest(unittest.TestCase):
    """Tests for the module."""

    def test_encode_gs_string(self) -> None:
        """Test the encode_gs_string function."""
        tests = [
            ("", '""'),
            ("hi!", '"hi!"'),
            ('Let\'s all say, "Hello!"', '"Let\'s all say, ""Hello!"""'),
        ]
        for inp, exp in tests:
            with self.subTest(inp):
                self.assertEqual(exp, gs_types.encode_gs_string(inp))

    def test_simple_reference_render(self) -> None:
        """Test the GSSimpleReference ast function."""
        tests: list[
            tuple[
                tuple[gs_types.GSSimpleType, int | float | str | bool | None],
                list[list[str]],
            ]
        ] = [
            (
                ("null", None),
                ([["null"]]),
            ),
            (
                ("boolean", True),
                ([["1"]]),
            ),
            (
                ("boolean", False),
                ([["0"]]),
            ),
            (
                ("number", 1.664),
                ([["1.664"]]),
            ),
            (
                ("string", 'foo " me'),
                ([['"foo "" me"']]),
            ),
            (
                ("function", "call_func"),
                ([["@call_func"]]),
            ),
            (
                ("type", "string"),
                ([["string"]]),
            ),
        ]
        for imp, exp in tests:
            src = Source(filename="f", lineno=1, column=1)
            with self.subTest(repr(imp)):
                renderer = MockRenderVisitor()
                with renderer.render_statement(src) as rend:
                    gs_types.GSSimpleReference(
                        source=src, gs_type=imp[0], value=imp[1]
                    ).render(rend)
                self.assertEqual(renderer.simple(), exp)
