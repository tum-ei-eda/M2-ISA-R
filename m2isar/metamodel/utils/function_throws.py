# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Tranformation functions to determine whether a function throws an exception."""

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

	return any(statements)

def binary_operation(self: behav.BinaryOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return any([left, right])

def slice_operation(self: behav.SliceOperation, context):
	expr = self.expr.generate(context)
	left = self.left.generate(context)
	right = self.right.generate(context)

	return any([expr, left, right])

def concat_operation(self: behav.ConcatOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return any([left, right])

def number_literal(self: behav.IntLiteral, context):
	return False

def int_literal(self: behav.IntLiteral, context):
	return False

def scalar_definition(self: behav.ScalarDefinition, context):
	return False

def assignment(self: behav.Assignment, context):
	target = self.target.generate(context)
	expr = self.expr.generate(context)

	return any([target, expr])

def conditional(self: behav.Conditional, context):
	conds = [x.generate(context) for x in self.conds]
	stmts = [any(y.generate(context) for y in x) for x in self.stmts]

	conds.extend(stmts)

	return any(conds)

def loop(self: behav.Loop, context):
	cond = self.cond.generate(context)
	stmts = [x.generate(context) for x in self.stmts]
	stmts.append(cond)

	return any(stmts)

def ternary(self: behav.Ternary, context):
	cond = self.cond.generate(context)
	then_expr = self.then_expr.generate(context)
	else_expr = self.else_expr.generate(context)

	return any([cond, then_expr, else_expr])

def return_(self: behav.Return, context):
	if self.expr is not None:
		return self.expr.generate(context)

	return False

def unary_operation(self: behav.UnaryOperation, context):
	right = self.right.generate(context)

	return right

def named_reference(self: behav.NamedReference, context):
	if isinstance(self.reference, arch.Memory) and arch.MemoryAttribute.ETISS_CAN_FAIL in self.reference.attributes:
		return True

	return False

def indexed_reference(self: behav.IndexedReference, context):
	if isinstance(self.reference, arch.Memory) and arch.MemoryAttribute.ETISS_CAN_FAIL in self.reference.attributes:
		return True

	return self.index.generate(context)

def type_conv(self: behav.TypeConv, context):
	expr = self.expr.generate(context)

	return expr

def callable_(self: behav.Callable, context):
	args = [arg.generate(context) for arg in self.args]
	args.append(self.ref_or_name.throws)

	return any(args)

def group(self: behav.Group, context):
	expr = self.expr.generate(context)

	return expr
