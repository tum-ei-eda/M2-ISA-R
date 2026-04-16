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
    Use self for additonal global state information
    Use context for stack-based information that is only relevant for the current branch of the AST.
    """
    @abstractmethod
    def generate(self, expr : behav.BaseNode, context=None):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

    @singledispatchmethod
    def default_visit(self, expr: behav.BaseNode, context):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

    @default_visit.register
    def visit_codeliteral(self, expr: behav.CodeLiteral, context):
        return expr

    @default_visit.register
    def visit_operator(self, expr: behav.Operator, context):
        return expr

    @default_visit.register
    def visit_operation(self, expr: behav.Operation, context):
        statements = []
        for stmt in expr.statements:
            stmt = stmt.generate(context)
            statements.append(stmt)
        expr.statements = statements
        return expr

    @default_visit.register
    def visit_block(self, expr: behav.Block, context):
        statements = []
        for stmt in expr.statements:
            stmt = stmt.generate(context)
            statements.append(stmt)
        expr.statements = statements
        return expr

    @default_visit.register
    def visit_binary_operation(self, expr: behav.BinaryOperation, context):
        expr.left = expr.left.generate(context)
        expr.right = expr.right.generate(context)
        return expr

    @default_visit.register
    def visit_slice_operation(self, expr: behav.SliceOperation, context):
        expr.expr = expr.expr.generate(context)
        expr.left = expr.left.generate(context)
        expr.right = expr.right.generate(context)
        return expr

    @default_visit.register
    def visit_concat_operation(self, expr: behav.ConcatOperation, context):
        expr.left = expr.left.generate(context)
        expr.right = expr.right.generate(context)
        return expr

    @default_visit.register
    def visit_number_literal(self, expr: behav.NumberLiteral, context):
        return expr

    @default_visit.register
    def visit_int_literal(self, expr: behav.IntLiteral, context):
        return expr

    @default_visit.register
    def visit_string_literal(self, expr: behav.StringLiteral, context):
        return expr

    @default_visit.register
    def visit_assignment(self, expr: behav.Assignment, context):
        expr_target = expr.target.generate(context)
        expr.expr = expr.expr.generate(context)
        return expr

    @default_visit.register
    def visit_conditional(self, expr: behav.Conditional, context):
        conds = []
        for cond in expr.conds:
            cond = cond.generate(context)
            conds.append(cond)
        expr.conds = conds
        stmts = []
        for stmt in expr.stmts:
            smts = stmt.generate(context)
            stmts.append(stmt)
        expr.stmts = stmts
        return expr

    @default_visit.register
    def visit_loop(self, expr: behav.Loop, context):
        expr.cond = expr.cond.generate(context)
        stmts = []
        for stmt in expr.stmts:
            stmt = stmt.generate(context)
            stmts.append(stmt)
        expr.stmts = stmts
        return expr

    @default_visit.register
    def visit_ternary_operation(self, expr: behav.Ternary, context):
        expr.cond = expr.cond.generate(context)
        expr.then_expr = expr.then_expr.generate(context)
        expr.else_expr = expr.else_expr.generate(context)
        return expr

    @default_visit.register
    def visit_scalar_definition(self, expr: behav.ScalarDefinition, context):
        return expr

    @default_visit.register
    def visit_break(self, expr: behav.Break, context):
        return expr

    @default_visit.register
    def visit_named_reference(self, expr: behav.NamedReference, context):
        return expr

    @default_visit.register
    def visit_type_conv(self, expr: behav.TypeConv, context):
        expr.expr = expr.expr.generate(context)
        return expr

    @default_visit.register
    def visit_callable(self, expr: behav.Callable, context):
        args = []
        for arg in expr.args:
            arg = arg.generate(context)
            args.append(arg)
        epxr.args = args
        return expr

    @default_visit.register
    def visit_procedure_call(self, expr: behav.Callable, context):
        args = []
        for arg in expr.args:
            arg = arg.generate(context)
            args.append(arg)
        epxr.args = args
        return expr

    @default_visit.register
    def visit_group(self, expr: behav.Group, context):
        expr.expr = expr.expr.generate(context)
        return expr
