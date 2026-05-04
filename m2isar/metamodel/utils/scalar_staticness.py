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

from ...metamodel import arch, behav, attribute_info
from .ExprVisitor import ExprVisitor

# pylint: disable=unused-argument

class ScalarStaticnessVisitor(ExprVisitor):
	"""Visitor that determines scalar staticness for behavior expression trees."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

	@generate.register
	def _(self, expr: behav.Operation, context: attribute_info.ScalarStaticnessContext):
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
			return attribute_info.StaticAttribute.NONE
		return min(valid)

	@generate.register
	def _(self, expr: behav.BinaryOperation, context: attribute_info.ScalarStaticnessContext):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(left, right)

	@generate.register
	def _(self, expr: behav.SliceOperation, context: attribute_info.ScalarStaticnessContext):
		expr_result = self.generate(expr.expr, context)
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(expr_result, left, right)

	@generate.register
	def _(self, expr: behav.ConcatOperation, context: attribute_info.ScalarStaticnessContext):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(left, right)

	@generate.register
	def _(self, expr: behav.Literal, context: attribute_info.ScalarStaticnessContext):
		return attribute_info.StaticAttribute.READ


	@generate.register
	def _(self, expr: behav.ScalarDefinition, context: attribute_info.ScalarStaticnessContext):
		scalar = cast(Any, expr.scalar)
		scalar.attributes["static"] = attribute_info.StaticAttribute.RW
		return attribute_info.StaticAttribute.RW

	@generate.register
	def _(self, expr: behav.Break, context):
		return attribute_info.StaticAttribute.READ

	@generate.register
	def _(self, expr: behav.Assignment, context: attribute_info.ScalarStaticnessContext):
		self.generate(expr.target, context)

		if context.context_is_static != attribute_info.StaticAttribute.NONE or isinstance(expr.target, behav.ScalarDefinition):
			expr_static = self.generate(expr.expr, context)

			if expr_static != attribute_info.StaticAttribute.NONE:
				expr_static = attribute_info.StaticAttribute.RW
		else:
			expr_static = attribute_info.StaticAttribute.NONE

		if isinstance(expr.target, behav.NamedReference) and isinstance(expr.target.reference, arch.Variable):
			target_ref = cast(Any, expr.target.reference)
			target_ref.attributes["static"] &= expr_static

		if isinstance(expr.target, behav.ScalarDefinition):
			target_scalar = cast(Any, expr.target.scalar)
			target_scalar.attributes["static"] &= expr_static

	@generate.register
	def _(self, expr: behav.Conditional, context: attribute_info.ScalarStaticnessContext):
		conds = [self.generate(x, context) for x in expr.conds]
		stmt_context = dataclasses.replace(context, context_is_static=min(conds))
		_ = [self.generate(x, stmt_context) for x in expr.stmts]

	@generate.register
	def _(self, expr: behav.Loop, context: attribute_info.ScalarStaticnessContext):
		cond = self.generate(expr.cond, context)
		stmt_context = dataclasses.replace(context, context_is_static=cond)
		_ = [self.generate(x, stmt_context) for x in expr.stmts]

	@generate.register
	def _(self, expr: behav.Ternary, context: attribute_info.ScalarStaticnessContext):
		cond = self.generate(expr.cond, context)
		then_expr = self.generate(expr.then_expr, context)
		else_expr = self.generate(expr.else_expr, context)

		return min(cond, then_expr, else_expr)

	@generate.register
	def _(self, expr: behav.Return, context: attribute_info.ScalarStaticnessContext):
		if expr.expr is not None:
			return self.generate(expr.expr, context)

		return attribute_info.StaticAttribute.RW

	@generate.register
	def _(self, expr: behav.UnaryOperation, context: attribute_info.ScalarStaticnessContext):
		right = self.generate(expr.right, context)

		return right

	@generate.register
	def _(self, expr: behav.NamedReference, context: attribute_info.ScalarStaticnessContext):
		if isinstance(expr.reference, arch.Variable):
			return expr.reference.attributes.get("static")

		static_map = {
			arch.Memory: attribute_info.StaticAttribute.NONE,
			arch.BitFieldDescr: attribute_info.StaticAttribute.READ,
			arch.Constant: attribute_info.StaticAttribute.READ,
			arch.FnParam: attribute_info.StaticAttribute.READ
		}

		return static_map.get(type(expr.reference), attribute_info.StaticAttribute.NONE)

	@generate.register
	def _(self, expr: behav.IndexedReference, context: attribute_info.ScalarStaticnessContext):
		self.generate(expr.index, context)

		return attribute_info.StaticAttribute.NONE

	@generate.register
	def _(self, expr: behav.TypeConv, context: attribute_info.ScalarStaticnessContext):
		expr_result = self.generate(expr.expr, context)

		return expr_result

	@generate.register
	def _(self, expr: behav.Callable, context: attribute_info.ScalarStaticnessContext):
		args = [self.generate(arg, context) for arg in expr.args]
		is_static = bool(getattr(expr.ref_or_name, "static", False))
		args.append(attribute_info.StaticAttribute.READ if is_static else attribute_info.StaticAttribute.NONE)

		return min(args)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context: attribute_info.ScalarStaticnessContext):
		args = [self.generate(arg, context) for arg in expr.args]
		is_static = bool(getattr(expr.ref_or_name, "static", False))
		args.append(attribute_info.StaticAttribute.READ if is_static else attribute_info.StaticAttribute.NONE)

		return min(args)

	@generate.register
	def _(self, expr: behav.Group, context: attribute_info.ScalarStaticnessContext):
		expr_result = self.generate(expr.expr, context)

		return expr_result
