# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich
#
# Copyright (C) 2026
# Modifed by JK TUW ECS

"""Generate a ttk.Treeview representation of a M2-ISA-R model structure."""

import tkinter as tk

from ...metamodel import behav
from .utils import TreeGenContext
from ...metamodel.utils.ExprVisitor import ExprVisitor
from .utils import TreeGenContext
from functools import singledispatchmethod
# pylint: disable=unused-argument


class TreeGenVisitor(ExprVisitor):
	"""Visitor to generate a ttk.Treeview representation of a M2-ISA-R model structure."""
	@singledispatchmethod
	def generate(self, expr : behav.BaseNode, context=None):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(expr).__name__}")

	@generate.register
	def visit_operation(self, expr: behav.Operation, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Operation"))

		for stmt in expr.statements:
			self.generate(stmt, context)

		context.pop()

	@generate.register
	def visit_block(self, expr: behav.Block, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Block"))

		for stmt in expr.statements:
			self.generate(stmt, context)

		context.pop()

	@generate.register
	def visit_binary_operation(self, expr: behav.BinaryOperation, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Binary Operation"))

		context.push(context.tree.insert(context.parent, tk.END, text="Left"))
		self.generate(expr.left, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Right"))
		self.generate(expr.right, context)
		context.pop()

		context.tree.insert(context.parent, tk.END, text="Op", values=(expr.op.value,))
		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

		context.pop()

	@generate.register
	def visit_slice_operation(self, expr: behav.SliceOperation, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Slice Operation"))

		context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
		self.generate(expr.expr, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Left"))
		self.generate(expr.left, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Right"))
		self.generate(expr.right, context)
		context.pop()

		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

		context.pop()


	@generate.register
	def concat_operation(self, expr: behav.ConcatOperation, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Concat Operation"))

		context.push(context.tree.insert(context.parent, tk.END, text="Left"))
		self.generate(expr.left, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Right"))
		self.generate(expr.right, context)
		context.pop()

		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

		context.pop()

	@generate.register
	def number_literal(self, expr: behav.Literal, context: "TreeGenContext"):
		context.tree.insert(context.parent, tk.END, text="Number Literal", values=(expr.value,))
		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

	@generate.register
	def .var_definition(self, expr: behav.VarDefinition, context: "TreeGenContext"):
		context.tree.insert(context.parent, tk.END, text="Scalar Definition", values=(expr.var.name,))
		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

	@generate.register
	def break_(self, expr: behav.Break, context: "TreeGenContext"):
		context.tree.insert(context.parent, tk.END, text="Break")

	@generate.register
	def assignment(self, expr: behav.Assignment, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Assignment"))

		context.push(context.tree.insert(context.parent, tk.END, text="Target"))
		self.generate(expr.target, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
		self.generate(expr.expr, context)
		context.pop()

		context.pop()

	@generate.register
	def conditional(self, expr: behav.Conditional, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Conditional"))

		context.push(context.tree.insert(context.parent, tk.END, text="Conditions"))
		for cond in expr.conds:
			self.generate(cond, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Statements"))
		for stmt in expr.stmts:
			self.generate(stmt, context)
		context.pop()

		context.pop()

	@generate.register
	def loop(self, expr: behav.Loop, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Loop"))

		context.tree.insert(context.parent, tk.END, text="Post Test", values=(expr.post_test,))

		context.push(context.tree.insert(context.parent, tk.END, text="Condition"))
		self.generate(expr.cond, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Statements"))
		for stmt in expr.stmts:
			self.generate(stmt, context)
		context.pop()

		context.pop()

	@generate.register
	def ternary(self, expr: behav.Ternary, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Ternary"))

		context.push(context.tree.insert(context.parent, tk.END, text="Cond"))
		self.generate(expr.cond, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Then Expression"))
		self.generate(expr.then_expr, context)
		context.pop()

		context.push(context.tree.insert(context.parent, tk.END, text="Else Expression"))
		self.generate(expr.else_expr, context)
		context.pop()

		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

		context.pop()

	@generate.register
	def return_(self, expr: behav.Return, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Return"))

		if expr.expr is not None:
			context.push(context.tree.insert(context.parent, tk.END, text="Expression"))
			self.generate(expr.expr, context)
			context.pop()

		context.pop()

	@generate.register
	def unary_operation(self, expr: behav.UnaryOperation, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Unary Operation"))

		context.push(context.tree.insert(context.parent, tk.END, text="Right"))
		self.generate(expr.right, context)
		context.pop()

		context.tree.insert(context.parent, tk.END, text="Op", values=(expr.op.value,))
		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

		context.pop()

	@generate.register
	def named_reference(self, expr: behav.NamedReference, context: "TreeGenContext"):
		context.tree.insert(context.parent, tk.END, text="Named Reference", values=(f"{expr.reference}",))
		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

	@generate.register
	def indexed_reference(self, expr: behav.IndexedReference, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Indexed Reference"))

		context.push(context.tree.insert(context.parent, tk.END, text="Reference", values=(f"{expr.reference}",)))
		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.reference.ty,))
		context.pop()

		# If LHS is a complex expression => RHS also an expression
		# TODO: Little Endian only so far supported
		if (expr.reference.name == "MEM"):
				if expr.right != None:
						context.push(context.tree.insert(context.parent, tk.END, text="IndexRange"))

						context.push(context.tree.insert(context.parent, tk.END, text="Left"))
						self.generate(expr.index, context)
						context.pop()
						assert(type(expr.right) == behav.NamedReference)
						context.push(context.tree.insert(context.parent, tk.END, text="Right"))
						self.generate(expr.right, context)
						context.pop()

						context.pop()

				else:
						context.push(context.tree.insert(context.parent, tk.END, text="Index"))
						self.generate(expr.index, context)
						context.pop()

		else:
				context.push(context.tree.insert(context.parent, tk.END, text="Index"))
				self.generate(expr.index, context)
				context.pop()

		context.tree.insert(context.parent, tk.END, text="Type ", values=(expr.ty,))

		context.pop()

	@generate.register
	def type_conv(self, expr: behav.TypeConv, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Type Conv"))

		context.tree.insert(context.parent, tk.END, text="Type", values=(expr.data_type,))
		context.tree.insert(context.parent, tk.END, text="Size", values=(expr.size,))

		context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
		self.generate(expr.expr, context)
		context.pop()

		context.pop()

	@generate.register
	def callable_(self, expr: behav.Callable, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Callable", values=(expr.ref_or_name.name,)))

		for arg, arg_descr in zip(expr.args, expr.ref_or_name.args):
			context.push(context.tree.insert(context.parent, tk.END, text="Arg", values=(arg_descr,)))
			self.generate(arg, context)
			context.pop()

		context.pop()

	@generate.register
	def procedure_call(self, expr: behav.ProcedureCall, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="ProcedureCall", values=(expr.ref_or_name.name,)))

		for arg, arg_descr in zip(expr.args, expr.ref_or_name.args):
			context.push(context.tree.insert(context.parent, tk.END, text="Arg", values=(arg_descr,)))
			self.generate(arg, context)
			context.pop()

		context.pop()

	@generate.register
	def group(self, expr: behav.Group, context: "TreeGenContext"):
		context.push(context.tree.insert(context.parent, tk.END, text="Group"))

		context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
		self.generate(expr.expr, context)
		context.pop()

		context.pop()
