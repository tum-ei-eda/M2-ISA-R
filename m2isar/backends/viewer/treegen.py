# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Generate a ttk.Treeview representation of a M2-ISA-R model structure."""

import tkinter as tk

from ...metamodel import arch, behav
from .utils import TreeGenContext

# pylint: disable=unused-argument

def operation(self: behav.Operation, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Operation"))

	for stmt in self.statements:
		stmt.generate(context)

	context.pop()

def binary_operation(self: behav.BinaryOperation, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Binary Operation"))

	context.push(context.tree.insert(context.parent, tk.END, text="Left"))
	self.left.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Right"))
	self.right.generate(context)
	context.pop()

	context.tree.insert(context.parent, tk.END, text="Op", values=(self.op.value,))

	context.pop()

def slice_operation(self: behav.SliceOperation, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Slice Operation"))

	context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
	self.expr.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Left"))
	self.left.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Right"))
	self.right.generate(context)
	context.pop()

	context.pop()

def concat_operation(self: behav.ConcatOperation, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Concat Operation"))

	context.push(context.tree.insert(context.parent, tk.END, text="Left"))
	self.left.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Right"))
	self.right.generate(context)
	context.pop()

	context.pop()

def number_literal(self: behav.IntLiteral, context: "TreeGenContext"):
	context.tree.insert(context.parent, tk.END, text="Number Literal", values=(self.value,))

def int_literal(self: behav.IntLiteral, context: "TreeGenContext"):
	context.tree.insert(context.parent, tk.END, text="Int Literal", values=(self.value,))

def scalar_definition(self: behav.ScalarDefinition, context: "TreeGenContext"):
	context.tree.insert(context.parent, tk.END, text="Scalar Definition", values=(self.scalar.name,))

def assignment(self: behav.Assignment, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Assignment"))

	context.push(context.tree.insert(context.parent, tk.END, text="Target"))
	self.target.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
	self.expr.generate(context)
	context.pop()

	context.pop()

def conditional(self: behav.Conditional, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Conditional"))

	context.push(context.tree.insert(context.parent, tk.END, text="Conditions"))
	for cond in self.conds:
		cond.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Statements"))
	for op in self.stmts:
		context.push(context.tree.insert(context.parent, tk.END, text="Statement"))
		for stmt in op:
			stmt.generate(context)
		context.pop()
	context.pop()

	context.pop()

def loop(self: behav.Loop, context: "TreeGenContext"):
	return self

def ternary(self: behav.Ternary, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Ternary"))

	context.push(context.tree.insert(context.parent, tk.END, text="Cond"))
	self.cond.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Then Expression"))
	self.then_expr.generate(context)
	context.pop()

	context.push(context.tree.insert(context.parent, tk.END, text="Else Expression"))
	self.else_expr.generate(context)
	context.pop()

	context.pop()

def return_(self: behav.Return, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Return"))

	if self.expr is not None:
		context.push(context.tree.insert(context.parent, tk.END, text="Expression"))
		self.expr.generate(context)
		context.pop()

	context.pop()

def unary_operation(self: behav.UnaryOperation, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Unary Operation"))

	context.push(context.tree.insert(context.parent, tk.END, text="Right"))
	self.right.generate(context)
	context.pop()

	context.tree.insert(context.parent, tk.END, text="Op", values=(self.op.value,))

	context.pop()

def named_reference(self: behav.NamedReference, context: "TreeGenContext"):
	context.tree.insert(context.parent, tk.END, text="Named Reference", values=(f"{self.reference}",))

def indexed_reference(self: behav.IndexedReference, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Indexed Reference"))

	context.tree.insert(context.parent, tk.END, text="Reference", values=(f"{self.reference}",))

	context.push(context.tree.insert(context.parent, tk.END, text="Index"))
	self.index.generate(context)
	context.pop()

	context.pop()

def type_conv(self: behav.TypeConv, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Type Conv"))

	context.tree.insert(context.parent, tk.END, text="Type", values=(self.data_type,))
	context.tree.insert(context.parent, tk.END, text="Size", values=(self.size,))

	context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
	self.expr.generate(context)
	context.pop()

	context.pop()

def callable_(self: behav.Callable, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Callable", values=(self.ref_or_name.name,)))

	for arg, arg_descr in zip(self.args, self.ref_or_name.args):
		context.push(context.tree.insert(context.parent, tk.END, text="Arg", values=(arg_descr,)))
		arg.generate(context)
		context.pop()

	context.pop()

def group(self: behav.Group, context: "TreeGenContext"):
	context.push(context.tree.insert(context.parent, tk.END, text="Group"))

	context.push(context.tree.insert(context.parent, tk.END, text="Expr"))
	self.expr.generate(context)
	context.pop()

	context.pop()
