"""Parse the AST from a JSON like structure."""

from collections.abc import Sequence
from typing import NamedTuple, Literal

from .basic import (
    GSStatement,
    GSBreak,
    GSContinue,
    GSReturn,
    GSValue,
    GSFunctionCall,
    GSImport,
    GSValueAssignment,
    GSWhileBlock,
    GSConditionStatementsBlock,
    GSForBlock,
    GSIfBlock,
    GSNull,
    GSConstantString,
    GSConstantNumber,
    GSFunctionDef,
    GSVariableRef,
    GSTypeRef,
    GSFunctionRef,
    GSList,
    GSKeyPair,
    GSMap,
    GSBinaryOperation,
    GSUnaryOperation,
)
from ..util.jdata import DictJsonData
from ..util.problems import Problems
from ..util.source import Source


def parse_source(
    filename: str, data: DictJsonData, problems: Problems
) -> Sequence[GSStatement]:
    """Turn the data source into a list of GSStatement objects."""
    return _parse_statements(
        ParseData.new(
            raw=data,
            data_filename=filename,
            data_path=[],
            problems=problems,
        )
    )


NodeKey = Literal[
    "src",
    "type",
    "name",
    "name_list",
    "name_value_list",
    "statement_list",
    "value",
    "value_list",
    "if",
    "str",
    "num",
    "map",
]
NODE_KEY_SRC: NodeKey = "src"
NODE_KEY_TYPE: NodeKey = "type"
NODE_KEY_NAME: NodeKey = "name"
NODE_KEY_NAME_LIST: NodeKey = "name_list"
NODE_KEY_NAME_VALUE_LIST: NodeKey = "name_value_list"
NODE_KEY_VALUE: NodeKey = "value"
NODE_KEY_VALUE_LIST: NodeKey = "value_list"
NODE_KEY_STATEMENT_LIST: NodeKey = "statement_list"
NODE_KEY_IF: NodeKey = "if"
NODE_KEY_STR: NodeKey = "str"
NODE_KEY_NUM: NodeKey = "num"
NODE_KEY_MAP: NodeKey = "map"

StatementNodeType = Literal[
    "break",
    "continue",
    "ret",
    "retval",
    "runcall",
    "import",
    "assign",
    "while",
    "for",
    "if",
    "block",  # special case.
]
StatementNodeTypeNames: set[StatementNodeType] = {
    # Should be a frozenset.
    "break",
    "continue",
    "ret",
    "retval",
    "runcall",
    "import",
    "assign",
    "while",
    "for",
    "if",
    "block",
}
ValueNodeType = Literal[
    "str",
    "num",
    "null",
    "function",
    "var",
    "type",
    "funcref",
    "list",
    "map",
    "valuecall",
    "binary",
    "unary",
]
ValueNodeTypeNames: set[ValueNodeType] = {
    # Should be a frozenset.
    "str",
    "num",
    "null",
    "function",
    "var",
    "type",
    "funcref",
    "list",
    "map",
    "valuecall",
    "binary",
    "unary",
}
UnknownNodeType = Literal["unknown"]
NodeType = StatementNodeType | ValueNodeType


