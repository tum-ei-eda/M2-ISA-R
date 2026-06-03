# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import copy
import dataclasses
import logging
import numpy as np
from typing import TYPE_CHECKING, Union

from ... import M2NameError, M2SyntaxError, M2TypeError, flatten
from ...metamodel import arch, behav, type_info, intrinsics, attribute_info
from ...metamodel.code_info import (BranchEntryInfoFactory, BranchInfo,
                                    LineInfoFactory, LineInfoPlacement)
from .parser_gen import CoreDSL2Parser, CoreDSL2Visitor
from .utils import BOOLCONST, RADIX, SHORTHANDS, SIGNEDNESS, infer_shape_from_type, create_np_array_from_literal_array
from .expr_interpreter import ExprInterpreterVisitor

exprInterpretVisitor = ExprInterpreterVisitor()

if TYPE_CHECKING:
	from ...metamodel.code_info import LineInfo

logger = logging.getLogger("behav_builder")

class BehaviorModelBuilder(CoreDSL2Visitor):
	"""ANTLR visitor to build an M2-ISA-R behavioral model of a function or instruction
	of a CoreDSL 2 specification.
	"""

	def __init__(self, parameters: "dict[str, arch.Parameter]", memories: "dict[str, arch.Memory]", memory_aliases: "dict[str, arch.Alias]",
		register_banks: "dict[str, Union[arch.RegisterBank, arch.Register]]", register_aliases: "dict[str, arch.Alias]", fields: "dict[str, arch.BitFieldDescr]",
		functions: "dict[str, arch.Function]", warned_fns: "set[str]"):

		super().__init__()

		self._parameters = parameters
		self._memories = memories
		self._memory_aliases = memory_aliases
		self._register_banks = register_banks
		self._register_aliases = register_aliases
		self._fields = fields
		self._vars = {}
		self._functions = functions
		self.warned_fns = warned_fns if warned_fns is not None else set()

	def visitChildren(self, node):
		"""Helper method to return flatter results on tree visits."""

		ret = super().visitChildren(node)
		if isinstance(ret, list) and len(ret) == 1:
			return ret[0]
		return ret

	def aggregateResult(self, aggregate, nextResult):
		"""Aggregate results from multiple children into a list."""

		ret = aggregate
		if nextResult is not None:
			if ret is None:
				ret = [nextResult]
			else:
				ret += [nextResult]
		return ret

	def visitProcedure_call(self, ctx: CoreDSL2Parser.Procedure_callContext):
		"""Generate a procedure (method call without return value) call."""

		# extract name and reference to procedure object to be called
		name = ctx.ref.text
		ref = self._functions.get(name, None)

		# error out if method is unknown
		if ref is None:
			raise M2NameError(f"procedure {name} is not defined")

		# generate method arguments
		args = [self.visit(obj) for obj in ctx.args] if ctx.args else []

		return behav.ProcedureCall(ref, args, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitMethod_call(self, ctx: "CoreDSL2Parser.Method_callContext"):
		"""Generate a function (method call with return value) call."""

		# extract name and reference to function object to be called
		name = ctx.ref.text
		ref = self._functions.get(name, None)

		# error out if method is unknown
		if ref is None:
			raise M2NameError(f"function \"{name}\" is not defined")

		if attribute_info.FunctionAttribute.ETISS_TRAP_ENTRY_FN in ref.attributes:
			raise M2SyntaxError(f"exception entry function \"{name}\" must be called as procedure")

		# generate method arguments
		args = [self.visit(obj) for obj in ctx.args] if ctx.args else []

		return behav.FunctionCall(ref, args, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitBlock(self, ctx: CoreDSL2Parser.BlockContext):
		"""Generate a block of statements, return a list."""

		items = [self.visit(obj) for obj in ctx.items]
		items = list(flatten(items))
		return behav.Block(items, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitDeclaration(self, ctx: CoreDSL2Parser.DeclarationContext):
		"""Generate a declaration statement. Can be multiple declarations of
		the same type at once. Each declaration can have an initial value.
		"""

		# extract variable qualifiers, currently unused
		storage = [self.visit(obj) for obj in ctx.storage]
		qualifiers = [self.visit(obj) for obj in ctx.qualifiers]
		attributes = [self.visit(obj) for obj in ctx.attributes]

		type_ = self.visit(ctx.type_)

		decls: "list[CoreDSL2Parser.DeclaratorContext]" = ctx.declarations

		ret_decls = []

		# iterate over all contained declarations
		for decl in decls:
			name = decl.name.text

			if (hasattr(decl, "size")):
				if len(decl.size) != 0 and decl.size != None:
					shape = []
					for ele in reversed(decl.size):
						m2isar_ele = self.visit(ele)
						type_ = type_info.ArrayType(type_, m2isar_ele)
						# # Why even limit this so far?
						# if (type(m2isar_ele) == behav.IntLiteral):
						# 	shape.append(m2isar_ele.value)
						# else:
						# 	raise(f"Unexpected Type {type(ele)} within Shape array")

			# instantiate a .var and its definition
			s = arch.Variable(name, type_, attribute_info.StaticAttribute.NONE)
			self._vars[name] = s
			sd = behav.VarDefinition(s)

			# if initializer is present, generate an assignment to apply
			# initialization to the Variable
			init = None
			if decl.init:
				init = self.visit(decl.init)
				if isinstance(init, list):
					for ele_nr in range(len(init)):
						ele = init[ele_nr]
						if isinstance(ele, behav.UnaryOperation):
							res : int = int(eval(f"{ele.op.value}{ele.right.value}"))
							ele = behav.Literal(res, type_.element_type, ele.line_info)
							init[ele_nr] = ele
						if not isinstance(ele, behav.Literal):
							raise M2TypeError(f"Initializer list can only contain literals, but got {type(ele)}")
					init = behav.Tensor(create_np_array_from_literal_array(init, type_), type_)
			else:
				if isinstance(type_, type_info.PrimitiveType):
					init = behav.Literal(0, type_)
				elif isinstance(type_, type_info.ArrayType):
					shape = []
					infer_shape_from_type(type_, shape)
					init = behav.Tensor(np.zeros(shape), type_)
				else:
					raise f"Literal has a not supported type {type}"


			a = behav.Assignment(sd, init, LineInfoFactory.make(decl.start.source[1].fileName, decl.start.start, decl.stop.stop, decl.start.line, decl.stop.line))
			ret_decls.append(a)

		return ret_decls

	def visitInitializerList(self, ctx: CoreDSL2Parser.InitializerListContext):
		"""Generate a list of initializers for array/tensor initialization."""

		inits : list[behav.Literal] = [self.visit(obj) for obj in list(ctx.getChildren())
									if isinstance(obj, CoreDSL2Parser.InitializerContext)]
		return inits


	def visitBreak_statement(self, ctx: CoreDSL2Parser.Break_statementContext):
		return behav.Break(LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line, placement=LineInfoPlacement.BEFORE))

	def visitReturn_statement(self, ctx: CoreDSL2Parser.Return_statementContext):
		"""Generate a return statement."""

		expr = self.visit(ctx.expr) if ctx.expr else None
		return behav.Return(expr, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line, placement=LineInfoPlacement.BEFORE))

	def visitWhile_statement(self, ctx: CoreDSL2Parser.While_statementContext):
		"""Generate a while loop."""

		stmt = self.visit(ctx.stmt) if ctx.stmt else None
		cond = self.visit(ctx.cond)

		if not isinstance(stmt, list):
			stmt = [stmt]

		return behav.Loop(cond, stmt, False, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitDo_statement(self, ctx: CoreDSL2Parser.Do_statementContext):
		"""Generate a do .. while loop."""

		stmt = self.visit(ctx.stmt) if ctx.stmt else None
		cond = self.visit(ctx.cond)

		if not isinstance(stmt, list):
			stmt = [stmt]

		return behav.Loop(cond, stmt, True, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitFor_statement(self, ctx: CoreDSL2Parser.For_statementContext):
		"""Generate a for loop. Currently hacky, untested and mostly broken."""

		start_decl, start_expr, end_expr, loop_exprs = self.visit(ctx.cond)
		stmt = self.visit(ctx.stmt) if ctx.stmt else None

		if not isinstance(stmt, list):
			stmt = [stmt]

		ret = []

		if start_decl is not None:
			ret.append(start_decl)
		if start_expr is not None:
			ret.append(start_expr)

		if loop_exprs:
			stmt.extend(loop_exprs)

		ret.append(behav.Loop(end_expr, stmt, False, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line)))

		return ret

	def visitFor_condition(self, ctx: CoreDSL2Parser.For_conditionContext):
		"""Generate the condition of a for loop."""

		start_decl = self.visit(ctx.start_decl) if ctx.start_decl else None
		start_expr = self.visit(ctx.start_expr) if ctx.start_expr else None
		end_expr = self.visit(ctx.end_expr) if ctx.end_expr else None
		loop_exprs = [self.visit(obj) for obj in ctx.loop_exprs] if ctx.loop_exprs else None

		return start_decl, start_expr, end_expr, loop_exprs

	def visitIf_statement(self, ctx: CoreDSL2Parser.If_statementContext):
		"""Generate an if statement. Packs all if, else if and else branches
		into one object.
		"""

		entry_info = BranchEntryInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line)

		conds = [self.visit(x) for x in ctx.cond]
		stmts = [self.visit(x) for x in ctx.stmt]

		stmts = [x if not isinstance(x, list) else None for x in stmts]

		for cond in conds:
			old_line_info: LineInfo = cond.line_info
			new_line_info = BranchInfo(**dataclasses.asdict(old_line_info), branch_id=entry_info.branch_id)
			cond.line_info = new_line_info

		if None in stmts:
			raise Exception("meep")

		return behav.Conditional(conds, stmts, entry_info)

	def visitConditional_expression(self, ctx: CoreDSL2Parser.Conditional_expressionContext):
		"""Generate a ternary expression."""

		cond = self.visit(ctx.cond)
		then_expr = self.visit(ctx.then_expr)
		else_expr = self.visit(ctx.else_expr)

		return behav.Ternary(cond, then_expr, else_expr, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitBinary_expression(self, ctx: CoreDSL2Parser.Binary_expressionContext):
		"""Generate a binary expression."""

		left = self.visit(ctx.left)
		op =  behav.Operator(ctx.bop.text)
		right = self.visit(ctx.right)

		return behav.BinaryOperation(left, op, right, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitPreinc_expression(self, ctx: CoreDSL2Parser.Preinc_expressionContext):
		"""Generate a pre-increment expression. Not yet supported, throws
		:exc:`NotImplementedError`."""

		raise NotImplementedError("pre-increment expressions are not supported yet")

	def visitPostinc_expression(self, ctx: CoreDSL2Parser.Preinc_expressionContext):
		"""Generate a post-increment expression. Not yet supported, throws
		:exc:`NotImplementedError`."""

		raise NotImplementedError("post-increment expressions are not supported yet")

	def visitPrefix_expression(self, ctx: CoreDSL2Parser.Prefix_expressionContext):
		"""Generate an unary expression."""

		op = behav.Operator(ctx.prefix.text)
		right = self.visit(ctx.right)

		return behav.UnaryOperation(op, right, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitParens_expression(self, ctx: CoreDSL2Parser.Parens_expressionContext):
		"""Generate a parenthesized expression."""

		expr = self.visit(ctx.expr)
		return behav.Group(expr, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitSlice_expression(self, ctx: CoreDSL2Parser.Slice_expressionContext):
		"""Generate a slice expression. Depending on context, this is translated
		to either an actual :class:`m2isar.metamodel.behav.SliceOperation`or
		an :class:`m2isar.metamodel.behav.IndexedReference` if a :class:`m2isar.metamodel.arch.Memory/RegisterBank
		object is to be sliced.
		"""

		expr = self.visit(ctx.expr)

		left = self.visit(ctx.left)
		right = self.visit(ctx.right) if ctx.right else left

		# TODO distinguish between Multi-Dimensional Slices and BitSlice with ArrayType/PrimitiveType???
		if isinstance(expr, behav.NamedReference) and isinstance(expr.reference.ty, type_info.ArrayType):
			assert(isinstance(expr.reference.ty, type_info.ArrayType))
			#Dont duplicate index to differentiate between index and ranged access
			if right == left:
					return behav.IndexedReference(expr.reference, left, None, \
								   LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))
			else:
					return behav.IndexedReference(expr.reference, left, right, \
								   LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))
		else:
			return behav.SliceOperation(expr, left, right, \
							   LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitConcat_expression(self, ctx: CoreDSL2Parser.Concat_expressionContext):
		"""Generate a concatenation expression."""

		left = self.visit(ctx.left)
		right = self.visit(ctx.right)

		return behav.ConcatOperation(left, right, \
							   LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitAssignment_expression(self, ctx: CoreDSL2Parser.Assignment_expressionContext):
		"""Generate an assignment. If a combined arithmetic-assignment is present,
		generate an additional binary operation and use it as the RHS.
		"""

		op = ctx.bop.text
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)

		if op != "=":
			op2 = behav.Operator(op[:-1])
			left_2 = copy.copy(left)
			left_2.line_info = None
			right = behav.BinaryOperation(left_2, op2, right)

		return behav.Assignment(left, right, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitReference_expression(self, ctx: CoreDSL2Parser.Reference_expressionContext):
		"""Generate a simple reference."""

		name = ctx.ref.text

		var = self._vars.get(name) or \
			self._fields.get(name) or \
			self._parameters.get(name) or \
			self._memory_aliases.get(name) or \
			self._memories.get(name) or \
			self._register_aliases.get(name) or \
			self._register_banks.get(name) or \
			intrinsics.get(name)

		if var is None:
			raise M2NameError(f"Named reference \"{name}\" does not exist!")

		return behav.NamedReference(var, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitInteger_constant(self, ctx: CoreDSL2Parser.Integer_constantContext):
		"""Generate an integer literal."""

		text: str = ctx.value.text.lower()

		tick_pos = text.find("'")

		if tick_pos != -1:
			width = int(text[:tick_pos])
			radix = text[tick_pos+1]
			value = int(text[tick_pos+2:], RADIX[radix])

		else:
			value = int(text, 0)
			width = value.bit_length()

		kind = type_info.TypeKind.INT if value <= 0 else type_info.TypeKind.UINT

		return behav.Literal(value,  type_info.PrimitiveType(kind, width), line_info=LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitCharacter_constant(self, ctx: CoreDSL2Parser.Character_constantContext):
		"""Generate a character literal. Converts directly to uint8."""

		text: str = ctx.value.text

		value = min(ord(text.replace("'", "")), 255)

		return behav.Literal(value, type_info.PrimitiveType(type_info.TypeKind.UINT, size=8), line_info=LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitString_constant(self, ctx: CoreDSL2Parser.String_constantContext):
		text: str = ctx.value.text
		assert len(text) >= 2
		assert text[0] == '"' and text[-1] == '"'
		text = text[1:-1]

		return behav.Literal(text, type_info.PrimitiveType(type_info.TypeKind.STR, len(text)), line_info=LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitBool_constant(self, ctx: CoreDSL2Parser.Bool_constantContext):
		"""Generate a boolean literal. Converts directly to uint1."""

		text: str = ctx.value.text

		return behav.Literal(BOOLCONST[text], type_info.PrimitiveType(type_info.TypeKind.UINT, 1), line_info=LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitCast_expression(self, ctx: CoreDSL2Parser.Cast_expressionContext):
		"""Generate a type cast."""

		expr = self.visit(ctx.right)
		if ctx.type_:
			type_ = self.visit(ctx.type_)
			kind = type_.kind
			size = type_.size

		if ctx.sign:
			sign = self.visit(ctx.sign)
			kind = type_info.TypeKind.INT if sign else type_info.TypeKind.UINT
			size = None

		return behav.TypeConv(kind, size, expr, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitType_specifier(self, ctx: CoreDSL2Parser.Type_specifierContext):
		"""Generate a generic type specifier."""

		type_ = self.visit(ctx.type_)
		if ctx.ptr:
			type_ = type_info.PointerType(type_)
		return type_

	def visitInteger_type(self, ctx: CoreDSL2Parser.Integer_typeContext):
		"""Generate an integer type specifier."""

		signed = True
		width = None

		if ctx.signed is not None:
			signed = self.visit(ctx.signed)

		if ctx.size is not None:
			width = self.visit(ctx.size)

		if ctx.shorthand is not None:
			width = self.visit(ctx.shorthand)

		if isinstance(width, behav.BaseNode):
			width =  exprInterpretVisitor.generate(width, None)
		else:
			raise M2TypeError("width has wrong type")

		kind = type_info.TypeKind.INT if signed else type_info.TypeKind.UINT

		return type_info.PrimitiveType(kind, width)

	def visitVoid_type(self, ctx: CoreDSL2Parser.Void_typeContext):
		"""Generate a void type specifier."""

		return type_info.PrimitiveType(type_info.TypeKind.VOID, None)

	def visitBool_type(self, ctx: CoreDSL2Parser.Bool_typeContext):
		"""Generate a bool type specifier. Aliases to unsigned<1>."""

		return type_info.PrimitiveType(type_info.TypeKind.UINT, 1)

	def visitInteger_signedness(self, ctx: CoreDSL2Parser.Integer_signednessContext):
		"""Generate integer signedness."""

		return SIGNEDNESS[ctx.children[0].symbol.text]

	def visitInteger_shorthand(self, ctx: CoreDSL2Parser.Integer_shorthandContext):
		"""Lookup a shorthand type specifier."""

		return behav.Literal(SHORTHANDS[ctx.children[0].symbol.text], line_info=LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))
