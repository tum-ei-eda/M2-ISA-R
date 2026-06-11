# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026

"""Generate a DOT representation of a M2-ISA-R model structure."""

from ...metamodel import behav
from .utils import TreeGenContext
from ...metamodel.utils.ExprVisitor import ExprVisitor
from .utils import TreeGenContext
from functools import singledispatchmethod
# pylint: disable=unused-argument


class TreeGenVisitor(ExprVisitor):
	"""Visitor to generate a DOT representation of a M2-ISA-R model structure."""
	@singledispatchmethod
	def generate(self, expr : behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

	@generate.register
	def visit_operation(self, expr: behav.Operation, context: "TreeGenContext"):
		context.insert(text="Operation")

		for stmt in expr.statements:
			self.generate(stmt, context)

		context.pop()

	@generate.register
	def visit_block(self, expr: behav.Block, context: "TreeGenContext"):
		context.insert(text="Block")

		for stmt in expr.statements:
			self.generate(stmt, context)

		context.pop()

	@generate.register
	def visit_binary_operation(self, expr: behav.BinaryOperation, context: "TreeGenContext"):
		context.insert(text="Binary Operation")

		context.insert(text="Left")
		self.generate(expr.left, context)
		context.pop()

		context.insert(text="Right")
		self.generate(expr.right, context)
		context.pop()

		context.insert2(text="Op", values=(expr.op.value,))

		context.pop()

	@generate.register
	def visit_slice_operation(self, expr: behav.SliceOperation, context: "TreeGenContext"):
		context.insert(text="Slice Operation")

		context.insert(text="Expr")
		self.generate(expr.expr, context)
		context.pop()

		context.insert(text="Left")
		self.generate(expr.left, context)
		context.pop()

		context.insert(text="Right")
		self.generate(expr.right, context)
		context.pop()

		context.pop()


	@generate.register
	def concat_operation(self, expr: behav.ConcatOperation, context: "TreeGenContext"):
		context.insert(text="Concat Operation")

		context.insert(text="Left")
		self.generate(expr.left, context)
		context.pop()

		context.insert(text="Right")
		self.generate(expr.right, context)
		context.pop()

		context.pop()

	@generate.register
	def number_literal(self, expr: behav.NumberLiteral, context: "TreeGenContext"):
		context.insert2(text="Number Literal", values=(expr.value,))

	@generate.register
	def int_literal(self, expr: behav.IntLiteral, context: "TreeGenContext"):
		context.insert2(text="Int Literal", values=(expr.value,))

	@generate.register
	def scalar_definition(self, expr: behav.ScalarDefinition, context: "TreeGenContext"):
		context.insert2(text="Scalar Definition", values=(expr.scalar.name,))

	@generate.register
	def break_(self, expr: behav.Break, context: "TreeGenContext"):
		context.insert2(text="Break")

	@generate.register
	def assignment(self, expr: behav.Assignment, context: "TreeGenContext"):
		context.insert(text="Assignment")

		context.insert(text="Target")
		self.generate(expr.target, context)
		context.pop()

		context.insert(text="Expr")
		self.generate(expr.expr, context)
		context.pop()

		context.pop()

	@generate.register
	def conditional(self, expr: behav.Conditional, context: "TreeGenContext"):
		context.insert(text="Conditional")

		context.insert(text="Conditions")
		for cond in expr.conds:
			self.generate(cond, context)
		context.pop()

		context.insert(text="Statements")
		for stmt in expr.stmts:
			self.generate(stmt, context)
		context.pop()

		context.pop()

	@generate.register
	def loop(self, expr: behav.Loop, context: "TreeGenContext"):
		context.insert(text="Loop")

		context.insert2(text="Post Test", values=(expr.post_test,))

		context.insert(text="Condition")
		self.generate(expr.cond, context)
		context.pop()

		context.insert(text="Statements")
		for stmt in expr.stmts:
			self.generate(stmt, context)
		context.pop()

		context.pop()

	@generate.register
	def ternary(self, expr: behav.Ternary, context: "TreeGenContext"):
		context.insert(text="Ternary")

		context.insert(text="Cond")
		self.generate(expr.cond, context)
		context.pop()

		context.insert(text="Then Expression")
		self.generate(expr.then_expr, context)
		context.pop()

		context.insert(text="Else Expression")
		self.generate(expr.else_expr, context)
		context.pop()

		context.pop()

	@generate.register
	def return_(self, expr: behav.Return, context: "TreeGenContext"):
		context.insert(text="Return")

		if expr.expr is not None:
			context.insert(text="Expression")
			self.generate(expr.expr, context)
			context.pop()

		context.pop()

	@generate.register
	def unary_operation(self, expr: behav.UnaryOperation, context: "TreeGenContext"):
		context.insert(text="Unary Operation")

		context.insert(text="Right")
		self.generate(expr.right, context)
		context.pop()

		context.insert(text="Op", values=(expr.op.value,))

		context.pop()

	@generate.register
	def named_reference(self, expr: behav.NamedReference, context: "TreeGenContext"):
		context.insert2(text="Named Reference", values=(f"{expr.reference}",))

	@generate.register
	def indexed_reference(self, expr: behav.IndexedReference, context: "TreeGenContext"):
		context.insert(text="Indexed Reference")

		context.insert2(text="Reference", values=(f"{expr.reference}",))

		# If LHS is a complex expression => RHS also an expression
		# TODO: Little Endian only so far supported
		if (expr.reference.name == "MEM"):
				if expr.right != None:
						context.insert(text="IndexRange")

						context.insert(text="Left")
						self.generate(expr.index, context)
						context.pop()
						assert(type(expr.right) == behav.NamedReference)
						context.insert(text="Right")
						self.generate(expr.right, context)
						context.pop()

						context.pop()

				else:
						context.insert(text="Index")
						self.generate(expr.index, context)
						context.pop()

		else:
				context.insert(text="Index")
				self.generate(expr.index, context)
				context.pop()

		context.pop()

	@generate.register
	def type_conv(self, expr: behav.TypeConv, context: "TreeGenContext"):
		context.insert(text="Type Conv")

		context.insert2(text="Type", values=(expr.data_type,))
		context.insert2(text="Size", values=(expr.size,))

		context.insert(text="Expr")
		self.generate(expr.expr, context)
		context.pop()

		context.pop()

	@generate.register
	def callable_(self, expr: behav.Callable, context: "TreeGenContext"):
		context.insert(text="Callable", values=(expr.ref_or_name.name,))

		for arg, arg_descr in zip(expr.args, expr.ref_or_name.args):
			context.insert(text="Arg", values=(arg_descr,))
			self.generate(arg, context)
			context.pop()

		context.pop()

	@generate.register
	def procedure_call(self, expr: behav.ProcedureCall, context: "TreeGenContext"):
		context.insert(text="ProcedureCall", values=(expr.ref_or_name.name,))

		for arg, arg_descr in zip(expr.args, expr.ref_or_name.args):
			context.insert(text="Arg", values=(arg_descr,))
			self.generate(arg, context)
			context.pop()

		context.pop()

	@generate.register
	def group(self, expr: behav.Group, context: "TreeGenContext"):
		context.insert(text="Group")

		context.insert(text="Expr")
		self.generate(expr.expr, context)
		context.pop()

		context.pop()