class DataNode(NamedTuple):
    """A node of data, with the possible keys parsed out.

    This globally works due to the fixed data type associated with each key.
    """

    source: Source
    node_type: NodeType | UnknownNodeType
    name: str | None
    name_list: Sequence[str] | None
    name_value_list: Sequence[tuple[str, DictJsonData | None]] | None
    statement_list: Sequence[DictJsonData] | None
    value: DictJsonData | None
    value_list: Sequence[DictJsonData] | None
    if_else_blocks: Sequence[DictJsonData] | None
    string_const: str | None
    number_const: int | float | None
    key_value_pairs: Sequence[tuple[DictJsonData, DictJsonData]] | None
    present_keys: Sequence[NodeKey]
    bad_keys: Sequence[NodeKey | tuple[NodeKey, int]]
    unknown_keys: Sequence[NodeKey]
    node_path: Sequence[str | int]

    @staticmethod
    def new(
        data: DictJsonData, filename: str, node_path: list[str | int]
    ) -> "DataNode":
        """Create a new data node."""

        source = Source(filename=filename, start=None, end=None)
        source_set = False
        node_type: NodeType | UnknownNodeType = "unknown"
        name: str | None = None
        name_list: list[str] | None = None
        name_value_list: list[tuple[str, DictJsonData | None]] | None = None
        statement_list: list[DictJsonData] | None = None
        value: DictJsonData | None = None
        value_list: list[DictJsonData] | None = None
        if_else_blocks: list[DictJsonData] | None = None
        string_const: str | None = None
        number_const: int | float | None = None
        key_value_pairs: list[tuple[DictJsonData, DictJsonData]] | None = None
        present_keys: list[NodeKey] = []
        bad_keys: list[NodeKey | tuple[NodeKey, int]] = []
        unknown_keys: list[NodeKey] = []

        for data_entry in data.items():
            match data_entry:
                case ("src", dict(source_data)):
                    present_keys.append(NODE_KEY_SRC)
                    source_set = True
                    source = Source.new(
                        filename=str(source_data.get("f", filename)),
                        start_line=int(source_data.get("sl", 0)),
                        start_col=int(source_data.get("sc", 0)),
                        end_line=int(source_data.get("el", 0)),
                        end_col=int(source_data.get("ec", 0)),
                    )
                case ("src", _):
                    bad_keys.append(NODE_KEY_SRC)

                case ("type", str(node_type_val)):
                    if (
                        node_type_val in StatementNodeTypeNames
                        or node_type_val in ValueNodeTypeNames
                    ):
                        present_keys.append(NODE_KEY_TYPE)
                        node_type = node_type_val
                    else:
                        bad_keys.append(NODE_KEY_TYPE)
                case ("type", _):
                    bad_keys.append(NODE_KEY_TYPE)

                case ("name", str(name_val)):
                    present_keys.append(NODE_KEY_NAME)
                    name = name_val
                case ("name", _):
                    bad_keys.append(NODE_KEY_NAME)

                case ("name_list", list(name_list_val)):
                    okay = True
                    name_list = []
                    idx = -1
                    for item in name_list_val:
                        idx += 1
                        if isinstance(item, str):
                            name_list.append(item)
                        else:
                            okay = False
                            bad_keys.append((NODE_KEY_NAME_LIST, idx))
                    if okay:
                        present_keys.append(NODE_KEY_NAME_LIST)
                case ("name_list", _):
                    bad_keys.append(NODE_KEY_NAME_LIST)

                case ("name_value_list", list(name_value_list_val)):
                    okay = True
                    name_value_list = []
                    idx = -1
                    for item in name_value_list_val:
                        idx += 1
                        if (
                            isinstance(item, dict)
                            and "name" in item
                            and isinstance(item["name"], str)
                        ):
                            name = str(item["name"])
                            value = item.get("value")
                            if value is None:
                                name_value_list.append((name, None))
                            elif isinstance(value, dict):
                                name_value_list.append((name, value))
                            else:
                                okay = False
                                bad_keys.append((NODE_KEY_NAME_VALUE_LIST, idx))
                        else:
                            okay = False
                            bad_keys.append((NODE_KEY_NAME_VALUE_LIST, idx))
                    if okay:
                        present_keys.append(NODE_KEY_NAME_VALUE_LIST)
                case ("name_value_list", _):
                    bad_keys.append(NODE_KEY_NAME_VALUE_LIST)

                case ("statement_list", list(statement_list_val)):
                    okay = True
                    statement_list = []
                    idx = -1
                    for item in statement_list_val:
                        idx += 1
                        if isinstance(item, dict):
                            statement_list.append(item)
                        else:
                            okay = False
                            bad_keys.append((NODE_KEY_STATEMENT_LIST, idx))
                    if okay:
                        present_keys.append(NODE_KEY_STATEMENT_LIST)
                case ("statement_list", _):
                    bad_keys.append(NODE_KEY_STATEMENT_LIST)

                case ("value", dict(value_val)):
                    present_keys.append(NODE_KEY_VALUE)
                    value = value_val
                case ("value", _):
                    bad_keys.append(NODE_KEY_VALUE)

                case ("value_list", list(value_list_val)):
                    okay = True
                    value_list = []
                    idx = -1
                    for item in value_list_val:
                        idx += 1
                        if isinstance(item, dict):
                            value_list.append(item)
                        else:
                            okay = False
                            bad_keys.append((NODE_KEY_VALUE_LIST, idx))
                    if okay:
                        present_keys.append(NODE_KEY_VALUE_LIST)
                case ("value_list", _):
                    bad_keys.append(NODE_KEY_VALUE_LIST)

                case ("if", list(if_val)):
                    okay = True
                    if_else_blocks = []
                    idx = -1
                    for item in if_val:
                        idx += 1
                        if isinstance(item, dict):
                            if_else_blocks.append(item)
                        else:
                            okay = False
                            bad_keys.append((NODE_KEY_IF, idx))
                    if okay:
                        present_keys.append(NODE_KEY_IF)
                case ("if", _):
                    bad_keys.append(NODE_KEY_IF)

                case ("str", str(string_const_val)):
                    present_keys.append(NODE_KEY_STR)
                    string_const = string_const_val
                case ("str", _):
                    bad_keys.append(NODE_KEY_STR)

                case ("num", int(int_val)):
                    present_keys.append(NODE_KEY_NUM)
                    number_const = int_val
                case ("num", float(float_val)):
                    present_keys.append(NODE_KEY_NUM)
                    number_const = float_val
                case ("num", _):
                    bad_keys.append(NODE_KEY_NUM)

                case ("map", list(map_val)):
                    okay = True
                    key_value_pairs = []
                    idx = -1
                    for item in map_val:
                        idx += 1
                        if (
                            isinstance(item, list)
                            and len(item) == 2
                            and isinstance(item[0], dict)
                            and isinstance(item[1], dict)
                        ):
                            key_value_pairs.append((item[0], item[1]))
                        else:
                            okay = False
                            bad_keys.append((NODE_KEY_MAP, idx))
                    if okay:
                        present_keys.append(NODE_KEY_MAP)
                case ("map", _):
                    bad_keys.append(NODE_KEY_MAP)

                case ("comment" | "$comment", _):
                    pass

                case (key, _):
                    unknown_keys.append(key)

        if not source_set:
            bad_keys.append("src")
        return DataNode(
            source=source,
            node_path=node_path,
            node_type=node_type,
            name=name,
            name_list=name_list,
            name_value_list=name_value_list,
            statement_list=statement_list,
            value=value,
            value_list=value_list,
            if_else_blocks=if_else_blocks,
            string_const=string_const,
            number_const=number_const,
            key_value_pairs=key_value_pairs,
            bad_keys=bad_keys,
            present_keys=present_keys,
            unknown_keys=unknown_keys,
        )

    def expect(self, keys: Sequence[NodeKey]) -> tuple[list[NodeKey], list[NodeKey]]:
        """Return the (expected keys not present, keys present but not in the expected keys)."""
        missing: list[NodeKey] = []
        extra: set[NodeKey] = set(self.present_keys)
        for key in keys:
            if key in extra:
                extra.remove(key)
            else:
                missing.append(key)
        return (missing, list(extra))


