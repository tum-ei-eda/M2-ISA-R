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

from ...metamodel import arch, behav
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
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}")

    @generate.register
    def _(self, expr: behav.Operation, writer):
        if len(expr.statements) > 1:
            writer.enter_block()
        for stmt in expr.statements:
            self.generate(stmt, writer)
            if not isinstance(stmt, (behav.Conditional, behav.Operation)):
                writer.write_line(";")
        if len(expr.statements) > 1:
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
    def _(self, expr: behav.VarDefinition, writer):
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
    def _(self, expr: behav.Assignment, writer):
        self.generate(expr.target, writer)
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
            writer.enter_block()
            self.generate(stmt, writer)
            if not isinstance(stmt, (behav.Conditional, behav.Operation)):
                writer.write_line(";")
            nl = len(expr.stmts) > i
            writer.leave_block(nl=nl)

    @generate.register
    def _(self, expr: behav.Loop, writer):
        writer.write("while (")
        self.generate(expr.cond, writer)
        writer.write(")")
        writer.enter_block()
        for stmt in expr.stmts:
            self.generate(stmt, writer)
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
        writer.write(expr.op.value)
        self.generate_grouped(expr.right, writer)

    @generate.register
    def _(self, expr: behav.NamedReference, writer):
        writer.write(expr.reference.name)
        # if isinstance(expr.reference, (arch.Constant, arch.Memory, arch.Scalar)):
        #     # writer.track(self.reference.name)
        #     pass

    @generate.register
    def _(self, expr: behav.IndexedReference, writer):
        writer.write(expr.reference.name)
        writer.write("[")
        # if isinstance(expr.reference, arch.Memory):
        #     # writer.track(expr.reference.name)
        #     pass
        self.generate(expr.index, writer)
        writer.write("]")

    @generate.register
    def _(self, expr: behav.TypeConv, writer):
        writer.write("(")
        writer.write_type(expr.ty)
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
