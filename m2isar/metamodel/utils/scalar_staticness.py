# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Transformation functions to determine which vars in a function or instruction
behavior are to be considered static.
"""

import dataclasses
from functools import singledispatchmethod
from typing import Any, cast

from ...metamodel import arch, behav, attribute_info
from .ExprVisitor import ExprVisitor

# pylint: disable=unused-argument

class VarAccessVisitor(ExprVisitor):
	"""Visitor that determines Variable staticness for behavior expression trees."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

	@generate.register
	def _(self, expr: behav.Operation, context: attribute_info.AccessContext):
		statements = []
		for stmt in expr.statements:
			temp = self.generate(stmt, context)
			if isinstance(temp, list):
				statements.extend(temp)
			else:
				statements.append(temp)

		return expr

	@generate.register
	def _(self, expr: behav.Block, context: attribute_info.AccessContext):
		explicit_attrs = getattr(expr, "explicit_attributes", set(expr.attributes))
		explicit = attribute_info.BlockAttribute.ACCESS in explicit_attrs
		access = expr.attributes.get(attribute_info.BlockAttribute.ACCESS) if explicit else context.access_is_static

		block_context = dataclasses.replace(context, access_is_static=access)
		stmts = [self.generate(x, block_context) for x in expr.statements]
		valid = [s for s in stmts if s is not None]
		result = min([access] + valid)
		if not explicit:
			expr.attributes[attribute_info.BlockAttribute.ACCESS] = result
		return result

	@generate.register
	def _(self, expr: behav.BinaryOperation, context: attribute_info.AccessContext):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(left, right)

	@generate.register
	def _(self, expr: behav.SliceOperation, context: attribute_info.AccessContext):
		expr_result = self.generate(expr.expr, context)
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(expr_result, left, right)

	@generate.register
	def _(self, expr: behav.ConcatOperation, context: attribute_info.AccessContext):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return min(left, right)

	@generate.register
	def _(self, expr: behav.Literal, context: attribute_info.AccessContext):
		return attribute_info.AccessAttribute.READ

	@generate.register
	def _(self, expr: behav.Tensor, context: attribute_info.AccessContext):
		return attribute_info.AccessAttribute.READ

	@generate.register
	def _(self, expr: behav.VarDefinition, context: attribute_info.AccessContext):
		var = cast(Any, expr.var)
		var.attributes["static"] = attribute_info.AccessAttribute.RW
		return attribute_info.AccessAttribute.RW

	@generate.register
	def _(self, expr: behav.Break, context):
		return context.access_is_static

	@generate.register
	def _(self, expr: behav.Continue, context):
		return context.access_is_static

	@generate.register
	def _(self, expr: behav.Assignment, context: attribute_info.AccessContext):
		self.generate(expr.target, context)

		expr_static = attribute_info.AccessAttribute.NONE
		if context.access_is_static != attribute_info.AccessAttribute.NONE or isinstance(expr.target, behav.VarDefinition):
			expr_static = self.generate(expr.expr, context)

			if expr_static != attribute_info.AccessAttribute.NONE:
				expr_static = attribute_info.AccessAttribute.RW
		else:
			expr_static = attribute_info.AccessAttribute.NONE

		if isinstance(expr.target, behav.NamedReference) and isinstance(expr.target.reference, arch.Variable):
			target_ref = cast(Any, expr.target.reference)
			target_ref.attributes["static"] &= expr_static

		if isinstance(expr.target, behav.VarDefinition):
			target_var = cast(Any, expr.target.var)
			target_var.attributes["static"] &= expr_static

	@generate.register
	def _(self, expr: behav.Conditional, context: attribute_info.AccessContext):
		conds = [self.generate(x, context) for x in expr.conds]
		stmt_context = dataclasses.replace(context, access_is_static=min(conds))
		stmts = [self.generate(x, stmt_context) for x in expr.stmts]
		return min(conds + [x for x in stmts if x is not None])

	@generate.register
	def _(self, expr: behav.LoopBase, context: attribute_info.AccessContext):
		init = [self.generate(x, context) for x in expr.init]
		cond = self.generate(expr.cond, context)
		stmt_context = dataclasses.replace(context, access_is_static=cond)
		stmts = [self.generate(x, stmt_context) for x in expr.stmts]
		updates = [self.generate(x, stmt_context) for x in expr.updates]
		valid = [x for x in init + [cond] + stmts + updates if x is not None]
		loop_access = min(valid) if valid else cond

		# A for-loop iterator belongs to the same execution domain as its loop.
		# If a runtime-dependent branch (including break/continue) makes the body
		# dynamic, its initializer and update must not remain generator-static.
		for init_stmt in expr.init:
			if isinstance(init_stmt, behav.Assignment) and isinstance(init_stmt.target, behav.VarDefinition):
				init_stmt.target.var.attributes["static"] &= loop_access

		return loop_access

	@generate.register
	def _(self, expr: behav.Ternary, context: attribute_info.AccessContext):
		cond = self.generate(expr.cond, context)
		then_expr = self.generate(expr.then_expr, context)
		else_expr = self.generate(expr.else_expr, context)

		return min(cond, then_expr, else_expr)

	@generate.register
	def _(self, expr: behav.Return, context: attribute_info.AccessContext):
		if expr.expr is not None:
			return self.generate(expr.expr, context)

		return attribute_info.AccessAttribute.RW

	@generate.register
	def _(self, expr: behav.UnaryOperation, context: attribute_info.AccessContext):
		right = self.generate(expr.right, context)

		return right

	@generate.register
	def _(self, expr: behav.NamedReference, context: attribute_info.AccessContext):
		if isinstance(expr.reference, arch.Variable):
			return expr.reference.attributes.get("static")

		static_map = {
			arch.Memory: attribute_info.AccessAttribute.NONE,
			arch.RegisterBank: attribute_info.AccessAttribute.NONE,
			arch.Register: attribute_info.AccessAttribute.NONE,
			arch.Alias: attribute_info.AccessAttribute.NONE,
			arch.BitFieldDescr: attribute_info.AccessAttribute.READ,
			arch.Parameter: attribute_info.AccessAttribute.READ,
			arch.FnParam: attribute_info.AccessAttribute.READ
		}

		return static_map.get(type(expr.reference), attribute_info.AccessAttribute.NONE)

	@generate.register
	def _(self, expr: behav.IndexedReference, context: attribute_info.AccessContext):
		self.generate(expr.index, context)

		return attribute_info.AccessAttribute.NONE

	@generate.register
	def _(self, expr: behav.TypeConv, context: attribute_info.AccessContext):
		expr_result = self.generate(expr.expr, context)

		return expr_result

	@generate.register
	def _(self, expr: behav.Callable, context: attribute_info.AccessContext):
		args = [self.generate(arg, context) for arg in expr.args]
		is_static = bool(expr.ref_or_name.attributes.get("static", False))
		args.append(attribute_info.AccessAttribute.READ if is_static else attribute_info.AccessAttribute.NONE)

		return min(args)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context: attribute_info.AccessContext):
		args = [self.generate(arg, context) for arg in expr.args]
		is_static = bool(expr.ref_or_name.attributes.get("static", False))
		args.append(attribute_info.AccessAttribute.READ if is_static else attribute_info.AccessAttribute.NONE)
		return min(args)

	@generate.register
	def _(self, expr: behav.Group, context: attribute_info.AccessContext):
		expr_result = self.generate(expr.expr, context)

		return expr_result