class ParseData(NamedTuple):
    """Data block surrounding a parsing context."""

    node: DataNode
    data_filename: str
    data_path: list[NodeKey | int]
    data_source: Source
    problems: Problems
    name: str
    name_list: Sequence[str]
    string_const: str
    number_const: int | float

    @staticmethod
    def new(
        raw: DictJsonData,
        data_filename: str,
        data_path: list[NodeKey | int],
        problems: Problems,
    ) -> "ParseData":
        """Create a new ParseData item with the data node parsed out."""
        source = Source(filename=data_filename, start=None, end=None)
        node = DataNode.new(raw, data_filename, data_path)
        for key in node.bad_keys:
            if isinstance(key, tuple):
                key_path = [*data_path, *key]
            else:
                key_path = [*data_path, key]
            problems.add_err(
                source,
                "INPUT-invalid-ast-format",
                path=key_path,
                reason="bad key contents",
            )
        for key in node.unknown_keys:
            problems.add_err(
                source,
                "INPUT-invalid-ast-format",
                path=[*data_path, key],
                reason="unknown key",
            )
        return ParseData(
            node=node,
            data_source=source,
            data_filename=data_filename,
            data_path=data_path,
            problems=problems,
            name=node.name or "",
            name_list=node.name_list or (),
            string_const=node.string_const or "",
            number_const=0 if node.number_const is None else node.number_const,
        )

    @property
    def statements(self) -> Sequence["ParseData"]:
        """Return the statements."""
        if not self.node.statement_list:
            return ()
        return [
            self.sub(self.node.statement_list[i], [NODE_KEY_STATEMENT_LIST, i])
            for i in range(len(self.node.statement_list))
        ]

    @property
    def value(self) -> "ParseData":
        """Return the value."""
        if not self.node.value:
            # Need something to return.
            return self
        return self.sub(self.node.value, [NODE_KEY_VALUE])

    @property
    def values(self) -> Sequence["ParseData"]:
        """Return the value list."""
        if not self.node.value_list:
            return ()
        return [
            self.sub(self.node.value_list[i], [NODE_KEY_VALUE_LIST, i])
            for i in range(len(self.node.value_list))
        ]

    @property
    def name_value_list(self) -> Sequence[tuple[str, "ParseData | None"]]:
        """Return the name-default value list."""
        if not self.node.name_value_list:
            return ()
        return [
            (
                self.node.name_value_list[i][0],
                (
                    None
                    if self.node.name_value_list[i][1] is None
                    else self.sub(
                        self.node.name_value_list[i][1],
                        [NODE_KEY_NAME_VALUE_LIST, i, 1],
                    )
                ),
            )
            for i in range(len(self.node.name_value_list))
        ]

    @property
    def map(self) -> Sequence[tuple["ParseData", "ParseData"]]:
        """Return the key-value pair list."""
        if not self.node.key_value_pairs:
            return ()
        return [
            (
                self.sub(self.node.key_value_pairs[i][0], [NODE_KEY_MAP, i, 0]),
                self.sub(self.node.key_value_pairs[i][1], [NODE_KEY_MAP, i, 1]),
            )
            for i in range(len(self.node.key_value_pairs))
        ]

    @property
    def if_blocks(self) -> Sequence["ParseData"]:
        """Return the if blocks."""
        if not self.node.if_else_blocks:
            return ()
        return [
            self.sub(self.node.if_else_blocks[i], [NODE_KEY_IF, i])
            for i in range(len(self.node.if_else_blocks))
        ]

    def sub(self, data: DictJsonData, sub_path: list[NodeKey | int]) -> "ParseData":
        """Create a sub-path object."""
        return ParseData.new(
            raw=data,
            data_filename=self.data_filename,
            data_path=[*self.data_path, *sub_path],
            problems=self.problems,
        )

    def expect(self, *keys: NodeKey) -> bool:
        """Expect exactly these keys, and return True if valid, False if invalid.

        This always includes the required 'source' and 'type' keys.
        """
        keys = list({*keys, "source", "type"})
        missing, extra = self.node.expect(keys)
        ret = True
        for key in missing:
            self.add_err(key, f"required for {self.node.node_type}")
            ret = False
        for key in extra:
            self.add_err(key, f"invalid for {self.node.node_type}")
            ret = False
        return ret

    def add_err(
        self, sub_key: NodeKey | int | list[NodeKey | int], reason: str
    ) -> None:
        """Add an error to the problems."""
        path = list(self.data_path)
        if isinstance(sub_key, str | int):
            path.append(sub_key)
        else:
            path.extend(sub_key)
        self.problems.add_err(
            self.data_source,
            "INPUT-invalid-ast-format",
            path=path,
            reason=reason,
        )


