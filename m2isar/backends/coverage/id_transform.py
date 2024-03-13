# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2024
# Chair of Electrical Design Automation
# Technical University of Munich


from ...metamodel import behav
from .utils import IdMatcherContext


def operation(self: behav.Operation, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	for stmt in self.statements:
		stmt.generate(context)

def block(self: behav.Block, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	for stmt in self.statements:
		stmt.generate(context)

def binary_operation(self: behav.BinaryOperation, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.left.generate(context)
	self.right.generate(context)

def slice_operation(self: behav.SliceOperation, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.expr.generate(context)
	self.left.generate(context)
	self.right.generate(context)

def concat_operation(self: behav.ConcatOperation, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.left.generate(context)
	self.right.generate(context)

def number_literal(self: behav.IntLiteral, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

def int_literal(self: behav.IntLiteral, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

def scalar_definition(self: behav.ScalarDefinition, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

def break_(self: behav.Break, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

def assignment(self: behav.Assignment, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.target.generate(context)
	self.expr.generate(context)

def conditional(self: behav.Conditional, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	for cond in self.conds:
		cond.generate(context)

	for stmt in self.stmts:
		#
		#for stmt in op:
			stmt.generate(context)
		#

def loop(self: behav.Loop, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.cond.generate(context)

	for stmt in self.stmts:
		stmt.generate(context)

def ternary(self: behav.Ternary, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.cond.generate(context)
	self.then_expr.generate(context)
	self.else_expr.generate(context)

def return_(self: behav.Return, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	if self.expr is not None:
		self.expr.generate(context)

def unary_operation(self: behav.UnaryOperation, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.right.generate(context)

def named_reference(self: behav.NamedReference, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

def indexed_reference(self: behav.IndexedReference, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.index.generate(context)

def type_conv(self: behav.TypeConv, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.expr.generate(context)

def callable_(self: behav.Callable, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	for arg, arg_descr in zip(self.args, self.ref_or_name.args):
		arg.generate(context)

def group(self: behav.Group, context: "IdMatcherContext"):
	if self.line_info is not None:
		context.id_to_obj_map[context.arch_name][self.line_info.id] = self

	self.expr.generate(context)
