# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026
# Chair of Embedded Computing Systems
# Technical University of Wien

"""A helper module for applying all expression visitor functions in this package to
functions and instructions to get rid of monkey patching and use instead polymorphism.
"""

from ...metamodel import behav
from abc import ABC, abstractmethod

from functools import singledispatchmethod
# pylint: disable=unused-argument


class ExprVisitor(ABC):
    """Base class for recursive metamodel traversal with 2 modes:
        - Generating text by appending context while traversing AST.
        - Analyzing/Mutating the AST (sometimes with the help of a context) and returning a modified AST.
    To implement a new visitor, overload the 'generate' method of nodes that need altered visitation behavior.
    """
    @singledispatchmethod
    def generate(self, expr : behav.BaseNode, context=None):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

    @generate.register
    def visit_codeliteral(self, expr: behav.CodeLiteral, context):
        pass

    @generate.register
    def visit_operator(self, expr: behav.Operator, context):
        pass

    @generate.register
    def visit_operation(self, expr: behav.Operation, context):
        for stmt in expr.statements:
            stmt.generate(context)

    @generate.register
    def visit_block(self, expr: behav.Block, context):
        for stmt in expr.statements:
            stmt.generate(context)

    @generate.register
    def visit_binary_operation(self, expr: behav.BinaryOperation, context):
        expr.left.generate(context)
        expr.right.generate(context)

    @generate.register
    def visit_slice_operation(self, expr: behav.SliceOperation, context):
        expr.expr.generate(context)
        expr.left.generate(context)
        expr.right.generate(context)

    @generate.register
    def visit_concat_operation(self, expr: behav.ConcatOperation, context):
        expr.left.generate(context)
        expr.right.generate(context)

    @generate.register
    def visit_number_literal(self, expr: behav.NumberLiteral, context):
        pass

    @generate.register
    def visit_int_literal(self, expr: behav.IntLiteral, context):
        pass

    @generate.register
    def visit_string_literal(self, expr: behav.StringLiteral, context):
        pass

    @generate.register
    def visit_assignment(self, expr: behav.Assignment, context):
        expr.target.generate(context)
        expr.expr.generate(context)

    @generate.register
    def visit_conditional(self, expr: behav.Conditional, context):
        for cond in expr.conds:
            cond.generate(context)
        for stmt in expr.stmts:
            stmt.generate(context)

    @generate.register
    def visit_loop(self, expr: behav.Loop, context):
        expr.cond.generate(context)
        for stmt in expr.stmts:
            stmt.generate(context)

    # TODO: Add more visit methods for other node types as needed, e.g., Ternary, etc.
    @generate.register
    def visit_ternary_operation(self, expr: behav.Ternary, context):
        expr.cond.generate(context)
        expr.then_expr.generate(context)
        expr.else_expr.generate(context)

    @generate.register
    def visit_scalar_definition(self, expr: behav.ScalarDefinition, context):
        pass

    @generate.register
    def visit_break(self, expr: behav.Break, context):
        pass

    @generate.register
    def visit_named_reference(self, expr: behav.NamedReference, context):
        pass

    @generate.register
    def visit_type_conv(self, expr: behav.TypeConv, context):
        expr.expr.generate(context)

    @generate.register
    def visit_callable(self, expr: behav.Callable, context):
        for arg in expr.args:
            arg.generate(context)

    @generate.register
    def visit_procedure_call(self, expr: behav.Callable, context):
        for arg in expr.args:
            arg.generate(context)

    @generate.register
    def group(self, expr: behav.Group, context):
        expr.expr.generate(context)
