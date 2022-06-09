# SPDX-License-Identifier: Apache-2.0

# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (c) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import itertools
import logging
from typing import Union

from ... import M2DuplicateError, M2NameError, M2TypeError, M2ValueError
from ...metamodel import arch, behav
from .parser_gen import CoreDSL2Parser, CoreDSL2Visitor
from .utils import RADIX, SHORTHANDS, SIGNEDNESS, flatten_list

logger = logging.getLogger("arch_builder")


class ArchitectureModelBuilder(CoreDSL2Visitor):
	_constants: "dict[str, arch.Constant]"
	_instructions: "dict[str, arch.Instruction]"
	_functions: "dict[str, arch.Function]"
	_instruction_sets: "dict[str, arch.InstructionSet]"
	_read_types: "dict[str, str]"
	_memories: "dict[str, arch.Memory]"
	_memory_aliases: "dict[str, arch.Memory]"
	_overwritten_instrs: "list[tuple[arch.Instruction, arch.Instruction]]"
	_instr_classes: "set[int]"
	_main_reg_file: Union[arch.Memory, None]

	def __init__(self):
		super().__init__()
		self._constants = {}
		self._instructions = {}
		self._functions = {}
		self._instruction_sets = {}
		self._read_types = {}
		self._memories = {}
		self._memory_aliases = {}

		self._overwritten_instrs = []
		self._instr_classes = set()
		self._main_reg_file = None

	def visitBit_field(self, ctx: CoreDSL2Parser.Bit_fieldContext):
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)
		range = arch.RangeSpec(left.value, right.value)
		return arch.BitField(ctx.name.text, range, arch.DataType.U)

	def visitBit_value(self, ctx: CoreDSL2Parser.Bit_valueContext):
		val = self.visit(ctx.value)
		return arch.BitVal(val.bit_size, val.value)

	def visitInstruction_set(self, ctx: CoreDSL2Parser.Instruction_setContext):
		self._read_types[ctx.name.text] = None

		name = ctx.name.text
		extension = []
		if ctx.extension:
			extension = [obj.text for obj in ctx.extension]

		contents = flatten_list([self.visit(obj) for obj in ctx.sections])

		constants = {}
		memories = {}
		functions = {}
		instructions = {}

		for item in contents:
			if isinstance(item, arch.Constant):
				constants[item.name] = item
			elif isinstance(item, arch.Memory):
				memories[item.name] = item
			elif isinstance(item, arch.Function):
				functions[item.name] = item
				item.ext_name = name
			elif isinstance(item, arch.Instruction):
				instructions[(item.code, item.mask)] = item
				item.ext_name = name
			else:
				raise M2ValueError("unexpected item encountered")

		i = arch.InstructionSet(name, extension, constants, memories, functions, instructions)

		if name in self._instruction_sets:
			raise M2DuplicateError(f"instruction set {name} already defined")

		self._instruction_sets[name] = i
		return i

	def visitCore_def(self, ctx: CoreDSL2Parser.Core_defContext):
		self.visitChildren(ctx)

		name = ctx.name.text

		c = arch.CoreDef(name, list(self._read_types.keys()), None,
			self._constants, self._memories, self._memory_aliases,
			self._functions, self._instructions, self._instr_classes)

		return c

	def visitSection_arch_state(self, ctx: CoreDSL2Parser.Section_arch_stateContext):
		decls = [self.visit(obj) for obj in ctx.declarations]
		decls = list(itertools.chain.from_iterable(decls))
		for obj in ctx.expressions:
			self.visit(obj)

		return decls

	def visitInstruction(self, ctx: CoreDSL2Parser.InstructionContext):
		encoding = [self.visit(obj) for obj in ctx.encoding]
		attributes = dict([self.visit(obj) for obj in ctx.attributes])
		disass = ctx.disass.text if ctx.disass is not None else None

		i = arch.Instruction(ctx.name.text, attributes, encoding, disass, ctx.behavior)
		self._instr_classes.add(i.size)

		instr_id = (i.code, i.mask)

		if instr_id in self._instructions:
			self._overwritten_instrs.append((self._instructions[instr_id], i))

		self._instructions[instr_id] = i

		return i

	def visitFunction_definition(self, ctx: CoreDSL2Parser.Function_definitionContext):
		attributes = dict([self.visit(obj) for obj in ctx.attributes])

		if arch.FunctionAttribute.ETISS_EXC_ENTRY in attributes:
			attributes[arch.FunctionAttribute.ETISS_NEEDS_ARCH] = []

		type_ = self.visit(ctx.type_)
		name = ctx.name.text

		params = []
		if ctx.params:
			params = self.visit(ctx.params)

		if not isinstance(params, list):
			params = [params]

		return_size = None
		data_type = arch.DataType.NONE

		if isinstance(type_, arch.IntegerType):
			return_size = type_._width
			data_type = arch.DataType.S if type_.signed else arch.DataType.U

		f = arch.Function(name, attributes, return_size, data_type, params, ctx.behavior, ctx.extern is not None)

		f2 = self._functions.get(name, None)

		if f2 is not None:
			if len(f2.operation.statements) > 0:
				raise M2DuplicateError(f"function {name} already defined")

		self._functions[name] = f
		return f

	def visitParameter_declaration(self, ctx: CoreDSL2Parser.Parameter_declarationContext):
		type_ = self.visit(ctx.type_)
		name = None
		size = None
		if ctx.decl:
			if ctx.decl.name:
				name = ctx.decl.name.text
			if ctx.decl.size:
				size = [self.visit(obj) for obj in ctx.decl.size]

		p = arch.FnParam(name, type_._width, arch.DataType.S if type_.signed else arch.DataType.U)
		return p

	def visitInteger_constant(self, ctx: CoreDSL2Parser.Integer_constantContext):
		text: str = ctx.value.text.lower()

		tick_pos = text.find("'")

		if tick_pos != -1:
			width = int(text[:tick_pos])
			radix = text[tick_pos+1]
			value = int(text[tick_pos+2:], RADIX[radix])

		else:
			value = int(text, 0)
			if text.startswith("0b"):
				width = len(text) - 2
			elif text.startswith("0x"):
				width = (len(text) - 2) * 4
			elif text.startswith("0") and len(text) > 1:
				width = (len(text) - 1) * 3
			else:
				width = value.bit_length()

		return behav.IntLiteral(value, width)

	def visitDeclaration(self, ctx: CoreDSL2Parser.DeclarationContext):
		storage = [self.visit(obj) for obj in ctx.storage]
		qualifiers = [self.visit(obj) for obj in ctx.qualifiers]
		attributes = dict([self.visit(obj) for obj in ctx.attributes])

		type_ = self.visit(ctx.type_)

		decls: "list[CoreDSL2Parser.DeclaratorContext]" = ctx.declarations

		ret_decls = []

		for decl in decls:
			name = decl.name.text

			if type_.ptr == "&": # register alias
				size = [1]
				init: behav.IndexedReference = self.visit(decl.init)
				attributes = {}

				if decl.size:
					size = [self.visit(obj).value for obj in decl.size]

				left = init.index
				right = init.right if init.right is not None else left
				reference = init.reference

				if decl.attributes:
					attributes = dict([self.visit(obj) for obj in decl.attributes])

				range = arch.RangeSpec(left, right)

				#if range.length != size[0]:
				#	raise ValueError(f"range mismatch for {name}")

				m = arch.Memory(name, range, type_._width, attributes)
				m.parent = reference
				m.parent.children.append(m)

				if name in self._memory_aliases:
					raise M2DuplicateError(f"memory {name} already defined")

				self._memory_aliases[name] = m
				ret_decls.append(m)

			else:
				if len(storage) == 0: # no storage specifier -> implementation parameter, "Constant" in M2-ISA-R
					init = None
					if decl.init is not None:
						init = self.visit(decl.init)

					c = arch.Constant(name, init, [], type_._width, type_.signed)

					if name in self._constants:
						raise M2DuplicateError(f"constant {name} already defined")
					self._constants[name] = c
					ret_decls.append(c)

				elif "register" in storage or "extern" in storage:
					size = [1]
					init = None
					attributes = {}

					if decl.size:
						size = [self.visit(obj) for obj in decl.size]

					if len(size) > 1:
						raise NotImplementedError("arrays with more than one dimension are not supported")

					if decl.init is not None:
						init = self.visit(decl.init)

					if decl.attributes:
						attributes = dict([self.visit(obj) for obj in decl.attributes])

					range = arch.RangeSpec(size[0])
					m = arch.Memory(name, range, type_._width, attributes)
					if init is not None:
						m._initval[None] = init.generate(None)

					if name in self._memories:
						raise M2DuplicateError(f"memory {name} already defined")

					if arch.MemoryAttribute.IS_MAIN_REG in attributes:
						self._main_reg_file = m

					self._memories[name] = m
					ret_decls.append(m)

		return ret_decls

	def visitType_specifier(self, ctx: CoreDSL2Parser.Type_specifierContext):
		type_ = self.visit(ctx.type_)
		if ctx.ptr:
			type_.ptr = ctx.ptr.text
		return type_

	def visitInteger_type(self, ctx: CoreDSL2Parser.Integer_typeContext):
		signed = True
		width = None

		if ctx.signed is not None:
			signed = self.visit(ctx.signed)

		if ctx.size is not None:
			width = self.visit(ctx.size)

		if ctx.shorthand is not None:
			width = self.visit(ctx.shorthand)

		if isinstance(width, behav.IntLiteral):
			width = width.value
		elif isinstance(width, behav.NamedReference):
			width = width.reference
		else:
			raise M2TypeError("width has wrong type")

		return arch.IntegerType(width, signed, None)

	def visitVoid_type(self, ctx: CoreDSL2Parser.Void_typeContext):
		return arch.VoidType(None)

	def visitBool_type(self, ctx: CoreDSL2Parser.Bool_typeContext):
		return arch.IntegerType(1, False, None)

	def visitBinary_expression(self, ctx: CoreDSL2Parser.Binary_expressionContext):
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)
		op = behav.Operator(ctx.bop.text)
		return behav.BinaryOperation(left, op, right)

	def visitSlice_expression(self, ctx: CoreDSL2Parser.Slice_expressionContext):
		left = self.visit(ctx.left)
		right = self.visit(ctx.right) if ctx.right is not None else None
		expr = self.visit(ctx.expr).reference

		op = behav.IndexedReference(expr, left, right)
		return op

	def visitPrefix_expression(self, ctx: CoreDSL2Parser.Prefix_expressionContext):
		prefix = behav.Operator(ctx.prefix.text)
		expr = self.visit(ctx.right)
		return behav.UnaryOperation(prefix, expr)

	def visitReference_expression(self, ctx: CoreDSL2Parser.Reference_expressionContext):
		name = ctx.ref.text
		ref = self._constants.get(name) or self._memories.get(name) or self._memory_aliases.get(name)
		if ref is None:
			raise M2NameError(f"reference {name} could not be resolved")
		return behav.NamedReference(ref)

	def visitStorage_class_specifier(self, ctx: CoreDSL2Parser.Storage_class_specifierContext):
		return ctx.children[0].symbol.text

	def visitInteger_signedness(self, ctx: CoreDSL2Parser.Integer_signednessContext):
		return SIGNEDNESS[ctx.children[0].symbol.text]

	def visitInteger_shorthand(self, ctx: CoreDSL2Parser.Integer_shorthandContext):
		return behav.IntLiteral(SHORTHANDS[ctx.children[0].symbol.text])

	def visitAssignment_expression(self, ctx: CoreDSL2Parser.Assignment_expressionContext):
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)

		if isinstance(left, behav.NamedReference):
			if isinstance(left.reference, arch.Constant):
				left.reference.value = right.generate(None)

			elif isinstance(left.reference, arch.Memory):
				left.reference._initval[None] = right.generate(None)

		elif isinstance(left, behav.IndexedReference):
			left.reference._initval[left.index.generate(None)] = right.generate(None)

	def visitAttribute(self, ctx: CoreDSL2Parser.AttributeContext):
		name = ctx.name.text

		attr = arch.InstrAttribute._member_map_.get(name.upper()) or \
			arch.MemoryAttribute._member_map_.get(name.upper()) or \
			arch.FunctionAttribute._member_map_.get(name.upper())

		if attr is None:
			logger.warning("unknown attribute \"%s\" encountered", name)
			attr = name

		return attr, ctx.params

	def visitChildren(self, node):
		ret = super().visitChildren(node)
		if isinstance(ret, list) and len(ret) == 1:
			return ret[0]
		return ret

	def aggregateResult(self, aggregate, nextResult):
		ret = aggregate
		if nextResult is not None:
			if ret is None:
				ret = [nextResult]
			else:
				ret += [nextResult]
		return ret
