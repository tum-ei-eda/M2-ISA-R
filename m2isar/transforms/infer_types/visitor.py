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
from functools import singledispatchmethod
from copy import deepcopy

from m2isar.metamodel import arch, behav
from ...metamodel.utils.ExprMutator import ExprMutator

logger = logging.getLogger("infer_types")

# pylint: disable=unused-argument

def infer_slice_sice_helper(expr):
    width = None
    if isinstance(expr.left, behav.NamedReference) and isinstance(expr.right, behav.NamedReference):
        if expr.left.reference.name == expr.right.reference.name:
            return 1
    elif isinstance(expr.left, behav.NamedReference):
        if isinstance(expr.right, behav.BinaryOperation):
            if expr.right.op.value in ["+", "-"]:
                if isinstance(expr.right.left, behav.NamedReference) and isinstance(expr.right.right, behav.IntLiteral):
                    if expr.left.reference.name == expr.right.left.reference.name:
                        width = expr.right.right.value + 1
                elif isinstance(expr.right.right, behav.NamedReference) and isinstance(expr.right.left, behav.IntLiteral):
                    if expr.left.reference.name == expr.right.right.reference.name:
                        width = expr.right.left.value + 1
    elif isinstance(expr.right, behav.NamedReference):
        if isinstance(expr.left, behav.BinaryOperation):
            if expr.left.op.value in ["+", "-"]:
                if isinstance(expr.left.left, behav.NamedReference) and isinstance(expr.left.right, behav.IntLiteral):
                    if expr.right.reference.name == expr.left.left.reference.name:
                        width = expr.left.right.value + 1
                elif isinstance(expr.left.right, behav.NamedReference) and isinstance(expr.left.left, behav.IntLiteral):
                    if expr.right.reference.name == expr.left.right.reference.name:
                        width = expr.left.left.value + 1
    return width

