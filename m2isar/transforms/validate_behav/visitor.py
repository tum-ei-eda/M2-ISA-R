

# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich


import logging
from copy import copy
from functools import singledispatchmethod

from m2isar.metamodel import arch, behav, type_info
from ...metamodel.utils.ExprVisitor import ExprVisitor

logger = logging.getLogger("validate_behav")

# pylint: disable=unused-argument

class ValidateBehavVisitor(ExprVisitor):
    """Visitor to validate a metamodel."""

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}")

    @generate.register
    def _(self, expr: behav.Operation, context):
        for stmt in expr.statements:
            self.generate(stmt, context)

    @generate.register
    def _(self, expr: behav.Block, context):
        for stmt in expr.statements:
            self.generate(stmt, context)

    @generate.register
    def _(self, expr: behav.BinaryOperation, context):
        self.generate(expr.left, context)
        self.generate(expr.right, context)
        op = expr.op

        assert expr.left.ty is not None
        assert expr.right.ty is not None
        if op.value in ["|", "&", "^"] and expr.left.ty.size != expr.right.ty.size:
            context.emit_warning(f"Bitwise operations with differently size operands are discouraged.", "bit-op-missmatch", logger=logger, line_info=expr.line_info)
        if op.value in ["<<", ">>", ">>>"] and expr.right.ty.kind == type_info.TypeKind.INT:
            context.emit_warning(f"Shift by signed amount", "shift-signed", logger=logger, line_info=expr.line_info)
        if op.value in ["<", "<=", ">", ">=", "==", "!="] and expr.left.ty.kind != expr.right.ty.kind:
            assert(expr.left.ty.kind.is_int and expr.right.ty.kind.is_int)
            if isinstance(expr.left, behav.Literal) and expr.left.value == 0:
                pass
            if isinstance(expr.right, behav.Literal) and expr.right.value == 0:
                pass
            else:
                context.emit_warning(f"Signed vs. unsigned comparison", "sign-compare", logger=logger, line_info=expr.line_info)
        # TODO: also check possible range of non-literal rhs?
        if op.value == "<<" and isinstance(expr.right, behav.Literal) and expr.left.ty.size <= expr.right.value:
            context.emit_warning(f"Shift count overflow for << operation ({expr.left.ty.size} vs. {expr.right.value})", "shift-overflow", logger=logger, line_info=expr.line_info)


    @generate.register
    def _(self, expr: behav.SliceOperation, context):
        self.generate(expr.expr, context)
        self.generate(expr.left, context)
        self.generate(expr.right, context)

    @generate.register
    def _(self, expr: behav.ConcatOperation, context):
        self.generate(expr.left, context)
        self.generate(expr.right, context)

    @generate.register
    def _(self, expr: behav.Literal, context):
        pass

    @generate.register
    def _(self, expr: behav.Assignment, context):
        self.generate(expr.target, context)
        self.generate(expr.expr, context)
        assert expr.target.ty is not None
        assert expr.expr.ty is not None
        assert isinstance(expr.target.ty, type_info.PrimitiveType)
        if expr.target.ty.size < expr.expr.ty.size:
            context.emit_warning(f"Implicit truncation {expr.expr.ty.size} -> {expr.target.ty.size} found", "implicit-trunc", logger=logger, line_info=expr.line_info)
        if expr.target.ty.size > expr.expr.ty.size:
            context.emit_warning(f"Implicit extend {expr.expr.ty.size} -> {expr.target.ty.size} found", "implicit-extend", logger=logger, line_info=expr.line_info)

    @generate.register
    def _(self, expr: behav.Conditional, context):
        for cond in expr.conds:
            self.generate(cond, context)
        for stmt in expr.stmts:
            self.generate(stmt, context)

    @generate.register
    def _(self, expr: behav.Loop, context):
        self.generate(expr.cond, context)
        for stmt in expr.stmts:
            self.generate(stmt, context)

    @generate.register
    def _(self, expr: behav.Ternary, context):
        self.generate(expr.cond, context)
        self.generate(expr.then_expr, context)
        self.generate(expr.else_expr, context)

    @generate.register
    def _(self, expr: behav.Return, context):
        if expr.expr is not None:
            self.generate(expr.expr, context)
        return expr

    @generate.register
    def _(self, expr: behav.UnaryOperation, context):
        self.generate(expr.right, context)
        return expr

    @generate.register
    def _(self, expr: behav.ScalarDefinition, context):
        pass

    @generate.register
    def _(self, expr: behav.Break, context):
        pass

    @generate.register
    def _(self, expr: behav.NamedReference, context):
        pass

    @generate.register
    def _(self, expr: behav.IndexedReference, context):
        self.generate(expr.index, context)

    @generate.register
    def _(self, expr: behav.TypeConv, context):
        self.generate(expr.expr, context)

    @generate.register
    def _(self, expr: behav.Callable, context):
        for arg in expr.args:
            self.generate(arg, context)

    @generate.register
    def _(self, expr: behav.Callable, context):
        for arg in expr.args:
            self.generate(arg, context)

    @generate.register
    def _(self, expr: behav.Group, context):
        self.generate(expr.expr, context)
