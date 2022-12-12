# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Transformation functions to determine whether a function is considered to be static."""

from ...metamodel import arch, behav

# pylint: disable=unused-argument

def operation(self: behav.Operation, context):
	statements = []
	for stmt in self.statements:
		temp = stmt.generate(context)
		if isinstance(temp, list):
			statements.extend(temp)
		else:
			statements.append(temp)

	return all(statements)

def binary_operation(self: behav.BinaryOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return all([left, right])

def slice_operation(self: behav.SliceOperation, context):
	expr = self.expr.generate(context)
	left = self.left.generate(context)
	right = self.right.generate(context)

	return all([expr, left, right])

def concat_operation(self: behav.ConcatOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return all([left, right])

def number_literal(self: behav.IntLiteral, context):
	return True

def int_literal(self: behav.IntLiteral, context):
	return True

def scalar_definition(self: behav.ScalarDefinition, context):
	return True

def assignment(self: behav.Assignment, context):
	target = self.target.generate(context)
	expr = self.expr.generate(context)

	return all([target, expr])

def conditional(self: behav.Conditional, context):
	conds = [x.generate(context) for x in self.conds]
	stmts = [all(y.generate(context) for y in x) for x in self.stmts]

	conds.extend(stmts)

	return all(conds)

def loop(self: behav.Loop, context):
	cond = self.cond.generate(context)
	stmts = [x.generate(context) for x in self.stmts]
	stmts.append(cond)

	return all(stmts)

def ternary(self: behav.Ternary, context):
	cond = self.cond.generate(context)
	then_expr = self.then_expr.generate(context)
	else_expr = self.else_expr.generate(context)

	return all([cond, then_expr, else_expr])

def return_(self: behav.Return, context):
	if self.expr is not None:
		return self.expr.generate(context)

	return True

def unary_operation(self: behav.UnaryOperation, context):
	right = self.right.generate(context)

	return right

def named_reference(self: behav.NamedReference, context):
	if isinstance(self.reference, arch.Scalar):
		return self.reference.static

	static_map = {
		arch.Memory: False,
		arch.BitFieldDescr: True,
		arch.Constant: True,
		arch.FnParam: True,
		arch.Scalar: True
	}

	return static_map.get(type(self.reference), False)

def indexed_reference(self: behav.IndexedReference, context):
	self.index.generate(context)

	return False

def type_conv(self: behav.TypeConv, context):
	expr = self.expr.generate(context)

	return expr

def callable_(self: behav.Callable, context):
	args = [arg.generate(context) for arg in self.args]
	args.append(self.ref_or_name.static)

	return all(args)

def group(self: behav.Group, context):
	expr = self.expr.generate(context)

	return expr
