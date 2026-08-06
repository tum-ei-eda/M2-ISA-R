# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""A transformation module for simplifying M2-ISA-R behavior expressions. The following
simplifications are done:

* Resolvable :class:`m2isar.metamodel.arch.Parameter` s are replaced by
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


def infer_slice_sice_helper(expr):
    def name(node):
        return node.reference.name if isinstance(node, behav.NamedReference) else None

    def int_value(node):
        return node.value if isinstance(node, behav.Literal) and node.ty.kind.is_int else None

    def width_from(ref, other):
        if not isinstance(other, behav.BinaryOperation):
            return None
        if other.op.value not in {"+", "-"}:
            return None

        for lhs, rhs in ((other.left, other.right), (other.right, other.left)):
            if name(lhs) == name(ref) and int_value(rhs) is not None:
                return rhs.value + 1

        return None

    if name(expr.left) and name(expr.left) == name(expr.right):
        return 1

    return width_from(expr.left, expr.right) or width_from(expr.right, expr.left)


class InferTypesMutator(ExprMutator):
    """Mutator to annote inferred types to a metamodel."""

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context):
        raise NotImplementedError(
            f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}"
        )

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
                logger.warning("Binary Operation needs inferred type.")
                expr.ty = None
                return expr
            elif expr.right.ty is None:
                logger.warning("Binary Operation needs inferred type.")
                expr.ty = None
                return expr
            assert isinstance(expr.left.ty, type_info.PrimitiveType)
            assert isinstance(expr.right.ty, type_info.PrimitiveType)
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
            expr.ty = type_info.PrimitiveType(kind, wr)
        else:
            if expr.op.value in ["||", "&&"]:
                expr.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 1)  # unsigned<1> / bool
            elif expr.op.value in ["<", ">", "==", "!=", ">=", "<="]:
                expr.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 1)  # unsigned<1> / bool
        assert expr.ty is not None

        return expr

    @generate.register
    def _(self, expr: behav.SliceOperation, context):
        expr.expr = self.generate(expr.expr, context)
        expr.left = self.generate(expr.left, context)
        expr.right = self.generate(expr.right, context)

        # type inference
        if expr.expr.ty is None:
            context.emit_warning(
                "Can not infer type of non-static slice operation.",
                "infer-type",
                logger=logger,
                line_info=expr.expr.line_info,
            )
            return expr
        assert isinstance(expr.expr.ty, (type_info.PrimitiveType))
        ty = expr.expr.ty
        # For non-static slices, we cann not infer the type!
        if isinstance(expr.left, behav.Literal) and isinstance(expr.right, behav.Literal):
            lval = expr.left.value
            rval = expr.right.value
            width = lval - rval + 1 if lval > rval else rval - lval + 1
        elif isinstance(expr.left, behav.Literal):
            logger.warning("Can not infer type of non-static slice operation.")
            return expr
        elif isinstance(expr.right, behav.Literal):
            logger.warning("Can not infer type of non-static slice operation.")
            return expr
        else:
            width = infer_slice_sice_helper(expr)
            if width is None:
                context.emit_warning(
                    "Can not infer type of non-static slice operation.",
                    "infer-non-static-slice",
                    logger=logger,
                    line_info=expr.left.line_info,
                )
                return expr
        ty_ = copy(ty)
        if isinstance(ty_, type_info.PrimitiveType):
            ty_.size = width
        elif isinstance(ty_, type_info.ArrayType):
            if width == 1:  # Array -> PrimitiveType
                ty_ = ty_.element_type
            else:  # Array Slice
                ty_.length = arch.get_const_or_val(width)
        else:
            raise f"Type Slicing not supported for type {ty_}"

        expr.ty = ty_
        return expr

    @generate.register
    def _(self, expr: behav.ConcatOperation, context):
        expr.left = self.generate(expr.left, context)
        expr.right = self.generate(expr.right, context)
        if expr.left.ty is None:
            logger.warning("Concat Operation needs inferred type.")
            return expr
        if expr.right.ty is None:
            logger.warning("Concat Operation needs inferred type.")
            return expr
        width = arch.get_const_or_val(expr.left.ty.size) + arch.get_const_or_val(expr.right.ty.size)
        size = arch.get_const_or_val(width)
        ty = type_info.PrimitiveType(type_info.TypeKind.UINT, size)
        expr.ty = ty

        return expr

    # behav.IntLiteral
    @generate.register
    def _(self, expr: behav.Literal, context):
        # type inference
        assert expr.ty.size is not None
        assert expr.ty.kind.is_int

        expr.ty = type_info.PrimitiveType(expr.ty.kind, expr.ty.size)
        return expr

    # behav.IntLiteral
    @generate.register
    def _(self, expr: behav.Tensor, context):
        # type inference
        assert expr.ty.length is not None
        assert expr.ty.element_type.kind.is_int

        expr.ty = type_info.ArrayType(expr.ty.element_type, expr.ty.length)
        return expr

    @generate.register
    def _(self, expr: behav.VarDefinition, context):
        # type inference
        assert isinstance(expr.var.ty, (type_info.PrimitiveType, type_info.ArrayType))
        if isinstance(expr.var.ty, type_info.ArrayType):
            assert expr.var.ty.element_type.size is not None
            assert expr.var.ty.element_type.kind.is_int
        elif isinstance(expr.var.ty, type_info.PrimitiveType):
            assert expr.var.ty.size is not None
            assert expr.var.ty.kind.is_int
        expr.ty = expr.var.ty
        return expr

    @generate.register
    def _(self, expr: behav.Assignment, context):
        expr.target = self.generate(expr.target, context)
        expr.expr = self.generate(expr.expr, context)

        # if isinstance(expr.expr, behav.IntLiteral) and isinstance(expr.target, behav.VarDefinition):
        #       expr.target.var.value = expr.expr.value

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
            expr.ty = type_info.PrimitiveType(type_info.TypeKind.INT, wr)

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
                ty = type_info.PrimitiveType(type_info.TypeKind.INT, w1 + 1)
            elif expr.op.value == "~":
                ty = type_info.PrimitiveType(type_info.TypeKind.INT, w1)
            elif expr.op.value == "!":
                ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 1)
            else:
                ty = None
            expr.ty = ty

        return expr

    @generate.register
    def _(self, expr: behav.NamedReference, context):
        reference = expr.reference

        if isinstance(reference, arch.BitFieldDescr):
            assert reference.ty.kind.is_int
            expr.ty = reference.ty
        elif isinstance(reference, (arch.Variable, arch.Memory, arch.RegisterBank, arch.Register)):
            assert isinstance(reference.ty, (type_info.PrimitiveType, type_info.ArrayType))
            # Constant-time calculation of sizes
            if isinstance(reference.ty, type_info.PrimitiveType):
                reference.ty.size = arch.get_const_or_val(reference.ty.size)
            elif isinstance(reference.ty, type_info.ArrayType):
                reference.ty.length = arch.get_const_or_val(reference.ty.length)
            expr.ty = reference.ty
        elif isinstance(reference, arch.Alias):  # propagate type from aliased mem or reg bank
            assert reference.length == 1
            if isinstance(reference.parent, (arch.Memory, arch.RegisterBank, arch.Variable)):
                # expr.ty = self.generate(behav.NamedReference(reference.parent), context)
                assert isinstance(reference.ty, type_info.PointerType)
                expr.ty = reference.ty.ty
                assert expr.ty is not None
            elif isinstance(reference.parent, arch.Register):
                expr.ty = reference.parent.ty
                assert expr.ty is not None
            else:
                raise NotImplementedError(
                    f"Alias parent type {type(reference.parent)} not supported for type inference"
                )
        elif isinstance(reference, arch.Intrinsic):
            assert reference.ty.kind.is_int and isinstance(reference.ty, type_info.PrimitiveType)
            expr.ty = reference.ty
        elif isinstance(reference, arch.Parameter):
            kind = type_info.TypeKind.INT if reference.signed else type_info.TypeKind.UINT
            expr.ty = type_info.PrimitiveType(kind, reference.size)
        elif isinstance(reference, arch.FnParam):
            expr.ty = reference.ty
        else:
            assert False, "Unhandled reference"

        return expr

    @generate.register
    def _(self, expr: behav.IndexedReference, context):
        expr.index = self.generate(expr.index, context)

        assert isinstance(expr.reference, (arch.Memory, arch.RegisterBank, arch.Variable))
        assert isinstance(expr.reference.ty, type_info.ArrayType)
        # expr.reference = self.generate(behav.NamedReference(expr.reference), context)

        if expr.right is not None:
            expr.right = self.generate(expr.right, context)

        # type inference
        assert expr.reference.ty.element_type.kind.is_int
        single_mem_acc_size = expr.reference.ty.element_type.size

        ## Simple eval check for ranged access.
        # Little-endian interpretation:
        # - lhs > rhs  → width = lhs - rhs + 1
        # - lhs == rhs → width = 8 bits

        if expr.right is None:
            size = single_mem_acc_size
        else:
            lhs_offset = helper_expr_size(expr.index)
            rhs_offset = helper_expr_size(expr.right)
            assert lhs_offset >= rhs_offset
            size = (lhs_offset - rhs_offset + 1) * single_mem_acc_size

        ty_ = type_info.PrimitiveType(expr.reference.ty.element_type.kind, size)

        expr.ty = ty_
        assert expr.ty is not None

        return expr

    @generate.register
    def _(self, expr: behav.TypeConv, context):
        expr.expr = self.generate(expr.expr, context)

        ty = deepcopy(expr.expr.ty)
        if ty is None:
            context.emit_warning("Type conv needs inferred type.", "infer-type", logger=logger, line_info=expr.expr.line_info)
            return expr
        assert isinstance(ty, type_info.PrimitiveType)
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
            if not (expr.ref_or_name.ty.kind == type_info.TypeKind.VOID):
                assert expr.ref_or_name.ty.kind.is_int
                width = arch.get_const_or_val(expr.ref_or_name.ty.size)
                expr.ty = type_info.PrimitiveType(expr.ref_or_name.ty.kind, arch.get_const_or_val(width))
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
                return -1 * int(expr.right.value)
        else:
            raise (f"Not supported Operation value Type {expr.op.value} within mem access range")

    elif type(sub_expr) == behav.NamedReference:
        return 0
    else:
        raise (f"Not supported expr Type {type(sub_expr)} within mem access range")
