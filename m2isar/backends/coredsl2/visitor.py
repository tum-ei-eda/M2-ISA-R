# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Visitor-pattern based printer for instruction/function  behavior."""

import logging
from functools import singledispatchmethod

from ...metamodel import arch, behav, type_info, attribute_info
from ...metamodel.utils.ExprVisitor import ExprVisitor


logger = logging.getLogger("coredsl2_writer")


# pylint: disable=unused-argument


class CDSLWriterVisitor(ExprVisitor):
    """Visitor to validate a metamodel."""

    def generate_grouped(self, expr, writer):
        if isinstance(expr, behav.Group):
            self.generate(expr, writer)
        else:
            writer.write("(")
            self.generate(expr, writer)
            writer.write(")")

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context):
        raise NotImplementedError(
            f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}"
        )

    @generate.register
    def _(self, expr: behav.Operation, writer):
        if len(expr.statements) > 1:
            writer.enter_block()
        for stmt in expr.statements:
            self.generate(stmt, writer)
            if not isinstance(stmt, (behav.Conditional, behav.LoopBase, behav.Operation, behav.Break, behav.Continue)):
                writer.write_line(";")
        if len(expr.statements) > 1:
            writer.leave_block()

    @generate.register
    def _(self, expr: behav.Block, writer):
        writer.enter_attributed_block(expr.attributes)
        for stmt in expr.statements:
            self.generate(stmt, writer)
            if not isinstance(stmt, (behav.Conditional, behav.LoopBase, behav.Operation, behav.Break, behav.Continue)):
                writer.write_line(";")
        writer.leave_block()

    @generate.register
    def _(self, expr: behav.BinaryOperation, writer):
        self.generate_grouped(expr.left, writer)
        writer.write(f" {expr.op.value} ")
        self.generate_grouped(expr.right, writer)

    @generate.register
    def _(self, expr: behav.SliceOperation, writer):
        self.generate(expr.expr, writer)
        writer.write("[")
        self.generate_grouped(expr.left, writer)
        writer.write(":")
        self.generate_grouped(expr.right, writer)
        writer.write("]")

    @generate.register
    def _(self, expr: behav.ConcatOperation, writer):
        # TODO: only add () where required
        self.generate_grouped(expr.left, writer)
        writer.write(" :: ")
        self.generate_grouped(expr.right, writer)

    @generate.register
    def _(self, expr: behav.Literal, writer):
        writer.write(expr.value)

    @generate.register
    def _(self, expr: behav.Tensor, writer):
        writer.write_array(expr.value)

    @generate.register
    def _(self, expr: behav.VarDefinition, writer):
        # TODO: add const attribute?
        static_attr = expr.var.attributes.get("static")
        is_const = static_attr == attribute_info.AccessAttribute.READ
        if is_const:
            writer.write("const ")
        if isinstance(expr.var.ty, type_info.ArrayType):
            writer.write_type(expr.var.ty.element_type)
            writer.write(" ")
            writer.write(expr.var.name)
            length = arch.get_const_or_val(expr.var.ty.length)
            writer.write(f"[{length}]")
        else:
            writer.write_type(expr.var.ty)
            writer.write(" ")
            writer.write(expr.var.name)
        if expr.var.value:
            writer.write(" = ")
            writer.write(expr.var.value)
        # writer.write_line(";")

    @generate.register
    def _(self, expr: behav.Break, writer):
        writer.write_line("break;")

    @generate.register
    def _(self, expr: behav.Continue, writer):
        writer.write_line("continue;")

    @generate.register
    def _(self, expr: behav.Assignment, writer):
        self.generate(expr.target, writer)
        operator = getattr(expr, 'compound_operator', None)
        if operator and isinstance(expr.expr, behav.BinaryOperation):
            writer.write(" " + operator + " ")
            self.generate(expr.expr.right, writer)
        else:
            writer.write(" = ")
            self.generate(expr.expr, writer)
        # writer.write_line(";")

    @generate.register
    def _(self, expr: behav.Conditional, writer):
        for i, stmt in enumerate(expr.stmts):
            if i == 0:
                writer.write("if (")
                self.generate(expr.conds[i], writer)
                writer.write(")")
            elif 0 < i < len(expr.conds):
                writer.write("else if(")
                self.generate(expr.conds[i], writer)
                writer.write(")")
            else:
                writer.write("else")
            nl = len(expr.stmts) > i
            if isinstance(stmt, behav.Block):
                self.generate(stmt, writer)
            else:
                writer.enter_block()
                self.generate(stmt, writer)
                if not isinstance(stmt, (behav.Conditional, behav.Operation)):
                    writer.write_line(";")
                writer.leave_block(nl=nl)

    @generate.register
    def _(self, expr: behav.LoopBase, writer):
        scoped_init = len(expr.init) > 1
        if scoped_init:
            writer.enter_block()
            for init in expr.init:
                self.generate(init, writer)
                writer.write_line(";")
        if isinstance(expr, behav.ForLoop) or expr.init or expr.updates:
            writer.write("for (")
            for i, init in enumerate([] if scoped_init else expr.init):
                if i:
                    writer.write(", ")
                self.generate(init, writer)
            writer.write("; ")
            self.generate(expr.cond, writer)
            writer.write("; ")
            for i, update in enumerate(expr.updates):
                if i:
                    writer.write(", ")
                self.generate(update, writer)
            writer.write(")")
        elif expr.post_test:
            writer.write("do")
        else:
            writer.write("while (")
            self.generate(expr.cond, writer)
            writer.write(")")
        if len(expr.stmts) == 1 and isinstance(expr.stmts[0], behav.Block):
            self.generate(expr.stmts[0], writer)
        else:
            writer.enter_block()
            for stmt in expr.stmts:
                self.generate(stmt, writer)
                if not isinstance(stmt, (behav.Conditional, behav.Operation, behav.LoopBase, behav.Break, behav.Continue)):
                    writer.write_line(";")
            writer.leave_block()
        if expr.post_test and not (expr.init or expr.updates):
            writer.write("while (")
            self.generate(expr.cond, writer)
            writer.write_line(");")
        if scoped_init:
            writer.leave_block()


    @generate.register
    def _(self, expr: behav.Ternary, writer):
        self.generate_grouped(expr.cond, writer)
        writer.write(" ? ")
        self.generate_grouped(expr.then_expr, writer)
        writer.write(" : ")
        self.generate_grouped(expr.else_expr, writer)

    @generate.register
    def _(self, expr: behav.Return, writer):
        writer.write("return")
        if expr.expr is not None:
            writer.write(" ")
            self.generate(expr.expr, writer)
        # writer.write_line(";")

    @generate.register
    def _(self, expr: behav.UnaryOperation, writer):
        emit_operand = self.generate if expr.op.value in ('++', '--') else self.generate_grouped
        if getattr(expr, 'postfix', False):
            emit_operand(expr.right, writer)
            writer.write(expr.op.value)
        else:
            writer.write(expr.op.value)
            emit_operand(expr.right, writer)

    @generate.register
    def _(self, expr: behav.NamedReference, writer):
        writer.write(expr.reference.name)
        # if isinstance(expr.reference, (arch.Constant, arch.Memory, arch.Scalar)):
        #     # writer.track(self.reference.name)
        #     pass

    @generate.register
    def _(self, expr: behav.IndexedReference, writer):
        if getattr(expr, 'grouped_base', False):
            writer.write("(")
        writer.write(expr.reference.name)
        if getattr(expr, 'grouped_base', False):
            writer.write(")")
        writer.write("[")
        # if isinstance(expr.reference, arch.Memory):
        #     # writer.track(expr.reference.name)
        #     pass
        self.generate(expr.index, writer)
        writer.write("]")

    @generate.register
    def _(self, expr: behav.TypeConv, writer):
        writer.write("(")
        # Preserve the declared cast, including signedness-only casts. Nested
        # conversions need not retain an inferred type after simplification.
        writer.write_type(type_info.PrimitiveType(expr.data_type, expr.size))
        writer.write(")")
        self.generate_grouped(expr.expr, writer)

    @generate.register
    def _(self, expr: behav.Callable, writer):
        ref = expr.ref_or_name
        if isinstance(ref, arch.Function):
            writer.write(ref.name)
        else:
            raise NotImplementedError
        writer.write("(")
        for i, stmt in enumerate(expr.args):
            self.generate(stmt, writer)
            if i < len(expr.args) - 1:
                writer.write(", ")
        writer.write(")")

    @generate.register
    def _(self, expr: behav.Group, writer):
        # writer.enter_block()
        self.generate_grouped(expr.expr, writer)
        # writer.leave_block()
