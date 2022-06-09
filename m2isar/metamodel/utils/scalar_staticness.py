# SPDX-License-Identifier: Apache-2.0

# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (c) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

from ...metamodel import arch, behav
from ...metamodel.utils import StaticType

def operation(self: behav.Operation, context):
	statements = []
	for stmt in self.statements:
		temp = stmt.generate(context)
		if isinstance(temp, list):
			statements.extend(temp)
		else:
			statements.append(temp)

	return self

def binary_operation(self: behav.BinaryOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return min(left, right)

def slice_operation(self: behav.SliceOperation, context):
	expr = self.expr.generate(context)
	left = self.left.generate(context)
	right = self.right.generate(context)

	return min(expr, left, right)

def concat_operation(self: behav.ConcatOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return min(left, right)

def number_literal(self: behav.IntLiteral, context):
	return StaticType.READ

def int_literal(self: behav.IntLiteral, context):
	return StaticType.READ

def scalar_definition(self: behav.ScalarDefinition, context):
	self.scalar.static = StaticType.RW
	return StaticType.RW

def assignment(self: behav.Assignment, context):
	target = self.target.generate(context)
	expr = self.expr.generate(context)
	if expr != StaticType.NONE:
		expr = StaticType.RW

	if isinstance(self.target, behav.NamedReference) and isinstance(self.target.reference, arch.Scalar):
		self.target.reference.static &= expr

	if isinstance(self.target, behav.ScalarDefinition):
		self.target.scalar.static &= expr


def conditional(self: behav.Conditional, context):
	conds = [x.generate(context) for x in self.conds]
	stmts = [[y.generate(context) for y in x] for x in self.stmts]

def loop(self: behav.Loop, context):
	return self

def ternary(self: behav.Ternary, context):
	cond = self.cond.generate(context)
	then_expr = self.then_expr.generate(context)
	else_expr = self.else_expr.generate(context)

	return min(cond, then_expr, else_expr)

def return_(self: behav.Return, context):
	expr = self.expr.generate(context)

	return expr

def unary_operation(self: behav.UnaryOperation, context):
	right = self.right.generate(context)

	return right

def named_reference(self: behav.NamedReference, context):
	if isinstance(self.reference, arch.Scalar):
		return self.reference.static

	static_map = {
		arch.Memory: StaticType.NONE,
		arch.BitFieldDescr: StaticType.READ,
		arch.Constant: StaticType.READ,
		arch.FnParam: StaticType.READ
	}

	return static_map.get(type(self.reference), StaticType.NONE)

def indexed_reference(self: behav.IndexedReference, context):
	index = self.index.generate(context)

	return StaticType.NONE

def type_conv(self: behav.TypeConv, context):
	expr = self.expr.generate(context)

	return expr

def callable(self: behav.Callable, context):
	args = [arg.generate(context) for arg in self.args]
	args.append(StaticType.READ if self.ref_or_name.static else StaticType.NONE)

	return min(args)

def group(self: behav.Group, context):
	expr = self.expr.generate(context)

	return expr