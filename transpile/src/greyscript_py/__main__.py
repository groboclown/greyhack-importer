"""CLI entrypoint."""

import sys

# Temporary for testing.
from greyscript_py.py.ast_handler import visit_file

print(visit_file(sys.argv[1]))
