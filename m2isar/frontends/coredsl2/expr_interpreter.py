# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Very crude expression evaluation functions for use during model generation."""

from ... import M2ValueError
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
	def _(self, expr: behav.NumberLiteral, context):
		return expr.value

	@generate.register
	def _(self, expr: behav.IntLiteral, context):
		return expr.value

	@generate.register
	def _(self, expr: behav.NamedReference, context):
		if isinstance(expr.reference, arch.Constant) and expr.reference.value is not None:
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
		return int(eval(f"{left}{expr.op.value}{right}"))

	@generate.register
	def _(self, expr: behav.UnaryOperation, context):
		right = self.generate(expr.right, context)
		return int(eval(f"{expr.op.value}{right}"))
