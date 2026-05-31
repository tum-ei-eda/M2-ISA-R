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

from ...metamodel import arch, behav, type_info
from .ExprVisitor import ExprVisitor
from functools import singledispatchmethod

# pylint: disable=unused-argument

class ExprSimplifierVisitor(ExprVisitor):
	"""Visitor that simplifies behavior expression trees."""

	@singledispatchmethod
	def generate(self, expr : behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")


	@generate.register
	def _(self, expr: behav.Operation, context):
		statements = []
		for stmt in expr.statements:
			try:
				temp = self.generate(stmt, context)
				if isinstance(temp, list):
					statements.extend(temp)
				else:
					statements.append(temp)
			except (NotImplementedError, ValueError):
				print(f"cant simplify {stmt}")

		expr.statements = statements
		return expr

	@generate.register
	def _(self, expr: behav.Block, context):
		expr.statements = [self.generate(x, context) for x in expr.statements]
		return expr

	@generate.register
	def _(self, expr: behav.BinaryOperation, context):
		expr.left = self.generate(expr.left, context)
		expr.right = self.generate(expr.right, context)

		if isinstance(expr.left, behav.Literal) and isinstance(expr.right, (behav.NamedReference, behav.IndexedReference)):
			if expr.left.ty.size < arch.get_const_or_val(expr.right.reference.ty.size):
				expr.left.ty.size = arch.get_const_or_val(expr.right.reference.ty.size)

		if isinstance(expr.right, behav.Literal) and isinstance(expr.left, (behav.NamedReference, behav.IndexedReference)):
			if isinstance(expr.left.ty, type_info.ArrayType):
				if expr.right.ty.size < arch.get_const_or_val(expr.left.reference.ty.element_type.size):
					expr.right.ty.size = arch.get_const_or_val(expr.left.reference.ty.element_type.size)
			else:
				if expr.right.ty.size < arch.get_const_or_val(expr.left.ty.size):
					expr.right.ty.size = arch.get_const_or_val(expr.left.ty.size)

		if isinstance(expr.left, behav.Literal) and isinstance(expr.right, behav.Literal):
			# pylint: disable=eval-used
			res: int = int(eval(f"{expr.left.value}{expr.op.value}{expr.right.value}"))
			if res < 0 or expr.left.ty.kind == type_info.TypeKind.INT or expr.right.ty.kind == type_info.TypeKind.INT:
				kind = type_info.TypeKind.INT
			else:
				kind = type_info.TypeKind.UINT
			return behav.Literal(res, type_info.PrimitiveType(kind, max(arch.get_const_or_val(expr.left.ty.size), arch.get_const_or_val(expr.right.ty.size), res.bit_length())))

		if expr.op.value == "&&":
			if isinstance(expr.left, behav.Literal):
				if expr.left.value:
					return expr.right
				return expr.left

			if isinstance(expr.right, behav.Literal):
				if expr.right.value:
					return expr.left
				return expr.right

		if expr.op.value == "||":
			if isinstance(expr.left, behav.Literal):
				if expr.left.value:
					return expr.left
				return expr.right

			if isinstance(expr.right, behav.Literal):
				if expr.right.value:
					return expr.right
				return expr.left

		return expr

	@generate.register
	def _(self, expr: behav.SliceOperation, context):
		expr.expr = self.generate(expr.expr, context)
		expr.left = self.generate(expr.left, context)
		expr.right = self.generate(expr.right, context)

		return expr

	@generate.register
	def _(self, expr: behav.ConcatOperation, context):
		expr.left = self.generate(expr.left, context)
		expr.right = self.generate(expr.right, context)

		return expr

	@generate.register
	def _(self, expr: behav.Literal, context):
		return expr

	@generate.register
	def _(self, expr: behav.VarDefinition, context):
		return expr

	@generate.register
	def _(self, expr: behav.Break, context):
		return expr

	@generate.register
	def _(self, expr: behav.Assignment, context):
		expr.target = self.generate(expr.target, context)
		expr.expr = self.generate(expr.expr, context)

		if isinstance(expr.expr, behav.Literal) and isinstance(expr.target, (behav.NamedReference, behav.IndexedReference)):
			if expr.expr.ty.size < arch.get_const_or_val(expr.target.ty.size):
				expr.expr.ty.size = arch.get_const_or_val(expr.target.ty.size)

		return expr

	@generate.register
	def _(self, expr: behav.Conditional, context):
		expr.conds = [self.generate(x, context) for x in expr.conds]
		expr.stmts = [self.generate(x, context) for x in expr.stmts]

		eval_false = True

		conds = []
		stmts = []

		for cond, stmt in zip(expr.conds, expr.stmts):
			if isinstance(cond, behav.Literal):
				if cond.value:
					return stmt
			else:
				conds.append(cond)
				stmts.append(stmt)
				eval_false = False

		if len(expr.conds) < len(expr.stmts):
			if eval_false and isinstance(expr.conds[-1], behav.Literal):
				if not cond.value:  # pylint: disable=undefined-loop-variable
					return expr.stmts[-1]
			stmts.append(expr.stmts[-1])

		expr.conds = conds
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

		if isinstance(expr.cond, behav.Literal):
			if expr.cond.value:
				return expr.then_expr

			return expr.else_expr

		return expr

	@generate.register
	def _(self, expr: behav.Return, context):
		if expr.expr is not None:
			expr.expr = self.generate(expr.expr, context)

		return expr

	@generate.register
	def _(self, expr: behav.UnaryOperation, context):
		expr.right = self.generate(expr.right, context)
		if isinstance(expr.right, behav.Literal):
			# pylint: disable=eval-used
			res: int = eval(f"{expr.op.value}{expr.right.value}")
			if res < 0:
				kind = type_info.TypeKind.INT
			else:
				kind = expr.right.ty.kind
			return behav.Literal(res, type_info.PrimitiveType(kind, max(expr.right.ty.size, res.bit_length())))

		return expr

	@generate.register
	def _(self, expr: behav.NamedReference, context):
		if isinstance(expr.reference, arch.Parameter):
			if expr.reference.signed:
				kind = type_info.TypeKind.INT
			else:
				kind = type_info.TypeKind.UINT
			return behav.Literal(expr.reference.value, type_info.PrimitiveType(kind, arch.get_const_or_val(expr.reference.size)))

		return expr

	@generate.register
	def _(self, expr: behav.IndexedReference, context):
		expr.index = self.generate(expr.index, context)

		return expr

	@generate.register
	def _(self, expr: behav.TypeConv, context):
		expr.expr = self.generate(expr.expr, context)
		if isinstance(expr.expr, behav.Literal):
			size = expr.size
			if size is None:
				assert expr.ty is not None
				size = expr.ty.size
				assert size is not None
			expr.expr.bit_size = size
			assert expr.expr.bit_size is not None
			expr.expr.signed = expr.data_type == type_info.TypeKind.INT
			return expr.expr

		return expr

	@generate.register
	def _(self, expr: behav.Callable, context):
		expr.args = [self.generate(stmt, context) for stmt in expr.args]

		return expr

	@generate.register
	def _(self, expr: behav.ProcedureCall, context):
		expr.args = [self.generate(stmt, context) for stmt in expr.args]

		return expr

	@generate.register
	def _(self, expr: behav.Group, context):
		expr.expr = self.generate(expr.expr, context)

		if isinstance(expr.expr, behav.Literal):
			return expr.expr

		return expr