def _parse_statements(p_data: ParseData) -> Sequence[GSStatement]:
    """Parse the AST model.

    The 'data' must be a list of statement nodes.
    """
    ret: list[GSStatement] = []
    for n_data in p_data.statements:
        match n_data.node.node_type:
            case "break":
                if n_data.expect():
                    ret.append(GSBreak(src=n_data.node.source))
            case "continue":
                if n_data.expect():
                    ret.append(GSContinue(src=n_data.node.source))
            case "ret":
                if n_data.expect():
                    ret.append(GSReturn(src=n_data.node.source, value=None))
            case "retval":
                if n_data.expect(NODE_KEY_VALUE):
                    ret.append(
                        GSReturn(
                            src=n_data.node.source,
                            value=_parse_value_node(n_data.value),
                        )
                    )
            case "runcall":
                if n_data.expect(NODE_KEY_VALUE_LIST, NODE_KEY_VALUE):
                    ret.append(
                        GSFunctionCall(
                            src=n_data.node.source,
                            func=_parse_value_node(n_data.value),
                            parameters=[_parse_value_node(v) for v in n_data.values],
                        )
                    )
            case "import":
                if n_data.expect(NODE_KEY_STR):
                    ret.append(
                        GSImport(src=n_data.node.source, path=n_data.string_const)
                    )
            case "assign":
                if n_data.expect(NODE_KEY_NAME, NODE_KEY_VALUE):
                    ret.append(
                        GSValueAssignment(
                            src=n_data.node.source,
                            name=n_data.name,
                            value=_parse_value_node(n_data.value),
                        )
                    )
            case "while":
                if n_data.expect(NODE_KEY_VALUE, NODE_KEY_STATEMENT_LIST):
                    ret.append(
                        GSWhileBlock(
                            src=n_data.node.source,
                            block=GSConditionStatementsBlock(
                                src=n_data.node.source,
                                condition=_parse_value_node(n_data.value),
                                statements=_parse_statements(n_data),
                            ),
                        )
                    )
            case "for":
                if n_data.expect(
                    NODE_KEY_NAME, NODE_KEY_VALUE, NODE_KEY_STATEMENT_LIST
                ):
                    ret.append(
                        GSForBlock(
                            src=n_data.node.source,
                            name=n_data.name,
                            value=_parse_value_node(n_data.value),
                            statements=_parse_statements(n_data),
                        )
                    )
            case "if":
                if n_data.expect(NODE_KEY_IF, NODE_KEY_STATEMENT_LIST):
                    # Should also check that if_else_blocks contains at least 1 item.
                    if_else: list[GSConditionStatementsBlock] = []
                    for if_data in n_data.if_blocks:
                        if if_data.expect(NODE_KEY_VALUE, NODE_KEY_STATEMENT_LIST):
                            if_else.append(
                                GSConditionStatementsBlock(
                                    src=if_data.node.source,
                                    condition=_parse_value_node(if_data.value),
                                    statements=_parse_statements(if_data),
                                )
                            )
                    ret.append(
                        GSIfBlock(
                            src=n_data.node.source,
                            if_blocks=if_else,
                            else_statements=_parse_statements(n_data),
                        )
                    )
            case "block":
                if n_data.expect(NODE_KEY_STATEMENT_LIST):
                    ret.extend(n_data.statements)
            case key:
                n_data.add_err([key], "invalid statement type")

    return ret


