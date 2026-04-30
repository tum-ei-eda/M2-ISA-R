# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Tranformation functions to determine whether a function throws an exception."""

from functools import reduce
from functools import singledispatchmethod
from operator import or_
from typing import Any

from ...metamodel import arch, behav, type_info, attribute_info
from .ExprVisitor import ExprVisitor

# pylint: disable=unused-argument

class FunctionThrowsVisitor(ExprVisitor):
	"""Visitor that determines whether behavior expression trees can throw exceptions."""

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

		return reduce(or_, statements, attribute_info.FunctionThrows.NO)

	@generate.register
	def _(self, expr: behav.Block, context):
		stmts = [self.generate(x, context) for x in expr.statements]
		return reduce(or_, stmts, attribute_info.FunctionThrows.NO)

	@generate.register
	def _(self, expr: behav.BinaryOperation, context):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return reduce(or_, [left, right])

	@generate.register
	def _(self, expr: behav.SliceOperation, context):
		expr_result = self.generate(expr.expr, context)
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return reduce(or_, [expr_result, left, right])

	@generate.register
	def _(self, expr: behav.ConcatOperation, context):
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		return reduce(or_, [left, right])

	@generate.register
	def _(self, expr: behav.Literal, context):
		return attribute_info.FunctionThrows.NO

	@generate.register
	def _(self, expr: behav.ScalarDefinition, context):
		return attribute_info.FunctionThrows.NO

	@generate.register
	def _(self, expr: behav.Break, context):
		return attribute_info.FunctionThrows.NO

	@generate.register
	def _(self, expr: behav.Assignment, context):
		target = self.generate(expr.target, context)
		expr_result = self.generate(expr.expr, context)

		return reduce(or_, [target, expr_result])

	@generate.register
	def _(self, expr: behav.Conditional, context):
		conds = [self.generate(x, context) for x in expr.conds]
		stmts = [self.generate(x, context) for x in expr.stmts]

		conds.extend(stmts)

		return attribute_info.FunctionThrows.MAYBE if reduce(or_, conds) else attribute_info.FunctionThrows.NO

	@generate.register
	def _(self, expr: behav.Loop, context):
		cond = self.generate(expr.cond, context)
		stmts = [self.generate(x, context) for x in expr.stmts]
		stmts.append(cond)

		return reduce(or_, stmts)

	@generate.register
	def _(self, expr: behav.Ternary, context):
		cond = self.generate(expr.cond, context)
		then_expr = self.generate(expr.then_expr, context)
		else_expr = self.generate(expr.else_expr, context)

		return reduce(or_, [cond, then_expr, else_expr])

	@generate.register
	def _(self, expr: behav.Return, context):
		if expr.expr is not None:
			return self.generate(expr.expr, context)

		return attribute_info.FunctionThrows.NO

	@generate.register
	def _(self, expr: behav.UnaryOperation, context):
		right = self.generate(expr.right, context)

		return right

	@generate.register
	def _(self, expr: behav.NamedReference, context):
		if isinstance(expr.reference, arch.Memory) and attribute_info.MemoryAttribute.ETISS_CAN_FAIL in expr.reference.attributes:
			return attribute_info.FunctionThrows.YES

		return attribute_info.FunctionThrows.NO

	@generate.register
	def _(self, expr: behav.IndexedReference, context):
		if isinstance(expr.reference, arch.Memory) and attribute_info.MemoryAttribute.ETISS_CAN_FAIL in expr.reference.attributes:
			return attribute_info.FunctionThrows.YES

		return self.generate(expr.index, context)

	@generate.register
	def _(self, expr: behav.TypeConv, context):
		expr_result = self.generate(expr.expr, context)

		return expr_result

	@generate.register
	def _(self, expr: behav.Callable, context):
		args = [self.generate(arg, context) for arg in expr.args]
		throws = getattr(expr.ref_or_name, "throws", attribute_info.FunctionThrows.NO)
		args.append(throws if isinstance(throws, attribute_info.FunctionThrows) else cast_to_throws(throws))

		return reduce(or_, args)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context):
		args = [self.generate(arg, context) for arg in expr.args]
		throws = getattr(expr.ref_or_name, "throws", attribute_info.FunctionThrows.NO)
		args.append(throws if isinstance(throws, attribute_info.FunctionThrows) else cast_to_throws(throws))

		return reduce(or_, args)

	@generate.register
	def _(self, expr: behav.Group, context):
		expr_result = self.generate(expr.expr, context)

		return expr_result


def cast_to_throws(throws: Any) -> attribute_info.FunctionThrows:
	"""Cast unknown throws values into FunctionThrows for robust visitor dispatch."""
	if isinstance(throws, bool):
		return attribute_info.FunctionThrows.YES if throws else attribute_info.FunctionThrows.NO
	return attribute_info.FunctionThrows(throws)
