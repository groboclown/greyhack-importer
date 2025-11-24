"""Handles Python AST nodes converted to GreyHack scripts."""

import ast
from collections.abc import Sequence
from typing import Literal, Generic, TypeVar

from . import value_context as vax, builder
from .built_ins import create_base_context, load_greyhack_module
from ..ast import basic
from ..util.problems import Problems
from ..util.source import Source

T = TypeVar("T", bound=basic.GSElement)

MODULE_GREYHACK = "greyhack"
GREYHACK_CONTENTS = load_greyhack_module()


class BaseVisitor(ast.NodeVisitor, Generic[T]):
    """Base visitor for modules and functions.

    Functions and modules both can contain the same information.
    """

    def __init__(self, src: Source, problems: Problems) -> None:
        self._src = src
        self._probs = problems
        self._has_problems = True

    def finalize(self) -> T | None:
        """Finalize the GSElement."""
        raise NotImplementedError

    def generic_visit(self, node: ast.AST) -> None:
        """Visitor for unhandled types."""
        print(f"{self._src}: unhandled visit({node}) from {self}")
        self._probs.add_err(
            self._src.child_ast(node),
            "BUG-python-structure",
            ast_from=str(type(self._src)),
            ast_type=str(type(ast)),
        )


Operators = Literal[
    "+", "-", "*", "/", "@", "%", "**", "<<", ">>", "|", "^", "&", "//", "(unknown)"
]
Context = Literal["load", "store", "del", "(unknown)"]
ComparisonOpr = Literal[
    "==", "!=", "<", "<=", ">", ">=", "is", "is not", "in", "not in", "(unknown)"
]


