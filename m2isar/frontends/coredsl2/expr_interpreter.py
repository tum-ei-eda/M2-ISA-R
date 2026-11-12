# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Very crude expression evaluation functions for use during model generation."""

from ... import M2ValueError
from ...diagnostics import M2ValidationError
from .constant_expressions import BINARY, cast_integer
from ...metamodel import arch, behav, type_info
from ...metamodel.utils.ExprVisitor import ExprVisitor
from functools import singledispatchmethod


class ExprInterpreterVisitor(ExprVisitor):
	"""Visitor for evaluating parse-time constant expressions."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}")

	@generate.register
	def _(self, expr: behav.Group, context):
		return self.generate(expr.expr, context)

	@generate.register
	def _(self, expr: behav.Literal, context):
		return int(expr.value)

	@generate.register
	def _(self, expr: behav.TypeConv, context):
		value = self.generate(expr.expr, context)
		width = arch.get_const_or_val(expr.size)
		if width is None:
			from ...transforms.infer_types.visitor import InferTypesMutator
			from ...warnings import WarningsManager
			InferTypesMutator().generate(expr.expr, WarningsManager(None))
			width = arch.get_const_or_val(expr.expr.ty.size)
		if not isinstance(width, int) or width <= 0:
			raise M2ValueError("cast width must be a positive constant")
		try:
			return cast_integer(value, width, expr.data_type == type_info.TypeKind.INT)
		except ValueError as exc:
			raise M2ValueError(str(exc)) from exc

	@generate.register
	def _(self, expr: behav.NamedReference, context):
		if isinstance(expr.reference, arch.Parameter) and expr.reference.value is not None:
			return expr.reference.value
		raise M2ValueError("non-interpretable value encountered")

	@generate.register
	def _(self, expr: behav.IndexedReference, context):
		idx = self.generate(expr.index, context)
		return expr.reference._initval[idx]

	@generate.register
	def _(self, expr: behav.BinaryOperation, context):
		left = self.generate(expr.left, context)
		op = expr.op.value
		if context and op == '&&' and not left:
			return 0
		if context and op == '||' and left:
			return 1
		right = self.generate(expr.right, context)
		if op in BINARY:
			return int(BINARY[op](left, right))
		if context and op in ('&&', '||'):
			return int(bool(right))
		if op == '/' or context and op == '%':
			if right == 0:
				raise M2ValidationError("Division by zero", 'DivisionByZero', expr.line_info)
			value = abs(left) // abs(right)
			quotient = -value if (left < 0) != (right < 0) else value
			return left - quotient * right if op == '%' else quotient
		if op in ('<<', '>>'):
			shift = right if op == '<<' else -right
			if shift > 100000:
				raise M2ValueError("constant shift is too large")
			return left << shift if shift >= 0 else left >> -shift
		raise M2ValidationError(f"Infix expression {op} is currently unsupported in constant expressions",
			'UnsupportedLanguageFeature', expr.line_info)

	@generate.register
	def _(self, expr: behav.Ternary, context):
		if not context:
			raise M2ValidationError("Ternary is not allowed in constant expression",
				'InvalidConstantExpressionNode', expr.line_info)
		branch = expr.then_expr if self.generate(expr.cond, context) else expr.else_expr
		return self.generate(branch, context)


	@generate.register
	def _(self, expr: behav.UnaryOperation, context):
		right = self.generate(expr.right, context)
		if expr.op.value == '-':
			return -right
		if context and expr.op.value in ('+', '~', '!'):
			if expr.op.value == '+':
				return right
			if expr.op.value == '!':
				return int(not right)
			from ...transforms.infer_types.visitor import InferTypesMutator
			from ...warnings import WarningsManager
			InferTypesMutator().generate(expr.right, WarningsManager(None))
			width = arch.get_const_or_val(expr.right.ty.size)
			if not isinstance(width, int) or width <= 0:
				raise M2ValueError("operand width must be a positive constant")
			try:
				return cast_integer(~right, width, expr.right.ty.kind == type_info.TypeKind.INT)
			except ValueError as exc:
				raise M2ValueError(str(exc)) from exc
		raise M2ValidationError(f"prefix operator {expr.op.value} is not allowed in constant expression",
			'InvalidConstantExpressionNode', expr.line_info)
