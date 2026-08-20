# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import itertools
import logging
from typing import Union

from ... import (M2DuplicateError, M2NameError, M2TypeError, M2ValueError,
                 flatten)
from ...metamodel import arch, behav, type_info, attribute_info, intrinsics
from ...metamodel.code_info import FunctionInfoFactory
from ..coredsl2.parser_gen import CoreDSL2Parser, CoreDSL2Visitor
from ..coredsl2.utils import RADIX, SHORTHANDS, SIGNEDNESS
from ..coredsl2.expr_interpreter import ExprInterpreterVisitor

logger = logging.getLogger("arch_builder")
exprInterpretVisitor = ExprInterpreterVisitor()

class ArchitectureModelBuilder(CoreDSL2Visitor):
	"""ANTLR visitor to build an M2-ISA-R architecture model of a CoreDSL 2 specification."""

	_parameters: "dict[str, arch.Parameter]"
	_instructions: "list[arch.Instruction]"
	_functions: "dict[str, arch.Function]"
	_always_blocks: "dict[str, arch.AlwaysBlock]"
	_instruction_sets: "dict[str, arch.InstructionSet]"
	_read_types: "dict[str, str]"
	_memories: "dict[str, arch.Memory]"
	_memory_aliases: "dict[str, arch.Alias]"
	_register_banks: "dict[str, Union[arch.RegisterBank, arch.Register]]"
	_register_aliases: "dict[str, arch.Alias]"
	_overwritten_instrs: "list[tuple[arch.Instruction, arch.Instruction]]"
	_instr_classes: "set[int]"
	_main_reg_file: Union[arch.RegisterBank, None]
	_float_reg_file: Union[arch.RegisterBank, None]
	_vector_reg_file: Union[arch.RegisterBank, None]
	_csr_reg_file: Union[arch.RegisterBank, None]

	def __init__(self, merge: bool = False):
		super().__init__()
		self._parameters = {}
		# self._instructions = {}
		self._instructions = []
		self._functions = {}
		self._always_blocks = {}
		self._instruction_sets = {}
		self._read_types = {}
		self._memories = {}
		self._memory_aliases = {}
		self._register_banks = {}
		self._register_aliases = {}

		self._overwritten_instrs = []
		self._instr_classes = set()
		self._main_reg_file = None
		self._float_reg_file = None
		self._vector_reg_file = None
		self._csr_reg_file = None
		self.merge = merge

	def visitBit_field(self, ctx: CoreDSL2Parser.Bit_fieldContext):
		"""Generate a bit field (instruction parameter in encoding)."""

		# generate lower and upper bounds
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)

		# instantiate M2-ISA-R objects
		range_spec = arch.RangeSpec(left.value, right.value)
		return arch.BitField(ctx.name.text, range_spec, type_info.TypeKind.UINT)

	def visitBit_value(self, ctx: CoreDSL2Parser.Bit_valueContext):
		"""Generate a fixed encoding part."""

		val = self.visit(ctx.value)
		return arch.BitVal(val.ty.size, val.value)

	def visitInstruction_set(self, ctx: CoreDSL2Parser.Instruction_setContext):
		"""Generate a top-level instruction set object."""

		# keep track of seen instruction set names
		self._read_types[ctx.name.text] = None

		name = ctx.name.text
		extension = []
		if ctx.extension:
			if len(ctx.extension) > 1:
				logger.warning("Extending more than one InstrSet is not CoreDSL2 compiliant!")
			extension = [obj.text for obj in ctx.extension]

		combines = []
		if ctx.combines:
			combines = [obj.text for obj in ctx.combines]
			assert len(ctx.sections) == 0
			sections = []
		else:
			sections = ctx.sections

		# generate flat list of instruction set contents
		contents = flatten([self.visit(obj) for obj in sections])

		parameters = {}
		memories = {}
		memory_aliases = {}
		register_banks = {}
		register_aliases = {}
		functions = {}
		always_blocks = {}
		# instructions = {}
		instructions = []
		# instructions += self._instructions
		if self.merge:
			parameters.update(self._parameters)
			memories.update(self._memories)
			memory_aliases.update(self._memory_aliases)
			register_banks.update(self._register_banks)
			register_aliases.update(self._register_aliases)
			functions.update(self._functions)

		# group contents by type
		for item in contents:
			if item is None:
				continue
			if isinstance(item, arch.Parameter):
				parameters[item.name] = item
			elif isinstance(item, arch.Memory):
				memories[item.name] = item
			elif isinstance(item, (arch.RegisterBank, arch.Register)):
				register_banks[item.name] = item
			elif isinstance(item, arch.Alias):
				assert item.parent is not None
				if isinstance(item.parent, arch.Memory):
					memory_aliases[item.name] = item
				elif isinstance(item.parent, (arch.RegisterBank, arch.Register)):
					register_aliases[item.name] = item
				else:
					raise M2TypeError(f"Unhandled alias parent type: {type(item.parent)}")
				register_aliases[item.name] = item
			elif isinstance(item, arch.Function):
				functions[item.name] = item
				item.ext_name = name
			elif isinstance(item, arch.Instruction):
				# instructions[(item.code, item.mask)] = item
				instructions.append(item)
				item.ext_name = name
			elif isinstance(item, arch.AlwaysBlock):
				always_blocks[item.name] = item
			else:
				raise M2ValueError(f"unexpected item encountered: {type(item)}")

		# instantiate M2-ISA-R object
		if ctx.combines:
			i = arch.InstructionSetGroup(name, combines)
		else:
			i = arch.InstructionSet(name, extension, parameters, memories, memory_aliases, register_banks, register_aliases, functions, instructions, always_blocks)

		if name in self._instruction_sets:
			raise M2DuplicateError(f"instruction set \"{name}\" already defined")

		# keep track of instruction set object
		self._instruction_sets[name] = i
		return i

	def visitSection_instructions(self, ctx: CoreDSL2Parser.Section_instructionsContext):
		attributes = dict([self.visit(obj) for obj in ctx.attributes])
		instructions: "list[arch.Instruction]" = [self.visit(obj) for obj in ctx.instructions]

		for attr, val in attributes.items():
			for instr in instructions:
				if attr not in instr.attributes:
					instr.attributes[attr] = val

		return instructions

	def visitCore_def(self, ctx: CoreDSL2Parser.Core_defContext):
		"""Generate a top-level CoreDef object."""

		self.visitChildren(ctx)

		name = ctx.name.text

		c = arch.CoreDef(name, list(self._read_types.keys()), None,
			self._parameters, self._memories, self._memory_aliases,
			self._register_banks, self._register_aliases, self._functions,
			self._instructions, self._instr_classes, intrinsics, self._always_blocks)

		return c

	def visitSection_arch_state(self, ctx: CoreDSL2Parser.Section_arch_stateContext):
		"""Generate "archictectural_state" section of CoreDSL file."""

		decls = [self.visit(obj) for obj in ctx.declarations]
		decls = list(itertools.chain.from_iterable(decls))
		for obj in ctx.expressions:
			self.visit(obj)

		return decls

	def visitAlways_block(self, ctx: CoreDSL2Parser.Always_blockContext):
		"""Generate always block"""

		name = ctx.name.text
		attributes = dict([self.visit(obj) for obj in ctx.attributes])

		a = arch.AlwaysBlock(name, attributes, ctx.behavior)

		self._always_blocks[name] = a

		return a

	def visitInstruction(self, ctx: CoreDSL2Parser.InstructionContext):
		"""Generate non-behavioral parts of an instruction."""

		# read encoding, attributes and disassembly
		encoding = [self.visit(obj) for obj in ctx.encoding]
		attributes = dict([self.visit(obj) for obj in ctx.attributes])
		assembly = ctx.assembly.text.replace("\"", "") if ctx.assembly is not None else None
		mnemonic = ctx.mnemonic.text.replace("\"", "") if ctx.mnemonic is not None else None

		i = arch.Instruction(ctx.name.text, attributes, encoding, mnemonic, assembly, ctx.behavior, None)
		self._instr_classes.add(i.size)

		# instr_id = (i.code, i.mask)

		opcode_str = "{code:0{width}x}:{mask:0{width}x}".format(code=i.code, mask=i.mask, width=i.size//4)
		i.function_info = FunctionInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line, f"instr_{i.name}_{opcode_str}")

		# check for duplicate instructions
		# if instr_id in self._instructions:
		# 	self._overwritten_instrs.append((self._instructions[instr_id], i))

		# keep track of instruction
		# self._instructions[instr_id] = i
		self._instructions.append(i)

		return i

	def visitFunction_definition(self, ctx: CoreDSL2Parser.Function_definitionContext):
		"""Generate non-behavioral parts of a function."""

		# decode attributes
		attributes = dict([self.visit(obj) for obj in ctx.attributes])

		if attribute_info.FunctionAttribute.ETISS_TRAP_ENTRY_FN in attributes:
			attributes[attribute_info.FunctionAttribute.ETISS_NEEDS_ARCH] = []

		# decode return type and name
		type_ = self.visit(ctx.type_)
		name = ctx.name.text

		# decode function arguments
		params = []
		if ctx.params:
			params = self.visit(ctx.params)

		if not isinstance(params, list):
			params = [params]

		return_size = None
		data_type = type_info.TypeKind.VOID

		if isinstance(type_, type_info.PrimitiveType):
			return_size = type_.size
			data_type = type_.kind

		f = arch.Function(name, attributes, return_size, data_type, params, ctx.behavior, ctx.extern is not None)
		if not f.extern:
			f.function_info = FunctionInfoFactory.make(ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line, "fn_" + f.name)

		# error on duplicate function definition
		# TODO: implement overwriting function prototypes?
		f2 = self._functions.get(name, None)

		if f2 is not None:
			if len(f2.operation.statements) > 0:
				raise M2DuplicateError(f"function \"{name}\" already defined")

			self._functions.pop(name)

		self._functions[name] = f
		return f

	def visitParameter_declaration(self, ctx: CoreDSL2Parser.Parameter_declarationContext):
		"""Generate function argument declaration."""

		# type is required, name and array size optional
		type_ = self.visit(ctx.type_)
		name = None
		size = None
		if ctx.decl:
			if ctx.decl.name:
				name = ctx.decl.name.text
			if ctx.decl.size:
				size = [self.visit(obj) for obj in ctx.decl.size]

		p = arch.FnParam(name, type_)
		return p

	def visitInteger_constant(self, ctx: CoreDSL2Parser.Integer_constantContext):
		"""Generate an integer literal."""

		# extract raw text
		text: str = ctx.value.text.lower()

		# extract tick position for verilog-stlye literal
		tick_pos = text.find("'")

		# decode verilog-style literal
		value = None
		if tick_pos != -1:
			width = int(text[:tick_pos])
			radix = text[tick_pos+1]
			value = int(text[tick_pos+2:], RADIX[radix])

		# decode normal dec, hex, bin, oct literal
		# TODO: remove width inference from text
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

		kind = type_info.TypeKind.UINT if value>0 else type_info.TypeKind.INT
		return behav.Literal(value, type_info.PrimitiveType(kind, width))

	def visitDeclaration(self, ctx: CoreDSL2Parser.DeclarationContext):
		"""Generate a declaration."""

		# extract storage type, qualifiers and attributes
		storage = [self.visit(obj) for obj in ctx.storage]
		qualifiers = [self.visit(obj) for obj in ctx.qualifiers]
		attributes = dict([self.visit(obj) for obj in ctx.attributes])

		# extract data type
		type_ = self.visit(ctx.type_)
		assert isinstance(type_, (type_info.PrimitiveType, type_info.PointerType))

		# extract list of contained declarations for the given type
		decls: "list[CoreDSL2Parser.DeclaratorContext]" = ctx.declarations

		ret_decls = []

		# generate each declaration
		for decl in decls:
			name = decl.name.text

			# generate a register alias
			if isinstance(type_, type_info.PointerType):
				# error out on duplicate declaration
				if name in self._memory_aliases or name in self._register_aliases:
					raise M2DuplicateError(f"memory {name} already defined")

				# assume default size
				size = [1]
				# alias needs to have a reference as initializer
				init: behav.IndexedReference = self.visit(decl.init)
				attributes = {}

				# extract array size
				if decl.size:
					size = [self.visit(obj).value for obj in decl.size]

				# extract referenced object and indices
				left = init.index
				right = init.right if init.right is not None else left
				reference = init.reference

				if decl.attributes:
					attributes = dict([self.visit(obj) for obj in decl.attributes])

				range_spec = arch.RangeSpec(left, right)

				#if range.length != size[0]:
				#	raise ValueError(f"range mismatch for \"{name}\"")

				# instantiate M2-ISA-R object, keep track of parent - child relations

				if attribute_info.RegisterAttribute.IS_PC in attributes:
					raise NotImplementedError(f"The program counter must be a register not an alias with name {name}")

				# Alias require a range to store details in Array, where it exactly points to (Ty is lhs info)
				alias = arch.Alias(name, reference, range_spec, type_, attributes)

				alias.parent.children.append(alias)

				# keep track of this declaration globally
				if isinstance(reference, (arch.RegisterBank, arch.Register)):
					self._register_aliases[name] = alias
				elif isinstance(reference, arch.Memory):
					self._memory_aliases[name] = alias
				else:
					raise M2TypeError("invalid alias reference type")
				# keep track of this declaration for this declaration statement
				ret_decls.append(alias)

			# normal declaration
			else:
				# no storage specifier -> implementation parameter, "Constant" in M2-ISA-R
				if len(storage) == 0:
					if name in self._parameters:
						raise M2DuplicateError(f"Parameter {name} already defined")

					# extract initializer if present
					init = None
					if decl.init is not None:
						init = self.visit(decl.init)

					signed = True if type_.kind == type_info.TypeKind.INT else False

					c = arch.Parameter(name, init, [], type_.size, signed)

					self._parameters[name] = c
					ret_decls.append(c)

				# register and extern declaration: "Memory" object in M2-ISA-R
				elif "register" in storage:
					if name in self._register_banks:
						raise M2DuplicateError(f"register bank {name} already defined")

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

					reg = None
					# TODO: Constant might be 1 as well and makes a RegisterBank to Register ... [1] should be illegal anyways?
					if isinstance(size[0], (arch.Parameter, behav.NamedReference)):
						reg = arch.RegisterBank(name, size[0], type_.kind, type_.size, attributes)
					elif isinstance(size[0], behav.Literal):
						if size[0].value >= 1:
							reg = arch.RegisterBank(name, size[0].value, type_.kind, type_.size, attributes)
						elif size[0].value == 1:
							reg = arch.Register(name, type_.kind, type_.size, attributes)
						else:
							M2ValueError("Size is negative for Registerbank")
					elif isinstance(size[0], int):
						# Unset Case: =1
						reg = arch.Register(name, type_.kind, type_.size, attributes)
					else:
						raise NotImplementedError("Only constant Parameter and Int allowed as dimension for register size")

					assert isinstance(reg, Union[arch.Register, arch.RegisterBank])
					
					# attach init value to register bank object
					if init is not None:
						reg._initval[None] = exprInterpretVisitor.generate(init, None)

					if isinstance(reg, arch.RegisterBank):
						if reg.is_main_reg:
							self._main_reg_file = reg
						elif reg.is_float_reg:
							self._float_reg_file = reg
						elif reg.is_vector_reg:
							self._vector_reg_file = reg
						assert sum([reg.is_main_reg, reg.is_float_reg, reg.is_vector_reg]) <= 1

					self._register_banks[name] = reg
					ret_decls.append(reg)
				elif "extern" in storage:
					if name in self._memories:
						raise M2DuplicateError(f"memory {name} already defined")

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

					m = arch.Memory(name, type_.kind, type_.size, size[0], attributes)

					# attach init value to memory object
					if init is not None:
						m._initval[None] = exprInterpretVisitor.generate(init, None)


					if m.is_csr_reg:
						self._csr_reg_file = m
					elif m.is_main_mem:
						self.main_memory = m
					elif m.is_vector_reg:
						self._vector_reg_file = m

					self._memories[name] = m
					ret_decls.append(m)

		return ret_decls

	def visitType_specifier(self, ctx: CoreDSL2Parser.Type_specifierContext):
		type_ = self.visit(ctx.type_)
		if ctx.ptr:
			type_ = type_info.PointerType(type_)
			# type_.ptr = ctx.ptr.text
		return type_

	def visitInteger_type(self, ctx: CoreDSL2Parser.Integer_typeContext):
		"""Generate an integer type specification."""

		# default signedness
		signed = True
		# minimal integer type is just a signedness without width
		width = None

		# extract sign
		if ctx.signed is not None:
			signed = self.visit(ctx.signed)

		# extract size
		if ctx.size is not None:
			width = self.visit(ctx.size)

		# extract and decode shorthand (int = signed<32>)
		if ctx.shorthand is not None:
			width = self.visit(ctx.shorthand)

		# type check width
		if isinstance(width, behav.Literal):
			width = width.value
		elif isinstance(width, behav.NamedReference):
			width = width.reference
		else:
			raise M2TypeError("width has wrong type")

		kind = type_info.TypeKind.INT if signed else type_info.TypeKind.UINT

		return type_info.PrimitiveType(kind, width)

	def visitVoid_type(self, ctx: CoreDSL2Parser.Void_typeContext):
		"""Generate a void type."""
		return type_info.PrimitiveType(type_info.TypeKind.VOID, None)

	def visitBool_type(self, ctx: CoreDSL2Parser.Bool_typeContext):
		"""Generate a bool (alias for unsigned<1>)."""
		return type_info.PrimitiveType(type_info.TypeKind.UINT, 1)

	def visitBinary_expression(self, ctx: CoreDSL2Parser.Binary_expressionContext):
		"""Generate a binary expression."""

		# visit LHS and RHS
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)
		op = behav.Operator(ctx.bop.text)

		# return M2-ISA-R object
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
		"""Generate a referencing expression."""

		name = ctx.ref.text

		# try to resolve the reference, error out if invalid
		ref = self._parameters.get(name) or self._memories.get(name) or self._memory_aliases.get(name) \
			  or self._register_banks.get(name) or self._register_aliases.get(name)
		if ref is None:
			raise M2NameError(f"reference \"{name}\" could not be resolved")
		return behav.NamedReference(ref)

	def visitStorage_class_specifier(self, ctx: CoreDSL2Parser.Storage_class_specifierContext):
		return ctx.children[0].symbol.text

	def visitType_qualifier(self, ctx: CoreDSL2Parser.Type_qualifierContext):
		return ctx.children[0].symbol.text

	def visitInteger_signedness(self, ctx: CoreDSL2Parser.Integer_signednessContext):
		return SIGNEDNESS[ctx.children[0].symbol.text]

	def visitInteger_shorthand(self, ctx: CoreDSL2Parser.Integer_shorthandContext):
		value = SHORTHANDS[ctx.children[0].symbol.text]
		return behav.Literal(value)

	def visitAssignment_expression(self, ctx: CoreDSL2Parser.Assignment_expressionContext):
		"""Generate an assignment. """

		# extract LHS and RHS
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)

		# if LHS is a reference, assign RHS as its default value
		if isinstance(left, behav.NamedReference):
			if isinstance(left.reference, arch.Parameter):
				left.reference.value = exprInterpretVisitor.generate(right, None)
			elif isinstance(left.reference, (arch.Register, arch.Alias)):
				left.reference._initval[None] = exprInterpretVisitor.generate(right, None)
		elif isinstance(left, behav.IndexedReference):
			left.reference._initval[exprInterpretVisitor.generate(left.index, None)] = exprInterpretVisitor.generate(right, None)

	def visitAttribute(self, ctx: CoreDSL2Parser.AttributeContext):
		"""Generate an attribute."""

		name = ctx.name.text

		# read attribute from enums
		attr = attribute_info.InstrAttribute._member_map_.get(name.upper()) or \
			attribute_info.MemoryAttribute._member_map_.get(name.upper()) or \
			attribute_info.FunctionAttribute._member_map_.get(name.upper()) \
			or attribute_info.RegisterAttribute._member_map_.get(name.upper()) \
			or attribute_info.AlwaysBlockAttribute._member_map_.get(name.upper())

		# warn if attribute is unknown to M2-ISA-R
		if attr is None:
			logger.warning("unknown attribute \"%s\" encountered", name)
			attr = name

		return attr, ctx.params

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