def _parse_value_node(p_data: ParseData) -> GSValue:
    """Construct a GSValue from the AST model node."""
    match p_data.node.node_type:
        case "str":
            if p_data.expect(NODE_KEY_STR):
                return GSConstantString(
                    src=p_data.node.source, value=p_data.string_const
                )
        case "num":
            if p_data.expect(NODE_KEY_NUM):
                return GSConstantNumber(
                    src=p_data.node.source, value=p_data.number_const
                )
        case "null":
            if p_data.expect():
                return GSNull(src=p_data.node.source)
        case "function":
            if p_data.expect(NODE_KEY_NAME_VALUE_LIST, NODE_KEY_STATEMENT_LIST):
                return GSFunctionDef(
                    src=p_data.node.source,
                    parameter_pairs=p_data.name_value_list,
                    statements=_parse_statements(p_data),
                )
        case "var":
            if p_data.expect(NODE_KEY_NAME):
                return GSVariableRef(src=p_data.node.source, name=p_data.name)
        case "type":
            if p_data.expect(NODE_KEY_NAME):
                return GSTypeRef(src=p_data.node.source, name=p_data.name)
        case "funcref":
            if p_data.expect(NODE_KEY_NAME):
                return GSFunctionRef(src=p_data.node.source, name=p_data.name)
        case "list":
            if p_data.expect(NODE_KEY_VALUE_LIST):
                return GSList(
                    src=p_data.node.source,
                    items=[_parse_value_node(n) for n in p_data.values],
                )
        case "map":
            if p_data.expect(NODE_KEY_MAP):
                return GSMap(
                    src=p_data.node.source,
                    items=[
                        GSKeyPair(
                            src=p_data.node.source,
                            key=_parse_value_node(k),
                            value=_parse_value_node(v),
                        )
                        for k, v in p_data.map
                    ],
                )
        case "valuecall":
            if p_data.expect(NODE_KEY_VALUE, NODE_KEY_VALUE_LIST):
                return GSFunctionCall(
                    src=p_data.node.source,
                    func=_parse_value_node(p_data.value),
                    parameters=[_parse_value_node(v) for v in p_data.values],
                )
        case "binary":
            if p_data.expect(NODE_KEY_NAME, NODE_KEY_VALUE_LIST):
                values = p_data.values
                if len(values) != 2:
                    p_data.add_err(
                        NODE_KEY_VALUE_LIST,
                        "binary operations require exactly 2 values in the list",
                    )
                else:
                    return GSBinaryOperation(
                        src=p_data.node.source,
                        operator=p_data.name,
                        left=values[0],
                        right=values[1],
                    )
        case "unary":
            if p_data.expect(NODE_KEY_NAME, NODE_KEY_VALUE):
                return GSUnaryOperation(
                    src=p_data.node.source,
                    operator=p_data.name,
                    value=p_data.value,
                )
        case key:
            p_data.add_err(NODE_KEY_TYPE, f"unsupported value type {key}")
    # Fallback for an invalid value.
    return GSNull(src=p_data.node.source)
