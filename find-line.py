#!/usr/bin/python

"""Given a main program and a line number, it will use that
line number as an absolute line, and scan through the import_code statements
to find the corresponding real file number.

This is useful if you're trying to build a file in Grey Hack that has
many imports, but the file fails to build due to a syntax problem.
The game will only report that the main program failed, and will
treat the import_code statements like the file is expanded in-place.
"""

from typing import Tuple, List, Optional
import os
import sys
import re

CONTEXT_LINES = 5
IMPORT_RE = re.compile(r'^\s*import_code\s*\(\s*"([^"]+)"\s*\)\s*$')


def read_file(
    filename: str, current_line: List[int]
) -> List[Tuple[str, int, int, str]]:
    """Read the file."""
    parent = os.path.dirname(filename)
    ret: List[Tuple[str, int, int, str]] = []
    orig_lineno = 1
    with open(filename, "r", encoding="utf-8") as fis:
        for line in fis.readlines():
            line = line.rstrip()
            ret.append((filename, current_line[0], orig_lineno, line))
            current_line[0] += 1
            orig_lineno += 1
            mtc = IMPORT_RE.match(line)
            if mtc is not None:
                imported = os.path.join(parent, mtc.group(1))
                ret.extend(read_file(imported, current_line))
    return ret


def find_lineno(filename: str, lineno: Optional[int]) -> None:
    """Find the line number in the main file, following imports."""
    all_lines = read_file(filename, [1])
    min_line = 0 if lineno is None else lineno - CONTEXT_LINES
    max_line = 0 if lineno is None else lineno + CONTEXT_LINES
    for src_file, global_lineno, src_lineno, src_line in all_lines:
        if lineno is None or (min_line <= global_lineno <= max_line):
            print(f"[{src_file}:{src_lineno}] {global_lineno}  {src_line}")


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv or len(sys.argv) not in (2, 3):
        print("Usage: find-line.py (main filename) (linenumber in question)")
        print("Use to help you find the original line number through all your imports.")
        sys.exit(1)
    if len(sys.argv) == 2:
        findl = None
    else:
        findl = int(sys.argv[2])
    find_lineno(sys.argv[1], findl)
