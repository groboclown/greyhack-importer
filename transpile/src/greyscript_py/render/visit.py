"""Perform the rendering visitation."""

from greyscript_py.ast import basic
from greyscript_py.render.abc import (
    StatementRenderVisitor,
    ValueRenderVisitor,
    BlockStatementRenderVisitor,
)


def render_statement(
    statement: basic.GSStatement, visitor: StatementRenderVisitor
) -> None:
    """Pass the statement through the visitor."""
    match statement:
        case basic.GSValueAssignment(v_a):
            srv = visitor.render_statement(v_a.src)
            srv.render_fragments(v_a.src, v_a.name, "=")
            render_value(v_a.value, srv.render_sub_value(v_a.src))
        case basic.GSFunctionCall(f_c):
            render_value(f_c, visitor.render_statement(f_c.src))
        case basic.GSReturn(ret_s):
            srv = visitor.render_statement(ret_s.src)
            srv.render_fragments(ret_s.src, "return")
            if ret_s.value is not None:
                render_value(ret_s.value, srv.render_sub_value(ret_s.src))
        case basic.GSBreak(b_s):
            srv = visitor.render_statement(b_s.src)
            srv.render_fragments(b_s.src, "break")
        case basic.GSContinue(c_s):
            srv = visitor.render_statement(c_s.src)
            srv.render_fragments(c_s.src, "continue")
        case basic.GSImport(imp):
            srv = visitor.render_statement(imp.src)
            # Format is very precise here.
            srv.render_fragments(imp.src, "import", "(")
            srv.render_string(imp.src, imp.path)
            srv.render_fragments(imp.src, ")")
        case basic.GSWhileBlock(w_s):
            block_start = visitor.render_block(w_s.src, "while")
            render_value(w_s.block.condition, block_start.render_sub_value(w_s.src))
            block_statements = block_start.end_start(w_s.src)
            for statement in w_s.block.statements:
                render_statement(statement, block_statements)
            block_statements.end_block(w_s.src)
        case basic.GSForBlock(for_s):
            block_start = visitor.render_block(for_s.src, "for")
            block_start.render_fragments(for_s.src, for_s.name, "=")
            render_value(for_s.value, block_start.render_sub_value(for_s.src))
            block_statements = block_start.end_start(for_s.src)
            for statement in for_s.statements:
                render_statement(statement, block_statements)
            block_statements.end_block(for_s.src)
        case basic.GSIfBlock(i_s):
            block_start = visitor.render_block(i_s.src, "if")
            block_statements: BlockStatementRenderVisitor | None = None
            first = True
            for condition_section in i_s.if_blocks:
                if first:
                    first = False
                else:
                    assert block_statements is not None
                    block_start = block_statements.continue_block(
                        condition_section.src, "else", "if"
                    )
                render_value(condition_section, block_start)
                block_statements = block_start.end_start(condition_section.src)
                for statement in condition_section.statements:
                    render_statement(statement, block_statements)

            assert block_statements is not None
            if i_s.else_statements:
                block_statements.continue_block(i_s.src, "else")
                for statement in i_s.else_statements.statements:
                    render_statement(statement, block_statements)
            block_statements.end_block(i_s.src)
        case other:
            raise ValueError(f"invalid block type {other}")


def render_value(value: basic.GSValue, visitor: ValueRenderVisitor) -> None:
    """Pass the value through the visitor."""
    match value:
        case basic.GSConstantNumber(n_v):
            visitor.render_fragments(n_v.src, str(n_v.value))
        case basic.GSConstantString(s_v):
            visitor.render_string(s_v.src, s_v.value)
        case basic.GSFunctionDef(fd_v):
            block_start = visitor.render_block(fd_v.src, "function")
            first = True
            # Wrapping parenthesis after the 'function' declaration are optional if
            # there are no parameters, similar to a function call having an optional "(" wrapper.
            for name, default in fd_v.parameter_pairs:
                if first:
                    first = False
                    block_start.render_fragments(fd_v.src, "(")
                else:
                    block_start.render_fragments(fd_v.src, ",")
                block_start.render_fragments(fd_v.src, name)
                if default:
                    block_start.render_fragments(default.src, "=")
                    render_value(default, block_start.render_sub_value(default.src))
            if not first:
                block_start.render_fragments(fd_v.src, ")")
            block_statements = block_start.end_start(fd_v.src)
            for statement in fd_v.statements:
                render_statement(statement, block_statements)
            block_statements.end_block(fd_v.src)
        case basic.GSNull(nul_v):
            visitor.render_fragments(nul_v.src, "null")
        case basic.GSMap(m_v):
            visitor.render_fragments(m_v.src, "{")
            first = True
            for pair in m_v.items:
                if first:
                    first = False
                else:
                    visitor.render_fragments(pair.src, ",")
                render_value(pair.key, visitor.render_sub_value(pair.key.src))
                visitor.render_fragments(pair.src, ":")
                render_value(pair.value, visitor.render_sub_value(pair.value.src))
            visitor.render_fragments(m_v.src, "}")
        case basic.GSList(l_v):
            visitor.render_fragments(l_v.src, "[")
            first = True
            for item in l_v.items:
                if first:
                    first = False
                else:
                    visitor.render_fragments(item.src, ",")
                render_value(item, visitor.render_sub_value(item.src))
            visitor.render_fragments(l_v.src, "]")
        case basic.GSVariableRef(r_v) | basic.GSTypeRef(r_v):
            visitor.render_fragments(r_v.src, r_v.name)
        case basic.GSFunctionRef(fr_v):
            visitor.render_fragments(fr_v.src, "@", fr_v.name)
        case basic.GSFunctionCall(fc_v):
            render_value(fc_v.func, visitor.render_sub_value(fc_v.src))
            # Here, the () wrap is optional.  The renderer should add them
            # if there is a fragment between open and close.
            visitor.render_fragments(fc_v.src, "(")
            first = True
            for param in fc_v.parameters:
                if first:
                    first = False
                else:
                    visitor.render_fragments(fc_v.src, ",")
                render_value(param, visitor.render_sub_value(fc_v.src))
            visitor.render_fragments(fc_v.src, ")")
        case basic.GSBinaryOperation(b_v):
            render_value(b_v.left, visitor.render_sub_value(b_v.src))
            visitor.render_fragments(b_v.src, b_v.operator)
            render_value(b_v.right, visitor.render_sub_value(b_v.src))
        case basic.GSUnaryOperation(u_v):
            visitor.render_fragments(u_v.src, u_v.operator)
            render_value(u_v.value, visitor.render_sub_value(u_v.src))
        case other:
            raise ValueError(f"invalid value type {other}")
