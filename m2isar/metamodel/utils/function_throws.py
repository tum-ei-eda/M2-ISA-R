# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Tranformation functions to determine whether a function throws an exception."""

from functools import reduce
from operator import or_

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

	return reduce(or_, statements, arch.FunctionThrows.NO)


def block(self: behav.Block, context):
	stmts = [x.generate(context) for x in self.statements]
	return reduce(or_, stmts, arch.FunctionThrows.NO)


def binary_operation(self: behav.BinaryOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return reduce(or_, [left, right])

def slice_operation(self: behav.SliceOperation, context):
	expr = self.expr.generate(context)
	left = self.left.generate(context)
	right = self.right.generate(context)

	return reduce(or_, [expr, left, right])

def concat_operation(self: behav.ConcatOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)

	return reduce(or_, [left, right])

def number_literal(self: behav.IntLiteral, context):
	return arch.FunctionThrows.NO

def int_literal(self: behav.IntLiteral, context):
	return arch.FunctionThrows.NO

def string_literal(self: behav.StringLiteral, context):
	return arch.FunctionThrows.NO

def scalar_definition(self: behav.ScalarDefinition, context):
	return arch.FunctionThrows.NO

def break_(self: behav.Break, context):
	return arch.FunctionThrows.NO

def assignment(self: behav.Assignment, context):
	target = self.target.generate(context)
	expr = self.expr.generate(context)

	return reduce(or_, [target, expr])

def conditional(self: behav.Conditional, context):
	conds = [x.generate(context) for x in self.conds]
	stmts = [x.generate(context) for x in self.stmts]

	conds.extend(stmts)

	return arch.FunctionThrows.MAYBE if reduce(or_, conds) else arch.FunctionThrows.NO

def loop(self: behav.Loop, context):
	cond = self.cond.generate(context)
	stmts = [x.generate(context) for x in self.stmts]
	stmts.append(cond)

	return reduce(or_, stmts)

def ternary(self: behav.Ternary, context):
	cond = self.cond.generate(context)
	then_expr = self.then_expr.generate(context)
	else_expr = self.else_expr.generate(context)

	return reduce(or_, [cond, then_expr, else_expr])

def return_(self: behav.Return, context):
	if self.expr is not None:
		return self.expr.generate(context)

	return arch.FunctionThrows.NO

def unary_operation(self: behav.UnaryOperation, context):
	right = self.right.generate(context)

	return right

def named_reference(self: behav.NamedReference, context):
	if isinstance(self.reference, arch.Memory) and arch.MemoryAttribute.ETISS_CAN_FAIL in self.reference.attributes:
		return arch.FunctionThrows.YES

	return arch.FunctionThrows.NO

def indexed_reference(self: behav.IndexedReference, context):
	if isinstance(self.reference, arch.Memory) and arch.MemoryAttribute.ETISS_CAN_FAIL in self.reference.attributes:
		return arch.FunctionThrows.YES

	return self.index.generate(context)

def type_conv(self: behav.TypeConv, context):
	expr = self.expr.generate(context)

	return expr

def callable_(self: behav.Callable, context):
	args = [arg.generate(context) for arg in self.args]
	args.append(self.ref_or_name.throws)

	return reduce(or_, args)


def procedure_call(self: behav.ProcedureCall, context):
	args = [arg.generate(context) for arg in self.args]
	args.append(self.ref_or_name.throws)

	return reduce(or_, args)

def group(self: behav.Group, context):
	expr = self.expr.generate(context)

	return expr
