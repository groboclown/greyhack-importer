"""Test the module."""

import os
import tempfile
import unittest

from greyscript_py.ast import basic
from greyscript_py.py import ast_handler
from greyscript_py.util.source import Source, FilePos


class AstHandlerTest(unittest.TestCase):
    """Test the functions."""

    def test_visit_file(self) -> None:
        """Test the visit_file function."""
        with open(self.tmp, "w", encoding="utf-8") as inp:
            inp.write("x = 1 + 2")
        script = ast_handler.visit_file(self.tmp)
        self.assertEqual(
            script.root.src.filename,
            self.tmp,
        )
        self.assertEqual(
            script.problems.all,
            [],
        )
        self.assertEqual(
            basic.GSBlock(
                src=Source(filename=self.tmp, start=None, end=None),
                statements=[
                    basic.GSValueAssignment(
                        src=Source(filename=self.tmp, start=FilePos(1, 1), end=FilePos(1, 10)),
                        name="x",
                        value=basic.GSBinaryOperation(
                            src=Source(filename=self.tmp, start=FilePos(1, 5), end=FilePos(1, 10)),
                            operator="+",
                            left=basic.GSConstantNumber(
                                src=Source(filename=self.tmp, start=FilePos(1, 5), end=FilePos(1, 6)),
                                value=1,
                            ),
                            right=basic.GSConstantNumber(
                                src=Source(filename=self.tmp, start=FilePos(1, 9), end=FilePos(1, 10)),
                                value=2,
                            ),
                        ),
                    )
                ],
            ),
            script.root,
        )

    def setUp(self) -> None:
        """Set up the test resources."""
        fd, name = tempfile.mkstemp()
        os.close(fd)
        self.tmp = name

    def tearDown(self) -> None:
        """Tear down test resources."""
        if self.tmp and os.path.exists(self.tmp):
            os.unlink(self.tmp)
