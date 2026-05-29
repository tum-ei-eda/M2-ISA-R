# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Transformation functions to determine whether a function is considered to be static."""

from functools import singledispatchmethod

from ...metamodel import arch, behav
from .ExprVisitor import ExprVisitor

# pylint: disable=unused-argument

class FunctionStaticnessVisitor(ExprVisitor):
	"""Visitor that determines whether behavior expression trees are static."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

	@generate.register
	def _(self, expr: behav.Operation, context):
		statements = []
		for stmt in expr.statements:
			temp = self.generate(stmt, context)
			if isinstance(temp, list):
				statements.extend(temp)
			else:
				statements.append(temp)

		return all(statements)

	@generate.register
	def _(self, expr: behav.Block, context):
		stmts = [self.generate(x, context) for x in expr.statements]
		return all(stmts)

	@generate.register
	def _(self, expr: behav.BinaryOperation, context):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return all([left, right])

	@generate.register
	def _(self, expr: behav.SliceOperation, context):
		expr_result = self.generate(expr.expr, context)
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return all([expr_result, left, right])

	@generate.register
	def _(self, expr: behav.ConcatOperation, context):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return all([left, right])

	@generate.register
	def _(self, expr: behav.Literal, context):
		return True

	@generate.register
	def _(self, expr: behav.ScalarDefinition, context):
		return True

	@generate.register
	def _(self, expr: behav.Break, context):
		return True

	@generate.register
	def _(self, expr: behav.Assignment, context):
		target = self.generate(expr.target, context)
		expr_result = self.generate(expr.expr, context)

		return all([target, expr_result])

	@generate.register
	def _(self, expr: behav.Conditional, context):
		conds = [self.generate(x, context) for x in expr.conds]
		stmts = [self.generate(x, context) for x in expr.stmts]

		conds.extend(stmts)

		return all(conds)

	@generate.register
	def _(self, expr: behav.Loop, context):
		cond = self.generate(expr.cond, context)
		stmts = [self.generate(x, context) for x in expr.stmts]
		stmts.append(cond)

		return all(stmts)

	@generate.register
	def _(self, expr: behav.Ternary, context):
		cond = self.generate(expr.cond, context)
		then_expr = self.generate(expr.then_expr, context)
		else_expr = self.generate(expr.else_expr, context)

		return all([cond, then_expr, else_expr])

	@generate.register
	def _(self, expr: behav.Return, context):
		if expr.expr is not None:
			return self.generate(expr.expr, context)

		return True

	@generate.register
	def _(self, expr: behav.UnaryOperation, context):
		right = self.generate(expr.right, context)

		return right

	@generate.register
	def _(self, expr: behav.NamedReference, context):
		if isinstance(expr.reference, arch.Variable):
			return expr.reference.attributes.get("static")

		static_map = {
			arch.Memory: False,
			arch.BitFieldDescr: True,
			arch.Parameter: True,
			arch.FnParam: True,
			arch.Variable: True,
			arch.Intrinsic: False
		}

		return static_map.get(type(expr.reference), False)

	@generate.register
	def _(self, expr: behav.IndexedReference, context):
		self.generate(expr.index, context)

		return False

	@generate.register
	def _(self, expr: behav.TypeConv, context):
		expr_result = self.generate(expr.expr, context)

		return expr_result

	@generate.register
	def _(self, expr: behav.Callable, context):
		args = [self.generate(arg, context) for arg in expr.args]
		args.append(bool(getattr(expr.ref_or_name, "static", False)))

		return all(args)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context):
		args = [self.generate(arg, context) for arg in expr.args]
		args.append(bool(getattr(expr.ref_or_name, "static", False)))

		return all(args)

	@generate.register
	def _(self, expr: behav.Group, context):
		expr_result = self.generate(expr.expr, context)

		return expr_result
