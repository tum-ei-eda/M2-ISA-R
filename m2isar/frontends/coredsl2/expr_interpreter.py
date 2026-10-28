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
from .constant_expressions import BINARY
from ...metamodel import arch, behav
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
		right = self.generate(expr.right, context)
		op = expr.op.value
		if op in BINARY:
			return int(BINARY[op](left, right))
		if op == '/':
			if right == 0:
				raise M2ValidationError("Division by zero", 'DivisionByZero', expr.line_info)
			value = abs(left) // abs(right)
			return -value if (left < 0) != (right < 0) else value
		if op in ('<<', '>>'):
			shift = right if op == '<<' else -right
			return left << shift if shift >= 0 else left >> -shift
		raise M2ValidationError(f"Infix expression {op} is currently unsupported in constant expressions",
			'UnsupportedLanguageFeature', expr.line_info)


	@generate.register
	def _(self, expr: behav.UnaryOperation, context):
		right = self.generate(expr.right, context)
		if expr.op.value == '-':
			return -right
		raise M2ValidationError(f"prefix operator {expr.op.value} is not allowed in constant expression",
			'InvalidConstantExpressionNode', expr.line_info)
