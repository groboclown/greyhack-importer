"""Perform the rendering visitation."""

from .abc import (
    StatementRenderVisitor,
    ValueRenderVisitor,
    BlockStatementRenderVisitor,
)
from ..ast import basic


def render_block(
        block: basic.GSBlock, visitor: StatementRenderVisitor
) -> None:
    """Pass the block through the visitor."""
    for stmt in block.statements:
        render_statement(stmt, visitor)


def render_statement(
    statement: basic.GSStatement, visitor: StatementRenderVisitor
) -> None:
    """Pass the statement through the visitor."""
    match statement:
        case basic.GSValueAssignment(src=src, name=name, value=value):
            srv = visitor.render_statement(src)
            srv.render_fragments(src, name, "=")
            render_value(value, srv.render_sub_value(src))
        case basic.GSFunctionCall(src=src, func=f_c_func, parameters=f_c_params):
            # There has GOT to be a better way to do this.
            render_value(
                basic.GSFunctionCall(src=src, func=f_c_func, parameters=f_c_params),
                visitor.render_statement(src),
            )
        case basic.GSReturn(src=src, value=ret_s):
            srv = visitor.render_statement(src)
            srv.render_fragments(src, "return")
            if ret_s is not None:
                render_value(ret_s, srv.render_sub_value(src))
        case basic.GSBreak(src=src):
            srv = visitor.render_statement(src)
            srv.render_fragments(src, "break")
        case basic.GSContinue(src=src):
            srv = visitor.render_statement(src)
            srv.render_fragments(src, "continue")
        case basic.GSImport(src=src, path=imp):
            srv = visitor.render_statement(src)
            # Format is very precise here.
            srv.render_fragments(src, "import", "(")
            srv.render_string(src, imp)
            srv.render_fragments(src, ")")
        case basic.GSBlock(src=_src, statements=b_s):
            for stmt in b_s:
                render_statement(stmt, visitor)
        case basic.GSWhileBlock(src=src, block=w_s):
            block_start = visitor.render_block(src, "while")
            render_value(w_s.condition, block_start.render_sub_value(src))
            block_statements = block_start.end_start(src)
            for statement in w_s.statements:
                render_statement(statement, block_statements)
            block_statements.end_block(src)
        case basic.GSForBlock(src=src, name=for_s_name, value=for_s_value, statements=for_s_stmts):
            block_start = visitor.render_block(src, "for")
            block_start.render_fragments(src, for_s_name, "=")
            render_value(for_s_value, block_start.render_sub_value(src))
            block_statements = block_start.end_start(src)
            for statement in for_s_stmts:
                render_statement(statement, block_statements)
            block_statements.end_block(src)
        case basic.GSIfBlock(src=src, if_blocks=i_s_if_blocks, else_statements=i_s_else_stmts):
            block_start = visitor.render_block(src, "if")
            n_block_statements: BlockStatementRenderVisitor | None = None
            first = True
            for condition_section in i_s_if_blocks:
                if first:
                    first = False
                else:
                    assert n_block_statements is not None
                    block_start = n_block_statements.continue_block(
                        condition_section.src, "else", "if"
                    )
                render_value(condition_section.condition, block_start)
                block_statements = block_start.end_start(condition_section.src)
                for statement in condition_section.statements:
                    render_statement(statement, block_statements)

            assert n_block_statements is not None
            if i_s_else_stmts:
                n_block_statements.continue_block(src, "else")
                for statement in i_s_else_stmts.statements:
                    render_statement(statement, n_block_statements)
            n_block_statements.end_block(src)
        case other:
            raise ValueError(f"invalid block type {other}")


def render_value(value: basic.GSValue, visitor: ValueRenderVisitor) -> None:
    """Pass the value through the visitor."""
    match value:
        case basic.GSConstantNumber(src=src, value=n_v):
            visitor.render_fragments(src, str(n_v))
        case basic.GSConstantString(src=src, value=s_v):
            visitor.render_string(src, s_v)
        case basic.GSFunctionDef(src=src, parameter_pairs=fd_pp, statements=fd_stmts):
            block_start = visitor.render_block(src, "function")
            first = True
            # Wrapping parenthesis after the 'function' declaration are optional if
            # there are no parameters, similar to a function call having an optional "(" wrapper.
            for name, default in fd_pp:
                if first:
                    first = False
                    block_start.render_fragments(src, "(")
                else:
                    block_start.render_fragments(src, ",")
                block_start.render_fragments(src, name)
                if default:
                    block_start.render_fragments(default.src, "=")
                    render_value(default, block_start.render_sub_value(default.src))
            if not first:
                block_start.render_fragments(src, ")")
            block_statements = block_start.end_start(src)
            for statement in fd_stmts.statements:
                render_statement(statement, block_statements)
            block_statements.end_block(src)
        case basic.GSNull(src=src):
            visitor.render_fragments(src, "null")
        case basic.GSMap(src=src, items=m_v):
            visitor.render_fragments(src, "{")
            first = True
            for pair in m_v:
                if first:
                    first = False
                else:
                    visitor.render_fragments(pair.src, ",")
                render_value(pair.key, visitor.render_sub_value(pair.key.src))
                visitor.render_fragments(pair.src, ":")
                render_value(pair.value, visitor.render_sub_value(pair.value.src))
            visitor.render_fragments(src, "}")
        case basic.GSList(src=src, items=l_v):
            visitor.render_fragments(src, "[")
            first = True
            for item in l_v:
                if first:
                    first = False
                else:
                    visitor.render_fragments(item.src, ",")
                render_value(item, visitor.render_sub_value(item.src))
            visitor.render_fragments(src, "]")
        case basic.GSVariableRef(src=src, name=r_v) | basic.GSTypeRef(src=src, name=r_v):
            visitor.render_fragments(src, r_v)
        case basic.GSFunctionRef(src=src, name=fr_v):
            visitor.render_fragments(src, "@", fr_v)
        case basic.GSFunctionCall(src=src, func=fc_name, parameters=fc_parms):
            render_value(fc_name, visitor.render_sub_value(src))
            # Here, the () wrap is optional.  The renderer should add them
            # if there is a fragment between open and close.
            visitor.render_fragments(src, "(")
            first = True
            for param in fc_parms:
                if first:
                    first = False
                else:
                    visitor.render_fragments(src, ",")
                render_value(param, visitor.render_sub_value(src))
            visitor.render_fragments(src, ")")
        case basic.GSBinaryOperation(src=src, left=b_l, right=b_r, operator=b_o):
            render_value(b_l, visitor.render_sub_value(src))
            visitor.render_fragments(src, b_o)
            render_value(b_r, visitor.render_sub_value(src))
        case basic.GSUnaryOperation(src=src, value=u_v, operator=u_o):
            visitor.render_fragments(src, u_o)
            render_value(u_v, visitor.render_sub_value(src))
        case other:
            raise ValueError(f"invalid value type {other}")
