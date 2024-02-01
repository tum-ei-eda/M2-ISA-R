# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Fortmatter implementation for CoreDSL assembly strings."""

# Inspired by: https://stackoverflow.com/a/9558001

from string import Formatter

import re
import ast
import operator as op

operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
			 ast.Div: op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
			 ast.USub: op.neg}

NAMES = {
	0: "zero",
	1: "ra",
	2: "sp",
	3: "gp",
	4: "tp",
	5: "t0",
	6: "t1",
	7: "t2",
	8: "s0",
	9: "s1",
	10: "a0",
	11: "a1",
	12: "a2",
	13: "a3",
	14: "a4",
	15: "a5",
	16: "a6",
	17: "a7",
	18: "s2",
	19: "s3",
	20: "s4",
	21: "s5",
	22: "s6",
	23: "s7",
	24: "s8",
	25: "s9",
	26: "s10",
	27: "s11",
	28: "t3",
	29: "t4",
	30: "t5",
	31: "t6",
}

FNAMES = {
	0: "f0",
	1: "f1",
	2: "f2",
	3: "f3",
	4: "f4",
	5: "f5",
	6: "f6",
	7: "f7",
	8: "fs0",
	9: "fs1",
	10: "fa0",
	11: "fa1",
	12: "fa2",
	13: "fa3",
	14: "fa4",
	15: "fa5",
	16: "fa6",
	17: "fa7",
	18: "fs2",
	19: "fs3",
	20: "fs4",
	21: "fs5",
	22: "fs6",
	23: "fs7",
	24: "fs8",
	25: "fs9",
	26: "fs10",
	27: "fs11",
	28: "ft8",
	29: "ft9",
	30: "ft10",
	31: "ft11",
}

class AsmFormatter(Formatter):

	def get_value(self, key, args, kwargs):
		if isinstance(key, int):
			return key
		assert isinstance(key, str)
		try:
			value = self.eval_expr(key, args, kwargs)
			return value
		except ValueError:
			pass

		return super().get_value(key, args, kwargs)

	def get_field(self, field_name, args, kwargs):
		return super().get_field(field_name, args, kwargs)

	def eval_expr(self, expr, args, kwargs):
		return self.eval_(ast.parse(expr, mode='eval').body, args, kwargs)

	def eval_(self, node, args, kwargs):
		if isinstance(node, ast.Num): # <number>
			return node.n
		elif isinstance(node, ast.Name): # <name>
			return super().get_value(node.id, args, kwargs)
		elif isinstance(node, ast.BinOp): # <left> <operator> <right>
			return operators[type(node.op)](self.eval_(node.left, args, kwargs), self.eval_(node.right, args, kwargs))
		elif isinstance(node, ast.UnaryOp): # <operator> <operand> e.g., -1
			return operators[type(node.op)](self.eval_(node.operand, args, kwargs))
		elif isinstance(node, ast.Call):
			if node.func.id == "name":
				assert len(node.args) == 1
				return NAMES[self.eval_(node.args[0], args, kwargs)]
			if node.func.id == "fname":
				assert len(node.args) == 1
				return FNAMES[self.eval_(node.args[0], args, kwargs)]
			assert False
		else:
			raise TypeError(node)