class InferTypesMutator(ExprMutator):
    """Mutator to annote inferred types to a metamodel."""

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}")

    @generate.register
    def _(self, expr: behav.Operation, context):
        statements = []
        for stmt in expr.statements:
            temp = self.generate(stmt, context)
            if isinstance(temp, list):
                statements.extend(temp)
            else:
                statements.append(temp)

        expr.statements = statements
        return expr


    @generate.register
    def _(self, expr: behav.BinaryOperation, context):
        expr.left = self.generate(expr.left, context)
        expr.right = self.generate(expr.right, context)

        # see: https://github.com/Minres/CoreDSL/wiki/Expressions#arithmetic-type-rules
        if expr.op.value in ["+", "-", "*", "/", "%", "|", "&", "^", "<<", ">>"]:
            if expr.left.inferred_type is None:
                context.emit_warning("Binary Operation needs inferred type.", "infer-type", logger=logger, line_info=expr.left.line_info)
                expr.inferred_type = None
                return expr
            elif expr.right.inferred_type is None:
                context.emit_warning("Binary Operation needs inferred type.", "infer-type", logger=logger, line_info=expr.right.line_info)
                expr.inferred_type = None
                return expr
            assert isinstance(expr.left.inferred_type, arch.IntegerType)
            assert isinstance(expr.right.inferred_type, arch.IntegerType)
            w1 = expr.left.inferred_type._width
            w2 = expr.right.inferred_type._width
            s1 = expr.left.inferred_type.signed
            s2 = expr.right.inferred_type.signed
            if expr.op.value == "+":
                if not s1 and not s2:
                    wr = max(w1, w2) + 1
                    sr = False
                elif s1 and s2:
                    wr = max(w1, w2) + 1
                    sr = True
                elif s1 and not s2:
                    wr = max(w1, w2 + 1) + 1
                    sr = True
                elif not s1 and s2:
                    wr = max(w1 + 1, w2) + 1
                    sr = True
            elif expr.op.value == "-":
                sr = True
                if not s1 and not s2:
                    wr = max(w1 + 1, w2 + 1)
                elif s1 and s2:
                    wr = max(w1 + 1, w2 + 1)
                elif s1 and not s2:
                    wr = max(w1, w2 + 1) + 1
                elif not s1 and s2:
                    wr = max(w1 + 1, w2) + 1
            elif expr.op.value == "*":
                wr = w1 + w2
                sr = s1 or s2
            elif expr.op.value == "/":
                wr = w1 if not s2 else (w1 + 1)
                sr = s1 or s2
            elif expr.op.value == "%":
                if not s1 and not s2:
                    wr = min(w1, w2)
                    sr = False
                elif s1 and s2:
                    wr = min(w1, w2)
                    sr = True
                elif s1 and not s2:
                    wr = min(w1, w2 + 1)
                    sr = True
                elif not s1 and s2:
                    wr = min(w1, max(1, w2 - 1))
                    sr = False
            elif expr.op.value in ["|", "&", "^"]:
                wr = max(w1, w2)
                sr = s1 or s2
            elif expr.op.value in [">>", "<<"]:
                wr = w1
                sr = s1
            expr.inferred_type = arch.IntegerType(wr, sr, None)
        else:
            if expr.op.value in ["||", "&&"]:
                expr.inferred_type = arch.IntegerType(1, False, None)  # unsigned<1> / bool
            elif expr.op.value in ["<", ">", "==", "!=", ">=", "<="]:
                expr.inferred_type = arch.IntegerType(1, False, None)  # unsigned<1> / bool
        assert expr.inferred_type is not None

        return expr


    @generate.register
    def _(self, expr: behav.SliceOperation, context):
        expr.expr = self.generate(expr.expr, context)
        expr.left = self.generate(expr.left, context)
        expr.right = self.generate(expr.right, context)

        # type inference
        if expr.expr.inferred_type is None:
            context.emit_warning("Can not infer type of non-static slice operation.", "infer-type", logger=logger, line_info=expr.expr.line_info)
            return expr
        assert isinstance(expr.expr.inferred_type, arch.IntegerType)
        ty = expr.expr.inferred_type
        # For non-static slices, we cann not infer the type!
        if isinstance(expr.left, behav.IntLiteral) and isinstance(expr.right, behav.IntLiteral):
            lval = expr.left.value
            rval = expr.right.value
            width = lval - rval + 1 if lval > rval else rval - lval + 1
        elif isinstance(expr.left, behav.IntLiteral):
            context.emit_warning("Can not infer type of non-static slice operation.", "infer-non-static-slice", logger=logger, line_info=expr.left.line_info)
            return expr
        elif isinstance(expr.right, behav.IntLiteral):
            context.emit_warning("Can not infer type of non-static slice operation.", "infer-non-static-slice", logger=logger, line_info=expr.right.line_info)
            return expr
        else:
            width = infer_slice_sice_helper(expr)
            if width is None:
                context.emit_warning("Can not infer type of non-static slice operation.", "infer-non-static-slice", logger=logger, line_info=expr.left.line_info)
                return expr
        ty_ = copy(ty)
        ty_._width = width
        expr.inferred_type = ty_

        return expr


    @generate.register
    def _(self, expr: behav.ConcatOperation, context):
        expr.left = self.generate(expr.left, context)
        expr.right = self.generate(expr.right, context)
        if expr.left.inferred_type is None:
            context.emit_warning("Concat Operation needs inferred type.", "infer-type", logger=logger, line_info=expr.left.line_info)
            return expr
        if expr.right.inferred_type is None:
            context.emit_warning("Concat Operation needs inferred type.", "infer-type", logger=logger, line_info=expr.right.line_info)
            return expr
        width = expr.left.inferred_type.width + expr.right.inferred_type.width
        ty = arch.IntegerType(width, False, None)
        expr.inferred_type = ty

        return expr


    @generate.register
    def _(self, expr: behav.IntLiteral, context):
        if isinstance(expr, behav.IntLiteral):
            bit_size = expr.bit_size
            signed = expr.signed

            expr.inferred_type = arch.IntegerType(bit_size, signed, None)
        return expr


    @generate.register
    def _(self, expr: behav.IntLiteral, context):
        # type inference
        bit_size = expr.bit_size
        signed = expr.signed

        expr.inferred_type = arch.IntegerType(bit_size, signed, None)

        return expr

    @generate.register
    def _(self, expr: behav.ScalarDefinition, context):
        # type inference
        signed = expr.scalar.data_type == arch.DataType.S
        width = expr.scalar.size
        expr.inferred_type = arch.IntegerType(width, signed, None)
        return expr

    @generate.register
    def _(self, expr: behav.Assignment, context):
        expr.target = self.generate(expr.target, context)
        expr.expr = self.generate(expr.expr, context)

        # if isinstance(expr.expr, behav.IntLiteral) and isinstance(expr.target, behav.ScalarDefinition):
        #       expr.target.scalar.value = expr.expr.value

        # type inference
        expr.inferred_type = None

        return expr

    @generate.register
    def _(self, expr: behav.Conditional, context):
        expr.conds = [self.generate(x, context) for x in expr.conds]
        # expr.stmts = [[self.generate(y, context) for y in x] for x in expr.stmts]
        stmts = []
        for stmt in expr.stmts:
            if isinstance(stmt, list):  # TODO: legacy?
                new = [seld.generate(y, context) for y in stmt]
            else:
                new = self.generate(stmt, context)
            stmts.append(new)
        expr.stmts = stmts

        return expr

    @generate.register
    def _(self, expr: behav.Loop, context):
        expr.cond = self.generate(expr.cond, context)
        expr.stmts = [self.generate(x, context) for x in expr.stmts]

        return expr

    @generate.register
    def _(self, expr: behav.Ternary, context):

        expr.cond = self.generate(expr.cond, context)
        expr.then_expr = self.generate(expr.then_expr, context)
        expr.else_expr = self.generate(expr.else_expr, context)

        # TODO
        then_ty = expr.then_expr.inferred_type
        else_ty = expr.else_expr.inferred_type
        if then_ty and else_ty:
            # assert then_ty.signed == else_ty.signed
            wt = then_ty.width
            we = else_ty.width
            wr = max(wt, we)
            expr.inferred_type = arch.IntegerType(wr, True, None)

        return expr

    @generate.register
    def _(self, expr: behav.Return, context):
        if expr.expr is not None:
            expr.expr = self.generate(expr.expr, context)

        return expr

    @generate.register
    def _(self, expr: behav.UnaryOperation, context):
        expr.right = self.generate(expr.right, context)
        if expr.right.inferred_type:
            w1 = expr.right.inferred_type.width
            if expr.op.value == "-":
                inferred_type = arch.IntegerType(w1 + 1, True, None)
            elif expr.op.value == "~":
                inferred_type = arch.IntegerType(w1, True, None)
            elif expr.op.value == "!":
                inferred_type = arch.IntegerType(1, False, None)
            else:
                inferred_type = None
            expr.inferred_type = inferred_type

        return expr

    @generate.register
    def _(self, expr: behav.NamedReference, context):
        reference = expr.reference

        # type inference
        # expr.infered_type = ?
        if isinstance(reference, arch.BitFieldDescr):
            assert expr.reference.data_type in [arch.DataType.U, arch.DataType.S]
            ty = arch.IntegerType(reference.size, reference.data_type == arch.DataType.S, None)
            expr.inferred_type = ty

        elif isinstance(reference, arch.Scalar):
            dt = reference.data_type
            sz = reference.size
            assert dt in [arch.DataType.U, arch.DataType.S]
            signed = dt == arch.DataType.S
            ty = arch.IntegerType(sz, signed, None)
            expr.inferred_type = ty
        elif isinstance(reference, arch.Memory):
            expr.inferred_type = arch.IntegerType(reference.size, False, None)
        elif isinstance(reference, arch.Intrinsic):
            assert expr.reference.data_type in [arch.DataType.U, arch.DataType.S]
            expr.inferred_type = arch.IntegerType(reference.size, reference.data_type == arch.DataType.S, None)
        elif isinstance(reference, arch.Constant):
            expr.inferred_type = arch.IntegerType(reference.size, reference.signed, None)
        else:
            assert False, "Unhandled reference"

        return expr

    @generate.register
    def _(self, expr: behav.IndexedReference, context):
        expr.index = self.generate(expr.index, context)

        # type inference
        assert isinstance(expr.reference, arch.Memory)
        ty = arch.DataType.U  # TODO: Memory class should keep track of dtype, not only size?
        assert ty in [arch.DataType.U, arch.DataType.S]
        single_mem_acc_size = expr.reference.size

        ## Simple eval check for ranged access.
        # Little-endian interpretation:
        # - lhs > rhs  → width = lhs - rhs + 1
        # - lhs == rhs → width = 8 bits

        if expr.right == None:
            size = single_mem_acc_size
        if expr.right != None:
                lhs_offset = helper_expr_size(expr.index)
                rhs_offset = helper_expr_size(expr.right)
                assert(lhs_offset >= rhs_offset)
                size = (lhs_offset - rhs_offset + 1)*single_mem_acc_size

        ty_ = arch.IntegerType(size, ty == arch.DataType.S, None)

        expr.inferred_type = ty_

        return expr

    @generate.register
    def _(self, expr: behav.TypeConv, context):
        expr.expr = self.generate(expr.expr, context)

        ty = deepcopy(expr.expr.inferred_type)
        if ty is None:
            context.emit_warning("Type conv needs inferred type.", "infer-type", logger=logger, line_info=expr.expr.line_info)
            return expr
        assert isinstance(ty, arch.IntegerType)
        assert expr.data_type in [arch.DataType.U, arch.DataType.S]
        ty.signed = expr.data_type == arch.DataType.S
        if expr.size is not None:
            ty._width = expr.size

        # type inference
        expr.inferred_type = ty

        return expr

    @generate.register
    def _(self, expr: behav.Callable, context):
        if isinstance(expr.ref_or_name, arch.Function):
            if expr.ref_or_name.data_type == arch.DataType.NONE:
                signed = None
            else:
                assert expr.ref_or_name.data_type in [arch.DataType.U, arch.DataType.S]
                signed = expr.ref_or_name.data_type == arch.DataType.S
            width = expr.ref_or_name.size
            expr.inferred_type = arch.IntegerType(width, signed, None)
        expr.args = [self.generate(stmt, context) for stmt in expr.args]

        return expr

    # Just use Callable super class
    # @generate.register
    # def _(self, expr: behav.ProcedureCall, context):
    #     expr.args = [self.generate(stmt, context) for stmt in expr.args]

    #     return expr

    @generate.register
    def _(self, expr: behav.Group, context):
        expr.expr = self.generate(expr.expr, context)

        if isinstance(expr.expr, behav.IntLiteral):
            return expr.expr

        # type inference
        expr.inferred_type = expr.expr.inferred_type

        return expr

    @generate.register
    def _(self, expr: behav.Break, context):
        return expr


# Simple expression evaluation for ranged mem indexes
def helper_expr_size(sub_expr: behav.BaseNode):
    expr = None
    if type(sub_expr) == behav.Group:
            expr = sub_expr.expr
            return helper_expr_size(expr)
    elif type(sub_expr) == behav.BinaryOperation:
            expr = sub_expr
            assert isinstance(expr.left, behav.NamedReference)

            if expr.op.value == "+":
                    if type(expr.right) == behav.IntLiteral:
                            return int(expr.right.value)

            elif expr.op.value == "-":
                    if type(expr.right) == behav.IntLiteral:
                            return (-1 * int(expr.right.value))
            else:
                    raise(f"Not supported Operation value Type {expr.op.value} within mem access range")

    elif type(sub_expr) == behav.NamedReference:
            return 0
    else:
            raise(f"Not supported expr Type {type(sub_expr)} within mem access range")
