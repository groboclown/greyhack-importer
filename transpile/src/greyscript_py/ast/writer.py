"""Turn the AST into a JSON file."""

from . import basic
from ..util.jdata import DictJsonData, ListJsonData, JsonData
from ..util.source import Source


def to_json(ast: basic.GSBlock) -> DictJsonData:
    """Convert the top-level AST block into a JSON data."""
    return _from_GSBlock(ast)


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
    # if isinstance(ast, basic.GSKeyPair): Not a stand-alone item
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
    # if isinstance(ast, basic.GSConditionStatementsBlock): Not a stand-alone item
    if isinstance(ast, basic.GSWhileBlock):
        return _from_GSWhileBlock(ast)
    if isinstance(ast, basic.GSForBlock):
        return _from_GSForBlock(ast)
    if isinstance(ast, basic.GSIfBlock):
        return _from_GSIfBlock(ast)
    raise NotImplementedError(repr(ast))


def _from_GSBlock(ast: basic.GSBlock) -> DictJsonData:
    statements: list[JsonData] = []
    for statement in ast.statements:
        statements.append(_from_GSElement(statement))
    return {
        "src": _from_Source(ast.src),
        "type": "block",
        "statement_list": statements,
    }


def _from_GSFunctionDef(ast: basic.GSFunctionDef) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "function",
        "name_value_list": [
            {"name": n[0], "value": _from_GSElement(n[1])} for n in ast.parameter_pairs
        ],
        "statement_list": [_from_GSElement(s) for s in ast.statements.statements],
    }


def _from_GSFunctionRef(ast: basic.GSFunctionRef) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "funcref",
        "name": ast.name,
    }


def _from_GSTypeRef(ast: basic.GSTypeRef) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "type",
        "name": ast.name,
    }


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


def _from_GSNull(ast: basic.GSNull) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "null",
    }


def _from_GSVariableRef(ast: basic.GSVariableRef) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "var",
        "name": ast.name,
    }


def _from_GSList(ast: basic.GSList) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "list",
        "value_list": [_from_GSElement(e) for e in ast.items],
    }


def _from_GSMap(ast: basic.GSMap) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "map",
        "map": [[_from_GSElement(p.key), _from_GSElement(p.value)] for p in ast.items],
    }


def _from_GSMemberReference(ast: basic.GSMemberReference) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "memref",
        "value": _from_GSElement(ast.value),
        "name": ast.member,
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


def _from_GSUnaryOperation(ast: basic.GSUnaryOperation) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "unary",
        "name": ast.operator,
        "value": _from_GSElement(ast.value),
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


def _from_GSBreak(ast: basic.GSBreak) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "break",
    }


def _from_GSContinue(ast: basic.GSContinue) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "continue",
    }


def _from_GSImport(ast: basic.GSImport) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "import",
        "str": ast.path,
    }


def _from_GSWhileBlock(ast: basic.GSWhileBlock) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "while",
        "value": _from_GSElement(ast.block.condition),
        "statement_list": [_from_GSElement(s) for s in ast.block.statements],
    }


def _from_GSForBlock(ast: basic.GSForBlock) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "for",
        "value": _from_GSElement(ast.value),
        "statement_list": [_from_GSElement(s) for s in ast.statements.statements],
    }


def _from_GSIfBlock(ast: basic.GSIfBlock) -> DictJsonData:
    return {
        "src": _from_Source(ast.src),
        "type": "if",
        # if_blocks
        "if": [
            {
                "value": _from_GSElement(s.condition),
                "statement_list": [_from_GSElement(b) for b in s.statements.statements],
            }
            for s in ast.if_blocks
        ],
        "statement_list": [_from_GSElement(s) for s in ast.else_statements.statements],
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
