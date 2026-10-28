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

# CoreDSL [[access=...]] block attribute keywords and their metamodel access.
BLOCK_ACCESS = {
	"NONE": attribute_info.AccessAttribute.NONE,
	"CONST": attribute_info.AccessAttribute.READ,
	"STATIC": attribute_info.AccessAttribute.RW,
}

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
		self._all_vars = {}
		self._used_local_names = set().union(parameters, memories, memory_aliases,
			register_banks, register_aliases, fields, functions)
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

	def visitDeref_expression(self, ctx):
		# Never silently discard the base through the generated default visitor.
		raise M2TypeError("Composite member access is not supported by model lowering")

	def visitIntrinsic_expression(self, ctx):
		"""Fold supported size intrinsics using the source validator's type rules."""
		from types import SimpleNamespace
		from .source_semantics import SemanticValidator, DslSymbol
		from .source_types import address, enum, from_meta, integer

		validator = SemanticValidator(SimpleNamespace(definitions=[]), None)
		for name, parameter in self._parameters.items():
			validator.symbols[name] = DslSymbol(ty=integer(parameter.size, parameter.signed), storage='param',
				known_value=parameter.value, model=parameter)
			enum_name = getattr(parameter, '_coredsl_enum_name', None)
			if enum_name is not None:
				validator.enum_named_types[enum_name] = enum(integer(parameter.size, parameter.signed))
		for collection in (self._memories, self._memory_aliases, self._register_banks, self._register_aliases, self._fields, self._vars):
			for name, item in collection.items():
				ty = from_meta(item.ty, arch.get_const_or_val)
				if collection is self._memories and ty.kind == 'array':
					ty = address(ty.element, ty.count)
				validator.symbols[name] = DslSymbol(ty=ty, model=item)
		value = validator.intrinsic_value(ctx)
		if value is None:
			if ctx.ref.text == '__encoding_size':
				return behav.NamedReference(intrinsics.get('__encoding_size'), LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))
			raise M2TypeError(f"Cannot lower unresolved intrinsic {ctx.ref.text}")
		return behav.Literal(value, type_info.PrimitiveType(type_info.TypeKind.UINT, max(1, value.bit_length())),
			line_info=LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

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
		"""Generate an attributed block of statements."""

		attributes = {}
		for attr_ctx in ctx.attributes:
			name = attr_ctx.name.text
			attr = attribute_info.BlockAttribute._member_map_.get(name.upper()) or name
			if attr == attribute_info.BlockAttribute.ACCESS:
				if len(attr_ctx.params) != 1:
					raise M2SyntaxError("block access attribute requires exactly one value")
				value_name = attr_ctx.params[0].getText().upper()
				if value_name not in BLOCK_ACCESS:
					raise M2SyntaxError("block access attribute must be NONE, CONST, or STATIC")
				attributes[attr] = BLOCK_ACCESS[value_name]
			else:
				attributes[attr] = [self.visit(param) for param in attr_ctx.params]

		outer_vars = self._vars
		self._vars = outer_vars.copy()
		try:
			items = [self.visit(obj) for obj in ctx.items]
		finally:
			self._vars = outer_vars
		items = list(flatten(items))
		return behav.Block(
			items,
			LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line),
			attributes,
			explicit_attributes=set(attributes),
		)

	def visitDeclaration(self, ctx: CoreDSL2Parser.DeclarationContext):
		"""Generate a declaration statement. Can be multiple declarations of
		the same type at once. Each declaration can have an initial value.
		"""

		# extract variable qualifiers, currently unused
		storage = [self.visit(obj) for obj in ctx.storage]
		qualifiers = [obj.getText() for obj in ctx.qualifiers if isinstance(obj, CoreDSL2Parser.Type_qualifierContext)]
		attributes = [self.visit(obj) for obj in ctx.attributes]

		base_type = self.visit(ctx.type_)

		decls: "list[CoreDSL2Parser.DeclaratorContext]" = ctx.declarations

		ret_decls = []

		# iterate over all contained declarations
		for decl in decls:
			name = decl.name.text
			type_ = copy.deepcopy(base_type)

			if "volatile" in qualifiers:
				raise M2SyntaxError(f"Volatile qualifier is not supported, in declaration of {name}")

			if (hasattr(decl, "size")):
				if len(decl.size) != 0 and decl.size != None:
					shape = []
					for ele in reversed(decl.size):
						m2isar_ele = self.visit(ele)
						type_ = type_info.ArrayType(type_, m2isar_ele)


			# instantiate a .var and its definition
			attributes_dict = {**{attr: True for attr in qualifiers}}

			# Const value prohibits Write
			if attributes_dict.get("const", False):
				attributes_dict["static"] = attribute_info.AccessAttribute.READ

			# Backends emit model names directly; each declaration needs a unique
			# name even when CoreDSL allows it to shadow another declaration.
			model_name = name
			suffix = 2
			while model_name in self._used_local_names:
				model_name = f'{name}_{suffix}'
				suffix += 1
			self._used_local_names.add(model_name)
			s = arch.Variable(model_name, type_, attributes=attributes_dict)
			sd = behav.VarDefinition(s)

			# if initializer is present, generate an assignment to apply
			# initialization to the Variable
			init = None
			if decl.init:
				init = self.visit(decl.init)
				if isinstance(init, list):
					initializer_elements = list(init)
					for ele_nr in range(len(init)):
						ele = init[ele_nr]
						if isinstance(ele, behav.UnaryOperation):
							res : int = int(eval(f"{ele.op.value}{ele.right.value}"))
							ele = behav.Literal(res, type_.element_type, ele.line_info)
							init[ele_nr] = ele
						if not isinstance(ele, behav.Literal):
							raise M2TypeError(f"Initializer list can only contain literals, but got {type(ele)}")
					init = behav.Tensor(create_np_array_from_literal_array(init, type_), type_,
					                    initializer_elements=initializer_elements)
			else:
				if isinstance(type_, type_info.PrimitiveType):
					init = behav.Literal(0, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
				elif isinstance(type_, type_info.ArrayType):
					shape = []
					infer_shape_from_type(type_, shape)
					init = behav.Tensor(np.zeros(shape, dtype=object), type_)
				else:
					raise M2TypeError(f"Literal has a not supported type {type}")


			# The initializer sees the previous binding, including an outer local.
			self._vars[name] = s
			self._all_vars[model_name] = s
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

	def visitContinue_statement(self, ctx: CoreDSL2Parser.Continue_statementContext):
		return behav.Continue(LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line, placement=LineInfoPlacement.BEFORE))

	def visitReturn_statement(self, ctx: CoreDSL2Parser.Return_statementContext):
		"""Generate a return statement."""

		expr = self.visit(ctx.expr) if ctx.expr else None
		return behav.Return(expr, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line, placement=LineInfoPlacement.BEFORE))

	def visitWhile_statement(self, ctx: CoreDSL2Parser.While_statementContext):
		"""Generate a while loop."""

		stmt = self.visit(ctx.stmt) if ctx.stmt else None
		cond = self.visit(ctx.cond)

		if not isinstance(stmt, behav.Block):
			statements = list(flatten(stmt)) if isinstance(stmt, list) else [stmt]
			stmt = behav.Block(statements, getattr(stmt, "line_info", None))

		return behav.WhileLoop(cond, stmt, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitDo_statement(self, ctx: CoreDSL2Parser.Do_statementContext):
		"""Generate a do .. while loop."""

		stmt = self.visit(ctx.stmt) if ctx.stmt else None
		cond = self.visit(ctx.cond)

		if not isinstance(stmt, behav.Block):
			statements = list(flatten(stmt)) if isinstance(stmt, list) else [stmt]
			stmt = behav.Block(statements, getattr(stmt, "line_info", None))

		return behav.DoWhileLoop(stmt, cond, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitFor_statement(self, ctx: CoreDSL2Parser.For_statementContext):
		"""Keep initializer locals visible throughout the loop, then restore scope."""
		outer_vars = self._vars
		self._vars = outer_vars.copy()
		try:
			return self._lower_for_statement(ctx)
		finally:
			self._vars = outer_vars

	def _lower_for_statement(self, ctx: CoreDSL2Parser.For_statementContext):
		"""Retain the initializer and updates on the source-level for loop."""

		start_decl, start_expr, end_expr, loop_exprs = self.visit(ctx.cond)
		stmt = self.visit(ctx.stmt) if ctx.stmt else None

		if not isinstance(stmt, behav.Block):
			statements = list(flatten(stmt)) if isinstance(stmt, list) else [stmt]
			stmt = behav.Block(statements, getattr(stmt, "line_info", None))

		init = []

		if start_decl is not None:
			init.extend(list(flatten(start_decl)))
		if start_expr is not None:
			init.append(start_expr)

		return behav.ForLoop(
			init, end_expr, loop_exprs or [], stmt,
			LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line),
		)

	def visitFor_condition(self, ctx: CoreDSL2Parser.For_conditionContext):
		"""Generate the condition of a for loop."""

		start_decl = self.visit(ctx.start_decl) if ctx.start_decl else None
		start_expr = self.visit(ctx.start_expr) if ctx.start_expr else None
		end_expr = self.visit(ctx.end_expr) if ctx.end_expr else behav.Literal(
			1, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
		loop_exprs = [self.visit(obj) for obj in ctx.loop_exprs] if ctx.loop_exprs else None

		return start_decl, start_expr, end_expr, loop_exprs

	def visitIf_statement(self, ctx: CoreDSL2Parser.If_statementContext):
		"""Generate an if statement. Packs all if, else if and else branches
		into one object.
		"""

		entry_info = BranchEntryInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line)

		conds = [self.visit(x) for x in ctx.cond]
		stmts = [self.visit(x) for x in ctx.stmt]
		stmts = [
			x if isinstance(x, behav.Block) else behav.Block(
				list(flatten(x)) if isinstance(x, list) else [x],
				getattr(x, "line_info", None),
			)
			for x in stmts
		]

		for cond in conds:
			old_line_info: LineInfo = cond.line_info
			new_line_info = BranchInfo(**dataclasses.asdict(old_line_info), branch_id=entry_info.branch_id)
			cond.line_info = new_line_info

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
		return behav.UnaryOperation(behav.Operator(ctx.op.text), self.visit(ctx.right),
			LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))

	def visitPostinc_expression(self, ctx: CoreDSL2Parser.Postinc_expressionContext):
		return behav.UnaryOperation(behav.Operator(ctx.op.text), self.visit(ctx.left),
			LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line), postfix=True)

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
		"""Generate a slice expression.

		Depending on context, this is translated to either an actual
		:class:`~m2isar.metamodel.behav.SliceOperation` or an
		:class:`~m2isar.metamodel.behav.IndexedReference` if a
		:class:`~m2isar.metamodel.arch.Memory` or
		:class:`~m2isar.metamodel.arch.RegisterBank` object is to be sliced.
		"""

		expr = self.visit(ctx.expr)

		left = self.visit(ctx.left)
		right = self.visit(ctx.right) if ctx.right else left

		base = expr
		while isinstance(base, behav.Group):
			base = base.expr
		location = LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start,
									   ctx.stop.stop, ctx.start.line, ctx.stop.line)
		if isinstance(base, behav.NamedReference) and isinstance(base.reference.ty, type_info.ArrayType):
			return behav.IndexedReference(base.reference, left, right if ctx.right else None,
									  location, grouped_base=base is not expr)
		return behav.SliceOperation(expr, left, right, location)

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

		assignment = behav.Assignment(left, right, LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))
		if op != "=":
			assignment.compound_operator = op
		return assignment

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

		from .constant_expressions import integer_literal
		from ...diagnostics import M2ValidationError
		line_info = LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line)
		try:
			value, width, signed = integer_literal(ctx.value.text)
		except ValueError as exc:
			raise M2ValidationError(str(exc), 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax', line_info) from exc
		kind = type_info.TypeKind.INT if signed else type_info.TypeKind.UINT
		return behav.Literal(value, type_info.PrimitiveType(kind, width), line_info=line_info)

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

	def visitEnum_reference(self, ctx):
		for parameter in self._parameters.values():
			if getattr(parameter, '_coredsl_enum_name', None) == ctx.name.text:
				kind = type_info.TypeKind.INT if parameter.signed else type_info.TypeKind.UINT
				return type_info.PrimitiveType(kind, parameter.size)
		raise M2TypeError(f"Cannot lower unresolved enum type {ctx.name.text}")

	def visitBool_type(self, ctx: CoreDSL2Parser.Bool_typeContext):
		"""Generate a bool type specifier. Aliases to unsigned<1>."""

		return type_info.PrimitiveType(type_info.TypeKind.UINT, 1)

	def visitInteger_signedness(self, ctx: CoreDSL2Parser.Integer_signednessContext):
		"""Generate integer signedness."""

		return SIGNEDNESS[ctx.children[0].symbol.text]

	def visitInteger_shorthand(self, ctx: CoreDSL2Parser.Integer_shorthandContext):
		"""Lookup a shorthand type specifier."""

		return behav.Literal(SHORTHANDS[ctx.children[0].symbol.text], line_info=LineInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line))
