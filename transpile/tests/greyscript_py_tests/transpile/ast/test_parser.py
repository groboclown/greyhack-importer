"""Test the module."""

import unittest
from greyscript_py.ast import parser
from greyscript_py.util.problems import Problems
from greyscript_py.util.source import FilePos, Source


class ParserTest(unittest.TestCase):
    """Test the module."""

    def test_basic_all(self) -> None:
        """Test the parser with all types."""
        problems = Problems()
        data = parser.ParseData.new(
            problems=problems,
            data_filename="test-all",
            data_path=(),
            raw={
                "src": {"f": "t1", "sl": 1, "sc": 1, "el": 100, "ec": 1},
                "name": "n",
                "type": "block",
                "statement_list": [

                ],
            }
        )
        self.assertEqual(
            [],
            [repr(p) for p in problems.all],
        )
        self.assertEqual(
            data,
            parser.ParseData(
                data_filename="test-all",
                data_path=[],
                data_source=Source(
                    filename="t1",
                    start=FilePos(line=1, col=1),
                    end=FilePos(line=100, col=1),
                ),
                problems=problems,
                name="n",
                name_list=(),
                string_const="",
                number_const=0,
                node=parser.DataNode(
                    source=Source(
                        filename="t1",
                        start=FilePos(line=1, col=1),
                        end=FilePos(line=100, col=1),
                    ),
                    node_type="block",
                    name="n",
                    name_list=None,
                    name_value_list=None,
                    statement_list=[],
                    value=None,
                    value_list=None,
                    if_else_blocks=None,
                    string_const=None,
                    number_const=None,
                    key_value_pairs=None,
                    present_keys=None,
                    bad_keys=[],
                    unknown_keys=[],
                    node_path=[],
                ),
            ),
        )
