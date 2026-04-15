# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""A transformation module for simplifying M2-ISA-R behavior expressions. The following
simplifications are done:

* Resolvable :class:`m2isar.metamodel.arch.Constant` s are replaced by
  `m2isar.metamodel.arch.IntLiteral` s representing their value
* Fully resolvable arithmetic operations are carried out and their results
  represented as a matching :class:`m2isar.metamodel.arch.IntLiteral`
* Conditions and loops with fully resolvable conditions are either discarded entirely
  or transformed into code blocks without any conditions
* Ternaries with fully resolvable conditions are transformed into only the matching part
* Type conversions of :class:`m2isar.metamodel.arch.IntLiteral` s apply the desired
  type directly to the :class:`IntLiteral` and discard the type conversion
"""

import logging
from copy import copy

from m2isar.metamodel import arch, behav

logger = logging.getLogger("validate_behav")

# pylint: disable=unused-argument


def operation(self: behav.Operation, context):
    # print("operation", operation)
    statements = []
    for stmt in self.statements:
        # try:
        temp = stmt.generate(context)
        if isinstance(temp, list):
            statements.extend(temp)
        else:
            statements.append(temp)
        # except (NotImplementedError, ValueError):
        #   print(f"cant simplify {stmt}")

    self.statements = statements
    return self


def binary_operation(self: behav.BinaryOperation, context):
    # print("binary_operation")
    self.left = self.left.generate(context)
    op = self.op
    self.right = self.right.generate(context)

    # print("self.left", self.left)
    # print("op", op)
    # print("self.right", self.right)
    assert self.left.inferred_type is not None
    assert self.right.inferred_type is not None
    if op.value in ["|", "&", "^"] and self.left.inferred_type.width != self.right.inferred_type.width:
        context.emit_warning(f"Bitwise operations with differently size operands are discouraged.", "bit-op-missmatch", logger=logger, line_info=self.line_info)
        # input("!!")
        # print("self.left.inferred_type", self.left.inferred_type)
        # print("self.right.inferred_type", self.right.inferred_type)
    if op.value in ["<<", ">>", ">>>"] and self.right.inferred_type.signed:
        context.emit_warning(f"Shift by signed amount", "shift-signed", logger=logger, line_info=self.line_info)
        # input("!!5")
    if op.value in ["<", "<=", ">", ">=", "==", "!="] and self.left.inferred_type.signed != self.right.inferred_type.signed:
        # TODO: handle unsigned < 0
        # print("self.left", self.left, dir(self.left), self.left.inferred_type)
        # print("self.right", self.right, dir(self.right), self.right.inferred_type)
        if isinstance(self.left, behav.IntLiteral) and self.left.value == 0:
            pass
        if isinstance(self.right, behav.IntLiteral) and self.right.value == 0:
            pass
        else:
            context.emit_warning(f"Signed vs. unsigned comparison", "sign-compare", logger=logger, line_info=self.line_info)
            # input("!!4")
    if op.value == "<<" and self.left.inferred_type.width <= self.right.inferred_type.width:
        context.emit_warning(f"Shift count overflow for << operation ({self.left.inferred_type.width} vs. {self.right.inferred_type.width})", "shift-overflow", logger=logger, line_info=self.line_info)
        # input("!!6")
    return self


def slice_operation(self: behav.SliceOperation, context):
    # print("slice_operation")
    self.expr = self.expr.generate(context)
    self.left = self.left.generate(context)
    self.right = self.right.generate(context)
    return self


def concat_operation(self: behav.ConcatOperation, context):
    # print("concat_coperation")
    self.left = self.left.generate(context)
    self.right = self.right.generate(context)
    return self


def number_literal(self: behav.IntLiteral, context):
    # print("number_literal")
    return self


def int_literal(self: behav.IntLiteral, context):
    # print("int_literal")
    return self


def scalar_definition(self: behav.ScalarDefinition, context):
    # print("scalar_definition")
    return self


def assignment(self: behav.Assignment, context):
    # print("assignment", self)
    self.target = self.target.generate(context)
    self.expr = self.expr.generate(context)
    # print("self.target", self.target)
    # print("self.expr", self.expr)
    assert self.target.inferred_type is not None
    assert self.expr.inferred_type is not None
    if self.target.inferred_type.width < self.expr.inferred_type.width:
        context.emit_warning(f"Implicit truncation {self.expr.inferred_type.width} -> {self.target.inferred_type.width} found", "implicit-trunc", logger=logger, line_info=self.line_info)
        # input("!!2")
    if self.target.inferred_type.width > self.expr.inferred_type.width:
        context.emit_warning(f"Implicit extend {self.expr.inferred_type.width} -> {self.target.inferred_type.width} found", "implicit-extend", logger=logger, line_info=self.line_info)
        # input("!!3")
    return self


def conditional(self: behav.Conditional, context):
    # print("conditional")
    self.conds = [x.generate(context) for x in self.conds]
    stmts = []
    for stmt in self.stmts:
        if isinstance(stmt, list):  # TODO: legacy?
            new = [y.generate(context) for y in stmt]
        else:
            new = stmt.generate(context)
        stmts.append(new)
    self.stmts = stmts
    return self


def loop(self: behav.Loop, context):
    # print("loop")
    self.cond = self.cond.generate(context)
    self.stmts = [x.generate(context) for x in self.stmts]
    return self


def ternary(self: behav.Ternary, context):
    # print("ternary")
    self.cond = self.cond.generate(context)
    self.then_expr = self.then_expr.generate(context)
    self.else_expr = self.else_expr.generate(context)

    return self


def return_(self: behav.Return, context):
    # print("return_")
    if self.expr is not None:
        self.expr = self.expr.generate(context)
    return self


def unary_operation(self: behav.UnaryOperation, context):
    # print("unary_operation")
    self.right = self.right.generate(context)
    return self


def named_reference(self: behav.NamedReference, context):
    # print("named_reference", self)
    return self


def indexed_reference(self: behav.IndexedReference, context):
    # print("indexed_reference")
    self.index = self.index.generate(context)
    return self


def type_conv(self: behav.TypeConv, context):
    # print("type_conv")
    self.expr = self.expr.generate(context)
    return self


def callable_(self: behav.Callable, context):
    # print("callable_")
    self.args = [stmt.generate(context) for stmt in self.args]
    return self


def procedure_call(self: behav.ProcedureCall, context):
    # print("procedure_call")
    self.args = [stmt.generate(context) for stmt in self.args]
    return self


def group(self: behav.Group, context):
    # print("group")
    self.expr = self.expr.generate(context)
    if isinstance(self.expr, behav.IntLiteral):
        return self.expr
    return self


def break_(self: behav.Break, context):
    # print("break_")
    return self
