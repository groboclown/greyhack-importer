"""Turn the AST into a JSON file."""

from . import basic
from ..util.jdata import DictJsonData, ListJsonData
from ..util.source import Source


def to_json(ast: basic.GSBlock) -> DictJsonData:
    """Convert the top-level AST block into a JSON data."""
    return _from_GSBlock(ast)


def _from_GSBlock(ast: basic.GSBlock) -> DictJsonData:
    """Convert the GSBlock."""
    statements: ListJsonData = []
    for statement in ast.statements:
        statements.append(_from_GSElement(statement))
    return {
        "src": _from_Source(ast.src),
        "type": "block",
        "statement_list": statements,
    }


def _from_GSFunctionDef(ast: basic.GSFunctionDef) -> DictJsonData:
    """Convert the GSFunctionDef into a JSON data."""
    return {
        "src": _from_Source(ast.src),
        "type": "function",
        "name_value_list": [
            {"name": n[0], "value": _from_GSElement(n[1])} for n in ast.parameter_pairs
        ],
        "statement_list": [_from_GSElement(s) for s in ast.statements.statements],
    }


def _from_GSFunctionRef(ast: basic.GSFunctionRef) -> DictJsonData:
    """Convert the GSFunctionRef into a JSON data."""
    return {
        "src": _from_Source(ast.src),
        "type": "funcref",
        "name": ast.name,
    }


def _from_GSElement(ast: basic.GSElement | None) -> DictJsonData | None:
    """Convert the Statement into a JSON data."""
    if ast is None:
        return None
    if isinstance(ast, basic.GSConstantString):
        return _from_GSConstantString(ast)
    if isinstance(ast, basic.GSConstantNumber):
        return _from_GSConstantNumber(ast)
    if isinstance(ast, basic.GSNull):
        return _from_GSNull(ast)
    if isinstance(ast, basic.GSBlock):
        return _from_GSBlock(ast)
    if isinstance(ast, basic.GSFunctionDef):
        return _from_GSFunctionDef(ast)
    if isinstance(ast, basic.GSFunctionRef):
        return _from_GSFunctionRef(ast)
    if isinstance(ast, basic.GSTypeRef):
        return _from_GSTypeRef(ast)
    if isinstance(ast, basic.GSVariableRef):
        return _from_GSVariableRef(ast)
    if isinstance(ast, basic.GSList):
        return _from_GSList(ast)
    if isinstance(ast, basic.GSKeyPair):
        return _from_GSKeyPair(ast)
    if isinstance(ast, basic.GSMap):
        return _from_GSMap(ast)
    if isinstance(ast, basic.GSMemberReference):
        return _from_GSMemberReference(ast)
    if isinstance(ast, basic.GSBinaryOperation):
        return _from_GSBinaryOperation(ast)
    if isinstance(ast, basic.GSUnaryOperation):
        return _from_GSUnaryOperation(ast)
    if isinstance(ast, basic.GSFunctionCall):
        return _from_GSFunctionCall(ast)
    if isinstance(ast, basic.GSValueAssignment):
        return _from_GSValueAssignment(ast)
    if isinstance(ast, basic.GSReturn):
        return _from_GSReturn(ast)
    if isinstance(ast, basic.GSBreak):
        return _from_GSBreak(ast)
    if isinstance(ast, basic.GSContinue):
        return _from_GSContinue(ast)
    if isinstance(ast, basic.GSImport):
        return _from_GSImport(ast)
    if isinstance(ast, basic.GSConditionStatementsBlock):
        return _from_GSConditionStatementsBlock(ast)
    if isinstance(ast, basic.GSWhileBlock):
        return _from_GSWhileBlock(ast)
    if isinstance(ast, basic.GSForBlock):
        return _from_GSForBlock(ast)
    if isinstance(ast, basic.GSIfBlock):
        return _from_GSIfBlock(ast)
    raise NotImplementedError(repr(ast))


def _from_GSConstantString(ast: basic.GSConstantString) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "str",
        "str": ast.value,
    }


def _from_GSConstantNumber(ast: basic.GSConstantNumber) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "num",
        "num": ast.value,
    }


def _from_GSVariableRef(ast: basic.GSVariableRef) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "var",
        "name": ast.name,
    }


def _from_GSBinaryOperation(ast: basic.GSBinaryOperation) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "binary",
        "name": ast.operator,
        "value_list": [
            _from_GSElement(ast.left),
            _from_GSElement(ast.right),
        ],
    }


def _from_GSFunctionCall(ast: basic.GSFunctionCall) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "runcall",
        "value": _from_GSElement(ast.func),
        "value_list": [_from_GSElement(v) for v in ast.parameters],
    }


def _from_GSValueAssignment(ast: basic.GSValueAssignment) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "assign",
        "name": ast.name,
        "value": _from_GSElement(ast.value),
    }


def _from_GSReturn(ast: basic.GSReturn) -> DictJsonData:
    if ast.value is None:
        return {
            "src": _from_Source(ast.src),
            "type": "ret",
        }
    return {
        "src": _from_Source(ast.src),
        "type": "retval",
        "value": _from_GSElement(ast.value),
    }


def _from_Source(src: Source) -> DictJsonData:
    start_line = 0
    start_col = 0
    end_line = 0
    end_col = 0
    if src.start:
        start_line = src.start.line
        start_col = src.start.col
    if src.end:
        end_line = src.end.line
        end_col = src.end.col
    return {
        "f": src.filename,
        "sl": start_line,
        "sc": start_col,
        "el": end_line,
        "ec": end_col,
    }
