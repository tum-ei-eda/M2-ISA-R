# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Transformation functions to determine which scalars in a function or instruction
behavior are to be considered static.
"""

import dataclasses

from ...metamodel import arch, behav
from ...metamodel.utils import ScalarStaticnessContext, StaticType

# pylint: disable=unused-argument

def operation(self: behav.Operation, context: ScalarStaticnessContext):
	statements = []
	for stmt in self.statements:
		temp = stmt.generate(context)
		if isinstance(temp, list):
			statements.extend(temp)
		else:
			statements.append(temp)

	return self

def block(self: behav.Block, context):
	stmts = [x.generate(context) for x in self.statements]
	valid = [s for s in stmts if s is not None]
	if not valid:
		return StaticType.NONE
	return min(valid)

def binary_operation(self: behav.BinaryOperation, context: ScalarStaticnessContext):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return min(left, right)

def slice_operation(self: behav.SliceOperation, context: ScalarStaticnessContext):
	expr = self.expr.generate(context)
	left = self.left.generate(context)
	right = self.right.generate(context)

	return min(expr, left, right)

def concat_operation(self: behav.ConcatOperation, context: ScalarStaticnessContext):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return min(left, right)

def number_literal(self: behav.NumberLiteral, context: ScalarStaticnessContext):
	return StaticType.READ

def int_literal(self: behav.IntLiteral, context: ScalarStaticnessContext):
	return StaticType.READ

def string_literal(self: behav.StringLiteral, context: ScalarStaticnessContext):
	return StaticType.READ

def scalar_definition(self: behav.ScalarDefinition, context: ScalarStaticnessContext):
	self.scalar.static = StaticType.RW
	return StaticType.RW

def break_(self: behav.Break, context):
	return StaticType.READ

def assignment(self: behav.Assignment, context: ScalarStaticnessContext):
	self.target.generate(context)

	if context.context_is_static != StaticType.NONE or isinstance(self.target, behav.ScalarDefinition):
		expr = self.expr.generate(context)

		if expr != StaticType.NONE:
			expr = StaticType.RW
	else:
		expr = StaticType.NONE

	if isinstance(self.target, behav.NamedReference) and isinstance(self.target.reference, arch.Scalar):
		self.target.reference.static &= expr

	if isinstance(self.target, behav.ScalarDefinition):
		self.target.scalar.static &= expr


def conditional(self: behav.Conditional, context: ScalarStaticnessContext):
	conds = [x.generate(context) for x in self.conds]
	stmt_context = dataclasses.replace(context, context_is_static=min(conds))
	_ = [x.generate(stmt_context) for x in self.stmts]

def loop(self: behav.Loop, context: ScalarStaticnessContext):
	cond = self.cond.generate(context)
	stmt_context = dataclasses.replace(context, context_is_static=cond)
	_ = [x.generate(stmt_context) for x in self.stmts]

def ternary(self: behav.Ternary, context: ScalarStaticnessContext):
	cond = self.cond.generate(context)
	then_expr = self.then_expr.generate(context)
	else_expr = self.else_expr.generate(context)

	return min(cond, then_expr, else_expr)

def return_(self: behav.Return, context: ScalarStaticnessContext):
	if self.expr is not None:
		return self.expr.generate(context)

	return StaticType.RW

def unary_operation(self: behav.UnaryOperation, context: ScalarStaticnessContext):
	right = self.right.generate(context)

	return right

def named_reference(self: behav.NamedReference, context: ScalarStaticnessContext):
	if isinstance(self.reference, arch.Scalar):
		return self.reference.static

	static_map = {
		arch.Memory: StaticType.NONE,
		arch.BitFieldDescr: StaticType.READ,
		arch.Constant: StaticType.READ,
		arch.FnParam: StaticType.READ
	}

	return static_map.get(type(self.reference), StaticType.NONE)

def indexed_reference(self: behav.IndexedReference, context: ScalarStaticnessContext):
	self.index.generate(context)

	return StaticType.NONE

def type_conv(self: behav.TypeConv, context: ScalarStaticnessContext):
	expr = self.expr.generate(context)

	return expr

def callable_(self: behav.Callable, context: ScalarStaticnessContext):
	args = [arg.generate(context) for arg in self.args]
	args.append(StaticType.READ if self.ref_or_name.static else StaticType.NONE)

	return min(args)

def group(self: behav.Group, context: ScalarStaticnessContext):
	expr = self.expr.generate(context)

	return expr
