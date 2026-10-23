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
    - Analyzing/Mutating the AST (sometimes with the help of a context)
      and returning a modified AST.

    To implement a new visitor, overload the 'generate' method of nodes that need altered visitation behavior.

    Use ``self`` for additonal global state information. Use ``context`` for
    stack-based information that is only relevant for the current AST branch.
    """
    @abstractmethod
    def generate(self, expr : behav.BaseNode, context=None):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

    @singledispatchmethod
    def default_visit(self, expr: behav.BaseNode, context):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

    @default_visit.register
    def visit_codeliteral(self, expr: behav.CodeLiteral, context):
        pass

    @default_visit.register
    def visit_operator(self, expr: behav.Operator, context):
        pass

    @default_visit.register
    def visit_operation(self, expr: behav.Operation, context):
        for stmt in expr.statements:
            self.generate(stmt, context)

    @default_visit.register
    def visit_block(self, expr: behav.Block, context):
        for stmt in expr.statements:
            self.generate(stmt, context)

    @default_visit.register
    def visit_binary_operation(self, expr: behav.BinaryOperation, context):
        self.generate(expr.left, context)
        self.generate(expr.right, context)

    @default_visit.register
    def visit_slice_operation(self, expr: behav.SliceOperation, context):
        self.generate(expr.expr, context)
        self.generate(expr.left, context)
        self.generate(expr.right, context)

    @default_visit.register
    def visit_concat_operation(self, expr: behav.ConcatOperation, context):
        self.generate(expr.left, context)
        self.generate(expr.right, context)

    @default_visit.register
    def visit_number_literal(self, expr: behav.Literal, context):
        pass

    @default_visit.register
    def visit_assignment(self, expr: behav.Assignment, context):
        self.generate(expr.target, context)
        self.generate(expr.expr, context)

    @default_visit.register
    def visit_conditional(self, expr: behav.Conditional, context):
        for cond in expr.conds:
            self.generate(cond, context)
        for stmt in expr.stmts:
            self.generate(stmt, context)

    @default_visit.register
    def visit_loop(self, expr: behav.LoopBase, context):
        for stmt in expr.init:
            self.generate(stmt, context)
        self.generate(expr.cond, context)
        for stmt in expr.stmts:
            self.generate(stmt, context)
        for update in expr.updates:
            self.generate(update, context)

    @default_visit.register
    def visit_ternary_operation(self, expr: behav.Ternary, context):
        self.generate(expr.cond, context)
        self.generate(expr.then_expr, context)
        self.generate(expr.else_expr, context)

    @default_visit.register
    def visit_return_operation(self, expr: behav.Return, context):
        if expr.expr is not None:
            self.generate(expr.expr, context)

    @default_visit.register
    def visit_unary_operation(self, expr: behav.UnaryOperation, context):
        self.generate(expr.right, context)

    @default_visit.register
    def visit_var_definition(self, expr: behav.VarDefinition, context):
        pass

    @default_visit.register
    def visit_break(self, expr: behav.Break, context):
        pass

    @default_visit.register
    def visit_continue(self, expr: behav.Continue, context):
        pass

    @default_visit.register
    def visit_named_reference(self, expr: behav.NamedReference, context):
        pass

    @default_visit.register
    def visit_indexed_reference(self, expr: behav.IndexedReference, context):
        self.generate(expr.index, context)

    @default_visit.register
    def visit_type_conv(self, expr: behav.TypeConv, context):
        self.generate(expr.expr, context)

    @default_visit.register
    def visit_callable(self, expr: behav.Callable, context):
        for arg in expr.args:
            self.generate(arg, context)

    @default_visit.register
    def visit_procedure_call(self, expr: behav.Callable, context):
        for arg in expr.args:
            self.generate(arg, context)

    @default_visit.register
    def visit_group(self, expr: behav.Group, context):
        self.generate(expr.expr, context)
