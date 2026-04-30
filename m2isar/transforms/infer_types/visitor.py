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
  `m2isar.metamodel.arch.Literal` s representing their value
* Fully resolvable arithmetic operations are carried out and their results
  represented as a matching :class:`m2isar.metamodel.arch.Literal`
* Conditions and loops with fully resolvable conditions are either discarded entirely
  or transformed into code blocks without any conditions
* Ternaries with fully resolvable conditions are transformed into only the matching part
* Type conversions of :class:`m2isar.metamodel.arch.Literal` s apply the desired
  type directly to the :class:`Literal` and discard the type conversion
"""

import logging
from copy import copy
from functools import singledispatchmethod
from copy import deepcopy

from m2isar.metamodel import arch, behav, type_info
from ...metamodel.utils.ExprMutator import ExprMutator

logger = logging.getLogger("infer_types")

# pylint: disable=unused-argument

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
            if expr.left.ty is None or expr.right.ty is None:
                logger.warning("Slice Operation needs inferred type. Skipping...")
                expr.ty = None
                return expr
            assert isinstance(expr.left.ty, type_info.IntegerType)
            assert isinstance(expr.right.ty, type_info.IntegerType)
            w1 = arch.get_const_or_val(expr.left.ty.size)
            w2 = arch.get_const_or_val(expr.right.ty.size)
            s1 = True if expr.left.ty.kind == type_info.TypeKind.INT else False
            s2 = True if expr.right.ty.kind == type_info.TypeKind.INT else False
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

            kind = type_info.TypeKind.INT if sr else type_info.TypeKind.UINT
            expr.ty = type_info.IntegerType(wr, kind)
        else:
            if expr.op.value in ["||", "&&"]:
                expr.ty = type_info.IntegerType(1, type_info.TypeKind.UINT)  # unsigned<1> / bool
            elif expr.op.value in ["<", ">", "==", "!=", ">=", "<="]:
                expr.ty = type_info.IntegerType(1, type_info.TypeKind.UINT)  # unsigned<1> / bool
        assert expr.ty is not None

        return expr


    @generate.register
    def _(self, expr: behav.SliceOperation, context):
        expr.expr = self.generate(expr.expr, context)
        expr.left = self.generate(expr.left, context)
        expr.right = self.generate(expr.right, context)

        # type inference
        if expr.expr.ty is None:
            logger.warning("Slice Operation needs inferred type. Skipping...")
            return expr
        assert isinstance(expr.expr.ty, type_info.IntegerType)
        ty = expr.expr.ty
        # For non-static slices, we cann not infer the type!
        if not isinstance(expr.left, behav.Literal):
            logger.warning("Can not infer type of non-static slice operation. Skipping...")
            return expr
        lval = expr.left.value
        if not isinstance(expr.right, behav.Literal):
            logger.warning("Can not infer type of non-static slice operation. Skipping...")
            return expr
        rval = expr.right.value
        width = lval - rval + 1 if lval > rval else rval - lval + 1
        ty_ = copy(ty)
        ty_.size = width
        expr.ty = ty_

        return expr


    @generate.register
    def _(self, expr: behav.ConcatOperation, context):
        expr.left = self.generate(expr.left, context)
        expr.right = self.generate(expr.right, context)
        if expr.left.ty is None:
            logger.warning("Concat Operation needs inferred type. Skipping...")
            return expr
        if expr.right.ty is None:
            logger.warning("Concat Operation needs inferred type. Skipping...")
            return expr
        width = arch.get_const_or_val(expr.left.ty.size) + arch.get_const_or_val(expr.right.ty.size)
        size = arch.get_const_or_val(width)
        ty = type_info.IntegerType(size, type_info.TypeKind.UINT)
        expr.ty = ty

        return expr


    # behav.IntLiteral
    @generate.register
    def _(self, expr: behav.Literal, context):
        # type inference
        assert(expr.ty.size is not None)
        assert(expr.ty.kind.is_int)
        expr.ty = type_info.IntegerType(expr.ty.size, expr.ty.kind)

        return expr

    @generate.register
    def _(self, expr: behav.ScalarDefinition, context):
        # type inference
        assert isinstance(expr.scalar.ty, type_info.PrimitiveType)
        assert expr.scalar.ty.size is not None
        assert expr.scalar.ty.kind.is_int
        expr.ty = expr.scalar.ty
        return expr

    @generate.register
    def _(self, expr: behav.Assignment, context):
        expr.target = self.generate(expr.target, context)
        expr.expr = self.generate(expr.expr, context)

        # if isinstance(expr.expr, behav.IntLiteral) and isinstance(expr.target, behav.ScalarDefinition):
        #       expr.target.scalar.value = expr.expr.value

        # type inference
        expr.ty = None

        return expr

    @generate.register
    def _(self, expr: behav.Conditional, context):
        expr.conds = [self.generate(x, context) for x in expr.conds]
        # expr.stmts = [[self.generate(y, context) for y in x] for x in expr.stmts]
        stmts = []
        for stmt in expr.stmts:
            if isinstance(stmt, list):  # TODO: legacy?
                new = [self.generate(y, context) for y in stmt]
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
        then_ty = expr.then_expr.ty
        else_ty = expr.else_expr.ty
        if then_ty and else_ty:
            # assert then_ty.signed == else_ty.signed
            wt = arch.get_const_or_val(then_ty.size)
            we = arch.get_const_or_val(else_ty.size)
            wr = max(wt, we)
            expr.ty = type_info.IntegerType(wr, type_info.TypeKind.INT)

        return expr

    @generate.register
    def _(self, expr: behav.Return, context):
        if expr.expr is not None:
            expr.expr = self.generate(expr.expr, context)

        return expr

    @generate.register
    def _(self, expr: behav.UnaryOperation, context):
        expr.right = self.generate(expr.right, context)
        if expr.right.ty:
            w1 = expr.right.ty.size
            if expr.op.value == "-":
                ty = type_info.IntegerType(w1 + 1, type_info.TypeKind.INT)
            elif expr.op.value == "~":
                ty = type_info.IntegerType(w1, type_info.TypeKind.INT)
            elif expr.op.value == "!":
                ty = type_info.IntegerType(1, type_info.TypeKind.UINT)
            else:
                ty = None
            expr.ty = ty

        return expr

    @generate.register
    def _(self, expr: behav.NamedReference, context):
        reference = expr.reference

        # type inference
        # expr.infered_type = ?
        if isinstance(reference, arch.BitFieldDescr):
            assert expr.reference.ty.kind.is_int
            ty = type_info.IntegerType(reference.ty.size, reference.ty.kind)
            expr.ty = ty

        elif isinstance(reference, arch.Symbol):
            assert isinstance(reference.ty, type_info.PrimitiveType)
            dt = reference.ty.kind
            sz = reference.ty.size
            assert dt.is_int
            ty = type_info.IntegerType(sz, dt)
            expr.ty = ty
        elif isinstance(reference, arch.Memory):
            expr.ty = type_info.IntegerType(reference.ty.size, type_info.TypeKind.UINT)
        elif isinstance(reference, arch.Intrinsic):
            assert expr.reference.ty.kind.is_int
            expr.ty = type_info.IntegerType(reference.ty.size, reference.ty.kind)
        elif isinstance(reference, arch.Constant):
            kind = type_info.TypeKind.INT if reference.signed else type_info.TypeKind.UINT

            expr.ty = type_info.IntegerType(reference.size, kind)
        else:
            assert False, "Unhandled reference"

        return expr

    @generate.register
    def _(self, expr: behav.IndexedReference, context):
        expr.index = self.generate(expr.index, context)

        # type inference
        assert isinstance(expr.reference, arch.Memory)
        ty = type_info.TypeKind.UINT  # TODO: Memory class should keep track of dtype, not only size?
        assert ty.is_int
        single_mem_acc_size = expr.reference.ty.size

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

        ty_ = type_info.IntegerType(size, ty)

        expr.ty = ty_

        return expr

    @generate.register
    def _(self, expr: behav.TypeConv, context):
        expr.expr = self.generate(expr.expr, context)

        ty = deepcopy(expr.expr.ty)
        if ty is None:
            logger.warning("Type conv needs inferred type. Skipping...")
            return expr
        assert isinstance(ty, type_info.IntegerType)
        assert expr.data_type.is_int
        ty.signed = expr.data_type == type_info.TypeKind.INT
        if expr.size is not None:
            ty.size = expr.size

        # type inference
        expr.ty = ty

        return expr

    @generate.register
    def _(self, expr: behav.Callable, context):
        if isinstance(expr.ref_or_name, arch.Function):
            if not(expr.ref_or_name.ty.kind == type_info.TypeKind.VOID):
                assert expr.ref_or_name.ty.kind.is_int
                width = arch.get_const_or_val(expr.ref_or_name.ty.size)
                expr.ty = type_info.IntegerType(arch.get_const_or_val(width), expr.ref_or_name.ty.kind)
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

        if isinstance(expr.expr, behav.Literal):
            return expr.expr

        # type inference
        expr.ty = expr.expr.ty

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
                    if type(expr.right) == behav.Literal:
                            return int(expr.right.value)

            elif expr.op.value == "-":
                    if type(expr.right) == behav.Literal:
                            return (-1 * int(expr.right.value))
            else:
                    raise(f"Not supported Operation value Type {expr.op.value} within mem access range")

    elif type(sub_expr) == behav.NamedReference:
            return 0
    else:
            raise(f"Not supported expr Type {type(sub_expr)} within mem access range")
