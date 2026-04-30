# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Transformation functions to determine which scalars in a function or instruction
behavior are to be considered static.
"""

import dataclasses
from functools import singledispatchmethod
from typing import Any, cast

from ...metamodel import arch, behav, type_info
from .ExprVisitor import ExprVisitor

# pylint: disable=unused-argument

class ScalarStaticnessVisitor(ExprVisitor):
	"""Visitor that determines scalar staticness for behavior expression trees."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

	@generate.register
	def _(self, expr: behav.Operation, context: type_info.ScalarStaticnessContext):
		statements = []
		for stmt in expr.statements:
			temp = self.generate(stmt, context)
			if isinstance(temp, list):
				statements.extend(temp)
			else:
				statements.append(temp)

		return expr

	@generate.register
	def _(self, expr: behav.Block, context):
		stmts = [self.generate(x, context) for x in expr.statements]
		valid = [s for s in stmts if s is not None]
		if not valid:
			return type_info.StaticType.NONE
		return min(valid)

	@generate.register
	def _(self, expr: behav.BinaryOperation, context: type_info.ScalarStaticnessContext):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(left, right)

	@generate.register
	def _(self, expr: behav.SliceOperation, context: type_info.ScalarStaticnessContext):
		expr_result = self.generate(expr.expr, context)
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(expr_result, left, right)

	@generate.register
	def _(self, expr: behav.ConcatOperation, context: type_info.ScalarStaticnessContext):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(left, right)

	@generate.register
	def _(self, expr: behav.Literal, context: type_info.ScalarStaticnessContext):
		return type_info.StaticType.READ


	@generate.register
	def _(self, expr: behav.ScalarDefinition, context: type_info.ScalarStaticnessContext):
		scalar = cast(Any, expr.scalar)
		scalar.static = type_info.StaticType.RW
		return type_info.StaticType.RW

	@generate.register
	def _(self, expr: behav.Break, context):
		return type_info.StaticType.READ

	@generate.register
	def _(self, expr: behav.Assignment, context: type_info.ScalarStaticnessContext):
		self.generate(expr.target, context)

		if context.context_is_static != type_info.StaticType.NONE or isinstance(expr.target, behav.ScalarDefinition):
			expr_static = self.generate(expr.expr, context)

			if expr_static != type_info.StaticType.NONE:
				expr_static = type_info.StaticType.RW
		else:
			expr_static = type_info.StaticType.NONE

		if isinstance(expr.target, behav.NamedReference) and isinstance(expr.target.reference, arch.Scalar):
			target_ref = cast(Any, expr.target.reference)
			target_ref.static &= expr_static

		if isinstance(expr.target, behav.ScalarDefinition):
			target_scalar = cast(Any, expr.target.scalar)
			target_scalar.static &= expr_static

	@generate.register
	def _(self, expr: behav.Conditional, context: type_info.ScalarStaticnessContext):
		conds = [self.generate(x, context) for x in expr.conds]
		stmt_context = dataclasses.replace(context, context_is_static=min(conds))
		_ = [self.generate(x, stmt_context) for x in expr.stmts]

	@generate.register
	def _(self, expr: behav.Loop, context: type_info.ScalarStaticnessContext):
		cond = self.generate(expr.cond, context)
		stmt_context = dataclasses.replace(context, context_is_static=cond)
		_ = [self.generate(x, stmt_context) for x in expr.stmts]

	@generate.register
	def _(self, expr: behav.Ternary, context: type_info.ScalarStaticnessContext):
		cond = self.generate(expr.cond, context)
		then_expr = self.generate(expr.then_expr, context)
		else_expr = self.generate(expr.else_expr, context)

		return min(cond, then_expr, else_expr)

	@generate.register
	def _(self, expr: behav.Return, context: type_info.ScalarStaticnessContext):
		if expr.expr is not None:
			return self.generate(expr.expr, context)

		return type_info.StaticType.RW

	@generate.register
	def _(self, expr: behav.UnaryOperation, context: type_info.ScalarStaticnessContext):
		right = self.generate(expr.right, context)

		return right

	@generate.register
	def _(self, expr: behav.NamedReference, context: type_info.ScalarStaticnessContext):
		if isinstance(expr.reference, arch.Scalar):
			return expr.reference.static

		static_map = {
			arch.Memory: type_info.StaticType.NONE,
			arch.BitFieldDescr: type_info.StaticType.READ,
			arch.Constant: type_info.StaticType.READ,
			arch.FnParam: type_info.StaticType.READ
		}

		return static_map.get(type(expr.reference), type_info.StaticType.NONE)

	@generate.register
	def _(self, expr: behav.IndexedReference, context: type_info.ScalarStaticnessContext):
		self.generate(expr.index, context)

		return type_info.StaticType.NONE

	@generate.register
	def _(self, expr: behav.TypeConv, context: type_info.ScalarStaticnessContext):
		expr_result = self.generate(expr.expr, context)

		return expr_result

	@generate.register
	def _(self, expr: behav.Callable, context: type_info.ScalarStaticnessContext):
		args = [self.generate(arg, context) for arg in expr.args]
		is_static = bool(getattr(expr.ref_or_name, "static", False))
		args.append(type_info.StaticType.READ if is_static else type_info.StaticType.NONE)

		return min(args)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context: type_info.ScalarStaticnessContext):
		args = [self.generate(arg, context) for arg in expr.args]
		is_static = bool(getattr(expr.ref_or_name, "static", False))
		args.append(type_info.StaticType.READ if is_static else type_info.StaticType.NONE)

		return min(args)

	@generate.register
	def _(self, expr: behav.Group, context: type_info.ScalarStaticnessContext):
		expr_result = self.generate(expr.expr, context)

		return expr_result