class ValueVisitor(BaseVisitor[basic.GSValue]):
    """Visits a code expression.

    ast.Expr contains an expression value.
    """

    @staticmethod
    def handle(
        parent: BaseVisitor, expr: ast.Expr | ast.expr, context: vax.ValueContext
    ) -> "ValueVisitor":
        """Handle this expression."""
        ret = ValueVisitor(
            parent=parent._src, expr=expr, problems=parent._probs, context=context
        )
        if isinstance(expr, ast.Expr) and hasattr(expr, "value"):
            ret.visit(expr.value)
        else:
            ret.visit(expr)
        return ret

    def __init__(
        self,
        parent: Source,
        expr: ast.Expr | ast.expr,
        context: vax.ValueContext,
        problems: Problems,
    ) -> None:
        BaseVisitor.__init__(self, parent.child_ast(expr), problems)
        self.context = context
        self.value: builder.PyGsBuilder[basic.GSValue] | None = None

    def finalize(self) -> T | None:
        """Finalize the GSElement."""
        if self._has_problems:
            return None
        if self.value is None:
            self._probs.add_err(self._src, "BUG-value-not-set")
            self._has_problems = True
            return None
        return self.value.build(self._probs)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit an attribute of an object."""
        print(f"ValueVisitor.visit_Attribute({node})")
        self._one(node)
        build = builder.TwoArgumentBuilder.new_member_ref(self._src.child_ast(node))
        build.left = ValueVisitor.handle(self, node.value, self.context).value
        build.right = builder.StaticBuilder(
            basic.GSConstantString(src=self._src.child_ast(node), value=str(node.value))
        )
        self.value = build

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Visit a binary operation."""
        print(f"ValueVisitor.visit_BinOp({node})")
        self._one(node)
        opr: Operators
        if isinstance(node.op, ast.Add):
            opr = "+"
        elif isinstance(node.op, ast.Sub):
            opr = "-"
        elif isinstance(node.op, ast.Mult):
            opr = "*"
        elif isinstance(node.op, ast.MatMult):
            opr = "@"
        elif isinstance(node.op, ast.Div):
            opr = "/"
        elif isinstance(node.op, ast.Mod):
            opr = "%"
        elif isinstance(node.op, ast.Pow):
            opr = "**"
        elif isinstance(node.op, ast.LShift):
            opr = "<<"
        elif isinstance(node.op, ast.RShift):
            opr = ">>"
        elif isinstance(node.op, ast.BitOr):
            opr = "|"
        elif isinstance(node.op, ast.BitXor):
            opr = "^"
        elif isinstance(node.op, ast.BitAnd):
            opr = "&"
        elif isinstance(node.op, ast.FloorDiv):
            opr = "//"
        else:
            self._probs.add_err(
                self._src.child_ast(node),
                "INPUT-invalid-python-use",
                text=ast.unparse(node),
            )
            opr = "(unknown)"
        build = builder.TwoArgumentBuilder.new_binary(self._src.child_ast(node), opr)
        build.left = ValueVisitor.handle(self, node.left, self.context).value
        build.right = ValueVisitor.handle(self, node.right, self.context).value
        self.value = build

    def visit_Call(self, node: ast.Call) -> None:
        """Visit a call."""
        print(f"ValueVisitor.visit_Call({node})")
        self._one(node)
        build = builder.CallBuilder(
            src=self._src.child_ast(node),
            context=self.context,
        )
        build.func = ValueVisitor.handle(self, node.func, self.context).value
        for arg in node.args:
            arg_val = ValueVisitor.handle(self, arg, self.context).value
            if arg_val:
                build.position_arguments.append(arg_val)
            else:
                build.position_arguments.append(
                    builder.ErrorBuilder(
                        self._src,
                        "BAD_ARG",
                        argument=repr(arg),
                        key=None,
                    )
                )
        for keyword in node.keywords:
            arg_val = ValueVisitor.handle(self, keyword.value, self.context).value
            if arg_val:
                kwarg = arg_val
            else:
                kwarg = builder.ErrorBuilder(
                    self._src,
                    "BAD_ARG",
                    argument=repr(keyword.value),
                    key=keyword.arg,
                )
            if keyword.arg is None:
                build.position_arguments.append(kwarg)
            else:
                build.named_arguments[str(keyword.arg)] = kwarg

        self.value = build

    def visit_Compare(self, node: ast.Compare) -> None:
        """Visit a comparison."""
        print(f"ValueVisitor.visit_Compare({node})")
        self._one(node)
        comparators: list[tuple[ComparisonOpr, ValueVisitor]] = []
        if len(node.comparators) != len(node.ops):
            raise AssertionError(
                f"expected comparators count ({node.comparators}) "
                f"== operator count ({node.ops})"
            )
        for i in range(len(node.comparators)):
            n_o = node.ops[i]
            opr: ComparisonOpr
            if isinstance(n_o, ast.Eq):
                opr = "=="
            elif isinstance(n_o, ast.NotEq):
                opr = "!="
            elif isinstance(n_o, ast.Lt):
                opr = "<"
            elif isinstance(n_o, ast.LtE):
                opr = "<="
            elif isinstance(n_o, ast.Gt):
                opr = ">"
            elif isinstance(n_o, ast.GtE):
                opr = ">="
            elif isinstance(n_o, ast.Is):
                opr = "is"
            elif isinstance(n_o, ast.IsNot):
                opr = "is not"
            elif isinstance(n_o, ast.In):
                opr = "in"
            elif isinstance(n_o, ast.NotIn):
                opr = "not in"
            else:
                self._probs.add_err(
                    self._src.child_ast(node),
                    "INPUT-invalid-python-use",
                    text=ast.unparse(node),
                )
                opr = "(unknown)"

            comparators.append(
                (opr, ValueVisitor.handle(self, node.comparators[i], self.context))
            )
        self.value = ComparisonExpr(
            left=ValueVisitor.handle(self, node.left),
            comparators=comparators,
        )

    def visit_Constant(self, node: ast.Constant) -> None:
        """Visit a constant."""
        print(f"ValueVisitor.visit_Constant({node})")
        src = self._src.child_ast(node)
        self._one(node)
        if node.value == Ellipsis or isinstance(node.value, complex):
            self.value = builder.ErrorBuilder(
                src,
                "INPUT-invalid-python-use",
                text=ast.unparse(node),
            )
            return
        if node.value is None:
            self.value = builder.StaticBuilder(basic.GSNull(src=src))
            return
        if isinstance(node.value, bool):
            self.value = builder.StaticBuilder(
                basic.GSConstantNumber(
                    src=src,
                    value=False if node.value == 0 else True,
                )
            )
            return
        if isinstance(node.value, int | float):
            self.value = builder.StaticBuilder(
                basic.GSConstantNumber(
                    src=src,
                    value=node.value,
                )
            )
            return
        if isinstance(node.value, str | bytes):
            self.value = builder.StaticBuilder(
                basic.GSConstantString(
                    src=src,
                    value=str(node.value),
                )
            )
            return

        self._probs.add_err(
            src,
            "INPUT-invalid-python-use",
            text=ast.unparse(node),
        )

    def visit_Name(self, node: ast.Name) -> None:
        """Visit a name."""
        print(f"ValueVisitor.visit_Name({node})")
        self._one(node)
        # Don't know if this is a
        # variable or function or other reference.
        self.value = builder.VariableBuilder(
            src=self._src.child_ast(node),
            name=str(node.id),
            context=self.context,
        )

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Visit an f-string."""
        print(f"ValueVisitor.visit_JoinedStr({node})")
        src = self._src.child_ast(node)
        # This adds an extra do-nothing at the end, but that's fine.
        self.value = builder.StaticBuilder(basic.GSConstantString(src=src, value=""))
        for val in node.values:
            el_src = self._src.child_ast(val)
            next_el: builder.PyGsBuilder[basic.GSValue] | None = None
            if isinstance(val, ast.Constant):
                # Note: a bit of a duplicate of visit_Constant above.
                if val.value == Ellipsis:
                    next_el = builder.StaticBuilder(
                        basic.GSConstantString(el_src, "...")
                    )
                elif isinstance(val.value, complex):
                    next_el = builder.StaticBuilder(
                        basic.GSConstantString(
                            el_src, f"({val.value.real} + {val.value.imag}i)"
                        )
                    )
                elif val.value is None:
                    next_el = builder.StaticBuilder(basic.GSNull(el_src))
                elif isinstance(val.value, bool):
                    next_el = builder.StaticBuilder(
                        basic.GSConstantNumber(
                            el_src, False if val.value == 0 else True
                        )
                    )
                elif isinstance(val.value, int | float):
                    next_el = builder.StaticBuilder(
                        basic.GSConstantNumber(el_src, val.value)
                    )
                elif isinstance(val.value, str | bytes):
                    next_el = builder.StaticBuilder(
                        basic.GSConstantString(el_src, str(val.value))
                    )
            elif isinstance(val, ast.FormattedValue):
                if val.format_spec:
                    self._probs.add_err(
                        el_src,
                        "BAD-USAGE-unhandled-format-in-f-string",
                        spec=repr(val.format_spec),
                    )
                next_el = ValueVisitor.handle(self, val.value, self.context).value
            else:
                self._probs.add_err(
                    el_src,
                    "BAD-USAGE-unhandled-value-in-f-string",
                    spec=repr(val),
                )
            joiner = builder.TwoArgumentBuilder.new_binary(el_src, "+")
            joiner.left = self.value
            joiner.right = next_el
            self.value = joiner

    def _one(self, node: ast.AST) -> None:
        """Ensure only one node present."""
        if self.value is not None:
            self._probs.add_err(
                self._src.child_ast(node),
                "BUG-python-structure",
                ast_from=str(type(self.value)),
                ast_type=str(type(node)),
            )
        self.value_source = self._src.child_ast(node)


class BlockVisitor(BaseVisitor[basic.GSBlock]):
    """Visits a block of statements."""

    @staticmethod
    def handle(
        parent: BaseVisitor, expr: Sequence[ast.stmt], context: vax.ValueContext
    ) -> builder.BlockBuilder:
        """Handle this expression."""
        vis = BlockVisitor(src=parent._src, problems=parent._probs, context=context)
        for statement in expr:
            vis.visit(statement)
        return builder.BlockBuilder(src=vis._src, statements=vis.statements)

    def __init__(
        self, src: Source, context: vax.ValueContext, problems: Problems
    ) -> None:
        BaseVisitor.__init__(self, src, problems)
        self.statements: list[builder.PyGsBuilder[basic.GSStatement]] = []
        self.context = context

    def finalize(self) -> basic.GSBlock | None:
        """Finalize the GSElement."""
        statements: list[basic.GSStatement] = []
        is_ok = True
        for stmt_builder in self.statements:
            stmt = stmt_builder.build(self._probs)
            if stmt is None:
                is_ok = False
            else:
                # Python-ism: if a statement is just a constant string, then it's a document string
                # and can be ignored.
                if not isinstance(stmt, basic.GSConstantString):
                    statements.append(stmt)
        if not is_ok:
            return None
        return basic.GSBlock(src=self._src, statements=statements)

    def visit_Expr(self, node: ast.Expr) -> None:
        """Visit an expression."""
        print(f"BlockVisitor.visit_Expr({node})")
        visitor = ValueVisitor.handle(self, node, self.context)
        if visitor.value:
            self.statements.append(visitor.value)

    def visit_Return(self, node: ast.Return) -> None:
        """Visit a return statement."""
        print(f"BlockVisitor.visit_Return({node})")
        src = self._src.child_ast(node)
        if node.value is not None:
            build = builder.OneArgumentBuilder.new_return_value(src)
            build.argument = ValueVisitor.handle(self, node.value, self.context).value
            self.statements.append(build)
        else:
            self.statements.append(
                builder.StaticBuilder(basic.GSReturn(src=src, value=None))
            )

    def visit_If(self, node: ast.If) -> None:
        """Visit an If block."""
        print(f"BlockVisitor.visit_If({node})")
        body = BlockVisitor(
            self._src.child_ast(node), self.context.enter(), self._probs
        )
        for body_node in node.body:
            body.visit(body_node)
        or_else: BlockVisitor | None = None
        if node.orelse:
            or_else = BlockVisitor(
                self._src.child_ast(node), self.context.enter(), self._probs
            )
            for or_else_node in node.orelse:
                or_else.visit(or_else_node)
        self.statements.append(
            basic.GSIfBlock(
                test=ValueVisitor.handle(self, node.test),
                body=body,
                or_else=or_else,
            )
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit an Assign block."""
        print(f"BlockVisitor.visit_Assign({node})")
        src = self._src.child_ast(node)
        if len(node.targets) != 1:
            self._probs.add_err(
                src,
                "Value assignment only allows one target value currently.",
            )
            return
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            self._probs.add_err(
                src,
                "Value assignment only allows name target.",
            )
            return
        gs_var = basic.GSVariableRef(src=src, name=target.id)
        self.context.add(
            src, target.id, vax.VariableValue(target.id, "func"), self._probs
        )
        build = builder.TwoArgumentBuilder.new_assign(src)
        build.left = builder.StaticBuilder(gs_var)
        build.right = ValueVisitor.handle(self, node.value, self.context).value
        self.statements.append(build)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a FunctionDef block."""
        print(f"BlockVisitor.visit_FunctionDef({node})")
        src = self._src.child_ast(node)
        if node.decorator_list:
            self._probs.add_err(src, "ERROR-bad-usage-decorator", name=node.name)
        gs_callable = basic.GSFunctionRef(src=src, name=node.name)
        ctx_args: list[vax.Argument] = []
        gs_args: list[tuple[str, basic.GSValue | None]] = []
        # node.args contains all the argument stuff in Python.
        # Only a subset are currently supported.
        #  - args: list of normal, named arguments (ast.arg)
        #  - defaults: list of ?
        #  - kw_defaults: list of ?
        #  - kwarg: ?
        #  - kwonlyargs: list of ?
        #  - posonlyargs: list of ? (arguments after '/').
        #  - vararg: ?
        for idx in range(len(node.args.args)):
            node_arg = node.args.args[idx]
            # arg_type: str | None = None
            # if node_arg.annotation:
            #    arg_type = node_arg.annotation.id
            # Can also look at type_comment for the comment's type declaration.
            arg_name = node_arg.arg
            # These don't have default values.
            ctx_args.append(vax.Argument(arg_name, idx, None))
            gs_args.append((arg_name, None))
        # FIXME handle others.
        ctx_callable = vax.FuncValue(
            source_name=node.name, value=gs_callable, arguments=ctx_args
        )
        # GS has functions definitions marked as value assignments.
        # This is now callable to other things within this block, and to inside the body.
        self.context.add(src, node.name, ctx_callable, self._probs)

        body = builder.OneArgumentBuilder.new_function_def(src, gs_args)
        body.argument = BlockVisitor.handle(self, node.body, self.context)

        build = builder.TwoArgumentBuilder.new_assign(src)
        build.left = builder.StaticBuilder(gs_callable)
        build.right = body
        self.statements.append(build)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit a simple import."""
        print(f"BlockVisitor.visit_Import({node})")
        for name in node.names:
            self._import((name.name,), name.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit a "from ... import ..." statement"""
        print(f"BlockVisitor.visit_ImportFrom({node})")
        for name in node.names:
            self._import((*node.module.split("."), name.name), name.asname)

    def _import(self, name: Sequence[str], as_name: str) -> None:
        """Import the name as a name (possibly the same)."""
        if name[0] == MODULE_GREYHACK:
            item, problems = vax.get(GREYHACK_CONTENTS.contents, name[1:])
            self._probs.add_from(problems)
            if item is not None:
                self.context.add(as_name, item)


class ClassVisitor(BaseVisitor):
    """Visits a class object."""


class LambdaVisitor:
    """Visits a lambda expression."""


class ConstantVisitor:
    """Visits a constant value."""


class ModuleVisitor(BlockVisitor):
    """Receives Python top-level module events."""

    def __init__(self, src: Source, problems: Problems, module_name: str) -> None:
        BlockVisitor.__init__(
            self,
            src=src,
            context=create_base_context(),
            problems=problems,
        )
        self.module_name = module_name


class FunctionVisitor(BlockVisitor):
    """Receives Python function events."""

    def __init__(self, func_name: str, func_args: list[str]) -> None:
        BlockVisitor.__init__(self)
        self.func_name = func_name
        self.func_args = func_args

    def visit_FunctionType(self, node: ast.FunctionType) -> None:
        """Visit old-style type comments for a function."""


def _as_ctx(
    ctx: ast.expr_context, parent: Source, node: ast.AST, probs: Problems
) -> Context:
    """Convert to an internal expression context."""
    if isinstance(ctx, ast.Load):
        return "load"
    elif isinstance(ctx, ast.Store):
        return "store"
    elif isinstance(ctx, ast.Del):
        return "del"
    probs.add_err(
        parent.child_ast(node),
        "INPUT-invalid-python-use",
        text=ast.unparse(node),
    )
    return "(unknown)"


"""
class ExampleVisitor(ast.NodeVisitor):
    "Used for examples."
    def generic_visit(self, node: AST) -> Any: ...
    def visit_Module(self, node: Module) -> Any: ...
    def visit_Interactive(self, node: Interactive) -> Any: ...
    def visit_Expression(self, node: Expression) -> Any: ...
    def visit_FunctionDef(self, node: FunctionDef) -> Any: ...
    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Any: ...
    def visit_ClassDef(self, node: ClassDef) -> Any: ...
    def visit_Return(self, node: Return) -> Any: ...
    def visit_Delete(self, node: Delete) -> Any: ...
    def visit_Assign(self, node: Assign) -> Any: ...
    def visit_AugAssign(self, node: AugAssign) -> Any: ...
    def visit_AnnAssign(self, node: AnnAssign) -> Any: ...
    def visit_For(self, node: For) -> Any: ...
    def visit_AsyncFor(self, node: AsyncFor) -> Any: ...
    def visit_While(self, node: While) -> Any: ...
    def visit_If(self, node: If) -> Any: ...
    def visit_With(self, node: With) -> Any: ...
    def visit_AsyncWith(self, node: AsyncWith) -> Any: ...
    def visit_Raise(self, node: Raise) -> Any: ...
    def visit_Try(self, node: Try) -> Any: ...
    def visit_Assert(self, node: Assert) -> Any: ...
    def visit_Import(self, node: Import) -> Any: ...
    def visit_ImportFrom(self, node: ImportFrom) -> Any: ...
    def visit_Global(self, node: Global) -> Any: ...
    def visit_Nonlocal(self, node: Nonlocal) -> Any: ...
    def visit_Expr(self, node: Expr) -> Any: ...
    def visit_Pass(self, node: Pass) -> Any: ...
    def visit_Break(self, node: Break) -> Any: ...
    def visit_Continue(self, node: Continue) -> Any: ...
    def visit_Slice(self, node: Slice) -> Any: ...
    def visit_BoolOp(self, node: BoolOp) -> Any: ...
    def visit_BinOp(self, node: BinOp) -> Any: ...
    def visit_UnaryOp(self, node: UnaryOp) -> Any: ...
    def visit_Lambda(self, node: Lambda) -> Any: ...
    def visit_IfExp(self, node: IfExp) -> Any: ...
    def visit_Dict(self, node: Dict) -> Any: ...
    def visit_Set(self, node: Set) -> Any: ...
    def visit_ListComp(self, node: ListComp) -> Any: ...
    def visit_SetComp(self, node: SetComp) -> Any: ...
    def visit_DictComp(self, node: DictComp) -> Any: ...
    def visit_GeneratorExp(self, node: GeneratorExp) -> Any: ...
    def visit_Await(self, node: Await) -> Any: ...
    def visit_Yield(self, node: Yield) -> Any: ...
    def visit_YieldFrom(self, node: YieldFrom) -> Any: ...
    def visit_Compare(self, node: Compare) -> Any: ...
    def visit_Call(self, node: Call) -> Any: ...
    def visit_FormattedValue(self, node: FormattedValue) -> Any: ...
    def visit_JoinedStr(self, node: JoinedStr) -> Any: ...
    def visit_Constant(self, node: Constant) -> Any: ...
    def visit_NamedExpr(self, node: NamedExpr) -> Any: ...
    def visit_TypeIgnore(self, node: TypeIgnore) -> Any: ...
    def visit_Attribute(self, node: Attribute) -> Any: ...
    def visit_Subscript(self, node: Subscript) -> Any: ...
    def visit_Starred(self, node: Starred) -> Any: ...
    def visit_Name(self, node: Name) -> Any: ...
    def visit_List(self, node: List) -> Any: ...
    def visit_Tuple(self, node: Tuple) -> Any: ...
    def visit_Del(self, node: Del) -> Any: ...
    def visit_Load(self, node: Load) -> Any: ...
    def visit_Store(self, node: Store) -> Any: ...
    def visit_And(self, node: And) -> Any: ...
    def visit_Or(self, node: Or) -> Any: ...
    def visit_Add(self, node: Add) -> Any: ...
    def visit_BitAnd(self, node: BitAnd) -> Any: ...
    def visit_BitOr(self, node: BitOr) -> Any: ...
    def visit_BitXor(self, node: BitXor) -> Any: ...
    def visit_Div(self, node: Div) -> Any: ...
    def visit_FloorDiv(self, node: FloorDiv) -> Any: ...
    def visit_LShift(self, node: LShift) -> Any: ...
    def visit_Mod(self, node: Mod) -> Any: ...
    def visit_Mult(self, node: Mult) -> Any: ...
    def visit_MatMult(self, node: MatMult) -> Any: ...
    def visit_Pow(self, node: Pow) -> Any: ...
    def visit_RShift(self, node: RShift) -> Any: ...
    def visit_Sub(self, node: Sub) -> Any: ...
    def visit_Invert(self, node: Invert) -> Any: ...
    def visit_Not(self, node: Not) -> Any: ...
    def visit_UAdd(self, node: UAdd) -> Any: ...
    def visit_USub(self, node: USub) -> Any: ...
    def visit_Eq(self, node: Eq) -> Any: ...
    def visit_Gt(self, node: Gt) -> Any: ...
    def visit_GtE(self, node: GtE) -> Any: ...
    def visit_In(self, node: In) -> Any: ...
    def visit_Is(self, node: Is) -> Any: ...
    def visit_IsNot(self, node: IsNot) -> Any: ...
    def visit_Lt(self, node: Lt) -> Any: ...
    def visit_LtE(self, node: LtE) -> Any: ...
    def visit_NotEq(self, node: NotEq) -> Any: ...
    def visit_NotIn(self, node: NotIn) -> Any: ...
    def visit_comprehension(self, node: comprehension) -> Any: ...
    def visit_ExceptHandler(self, node: ExceptHandler) -> Any: ...
    def visit_arguments(self, node: arguments) -> Any: ...
    def visit_arg(self, node: arg) -> Any: ...
    def visit_keyword(self, node: keyword) -> Any: ...
    def visit_alias(self, node: alias) -> Any: ...
    def visit_withitem(self, node: withitem) -> Any: ...

    def visit_Match(self, node: Match) -> Any: ...
    def visit_match_case(self, node: match_case) -> Any: ...
    def visit_MatchValue(self, node: MatchValue) -> Any: ...
    def visit_MatchSequence(self, node: MatchSequence) -> Any: ...
    def visit_MatchSingleton(self, node: MatchSingleton) -> Any: ...
    def visit_MatchStar(self, node: MatchStar) -> Any: ...
    def visit_MatchMapping(self, node: MatchMapping) -> Any: ...
    def visit_MatchClass(self, node: MatchClass) -> Any: ...
    def visit_MatchAs(self, node: MatchAs) -> Any: ...
    def visit_MatchOr(self, node: MatchOr) -> Any: ...

    def visit_TryStar(self, node: TryStar) -> Any: ...

    def visit_TypeVar(self, node: TypeVar) -> Any: ...
    def visit_ParamSpec(self, node: ParamSpec) -> Any: ...
    def visit_TypeVarTuple(self, node: TypeVarTuple) -> Any: ...
    def visit_TypeAlias(self, node: TypeAlias) -> Any: ...

    # visit methods for deprecated nodes
    def visit_ExtSlice(self, node: ExtSlice) -> Any: ...
    def visit_Index(self, node: Index) -> Any: ...
    def visit_Suite(self, node: Suite) -> Any: ...
    def visit_AugLoad(self, node: AugLoad) -> Any: ...
    def visit_AugStore(self, node: AugStore) -> Any: ...
    def visit_Param(self, node: Param) -> Any: ...
"""
