# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2024
# Chair of Electrical Design Automation
# Technical University of Munich

"""Visitor for mapping line/function IDs to model objects for coverage backends."""

from ...metamodel import behav
from ...metamodel.utils.ExprVisitor import ExprVisitor
from .utils import IdMatcherContext
from functools import singledispatchmethod


class IdTransformVisitor(ExprVisitor):
	"""Visitor that builds a mapping from code info IDs to behavior objects."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

	def _store_id(self, expr: behav.BaseNode, context: "IdMatcherContext"):
		if expr.line_info is not None:
			context.id_to_obj_map[context.arch_name][expr.line_info.id] = expr

	@generate.register
	def _(self, expr: behav.Operation, context: "IdMatcherContext"):
		self._store_id(expr, context)
		for stmt in expr.statements:
			self.generate(stmt, context)

	@generate.register
	def _(self, expr: behav.Block, context: "IdMatcherContext"):
		self._store_id(expr, context)
		for stmt in expr.statements:
			self.generate(stmt, context)

	@generate.register
	def _(self, expr: behav.BinaryOperation, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.left, context)
		self.generate(expr.right, context)

	@generate.register
	def _(self, expr: behav.SliceOperation, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.expr, context)
		self.generate(expr.left, context)
		self.generate(expr.right, context)

	@generate.register
	def _(self, expr: behav.ConcatOperation, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.left, context)
		self.generate(expr.right, context)

	@generate.register
	def _(self, expr: behav.NumberLiteral, context: "IdMatcherContext"):
		self._store_id(expr, context)

	@generate.register
	def _(self, expr: behav.IntLiteral, context: "IdMatcherContext"):
		self._store_id(expr, context)

	@generate.register
	def _(self, expr: behav.ScalarDefinition, context: "IdMatcherContext"):
		self._store_id(expr, context)

	@generate.register
	def _(self, expr: behav.Break, context: "IdMatcherContext"):
		self._store_id(expr, context)

	@generate.register
	def _(self, expr: behav.Assignment, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.target, context)
		self.generate(expr.expr, context)

	@generate.register
	def _(self, expr: behav.Conditional, context: "IdMatcherContext"):
		self._store_id(expr, context)
		for cond in expr.conds:
			self.generate(cond, context)
		for stmt in expr.stmts:
			self.generate(stmt, context)

	@generate.register
	def _(self, expr: behav.Loop, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.cond, context)
		for stmt in expr.stmts:
			self.generate(stmt, context)

	@generate.register
	def _(self, expr: behav.Ternary, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.cond, context)
		self.generate(expr.then_expr, context)
		self.generate(expr.else_expr, context)

	@generate.register
	def _(self, expr: behav.Return, context: "IdMatcherContext"):
		self._store_id(expr, context)
		if expr.expr is not None:
			self.generate(expr.expr, context)

	@generate.register
	def _(self, expr: behav.UnaryOperation, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.right, context)

	@generate.register
	def _(self, expr: behav.NamedReference, context: "IdMatcherContext"):
		self._store_id(expr, context)

	@generate.register
	def _(self, expr: behav.IndexedReference, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.index, context)

	@generate.register
	def _(self, expr: behav.TypeConv, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.expr, context)

	@generate.register
	def _(self, expr: behav.Callable, context: "IdMatcherContext"):
		self._store_id(expr, context)
		for arg in expr.args:
			self.generate(arg, context)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context: "IdMatcherContext"):
		self._store_id(expr, context)
		for arg in expr.args:
			self.generate(arg, context)

	@generate.register
	def _(self, expr: behav.Group, context: "IdMatcherContext"):
		self._store_id(expr, context)
		self.generate(expr.expr, context)
