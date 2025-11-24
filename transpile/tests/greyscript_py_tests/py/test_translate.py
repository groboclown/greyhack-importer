"""Test translation of different kinds of Python code."""

import importlib.resources
import json
import os
import shutil
import tempfile
import unittest

from greyscript_py.ast.parser import parse_source
from greyscript_py.ast.writer import to_json
from greyscript_py.py import ast_handler
from greyscript_py.render.verbose import VerboseRenderer
from greyscript_py.render.visit import render_block
from greyscript_py.util.problems import Problems
from . import data as data_dir


class TranslateTest(unittest.TestCase):
    """Test different data."""

    def test_all(self) -> None:
        """Test all the data."""
        for name in _load("index.list").splitlines():
            name = name.strip()
            if not name or name[0] == "#":
                continue
            with self.subTest(name=name):
                try:
                    self.run_one(name)
                except AssertionError as err:
                    raise err
                except BaseException as err:
                    self.fail(err)

    def test_quick(self) -> None:
        """Debug one test explicitly."""
        # self.run_one("value_assignment_000")
        # self.run_one("value_assignment_001")
        self.run_one("func_def_call_000")

    def run_one(self, name: str) -> None:
        """Run one test."""
        py_code = _load(f"{name}.py")
        gs_expected = _load(f"{name}.gs")
        raw_ast_expected = json.loads(_load(f"{name}.json"))
        problems = Problems()
        ast_expected = parse_source("f", raw_ast_expected, problems)
        self.assertEqual(problems.all, [])
        script = ast_handler.visit_file_text("f", py_code)
        renderer = VerboseRenderer(script.root.src)
        render_block(script.root, renderer)
        with self.subTest(name=f"{name}.problems"):
            self.assertEqual(
                [],
                list(script.problems.errors),
            )
        print("Found: " + json.dumps(to_json(script.root), indent=2))
        with self.subTest(name=f"{name}.json"):
            self.assertEqual(
                json.dumps(raw_ast_expected, indent=2),
                json.dumps(to_json(script.root), indent=2),
            )
        with self.subTest(name=f"{name}.ast"):
            self.assertEqual(
                ast_expected,
                script.root,
            )
        with self.subTest(name=f"{name}.gs"):
            text = renderer.text()
            print(text)
            self.assertEqual(
                gs_expected,
                text,
            )

    def setUp(self) -> None:
        """Set up the test resources."""
        name = tempfile.mkdtemp()
        self.tmp = name

    def tearDown(self) -> None:
        """Tear down test resources."""
        if self.tmp and os.path.exists(self.tmp):
            shutil.rmtree(self.tmp)


def _load(name: str) -> str:
    """Load the named resource."""
    data = importlib.resources.files(data_dir) / name
    with data.open("r", encoding="utf-8") as inp:
        return inp.read()
