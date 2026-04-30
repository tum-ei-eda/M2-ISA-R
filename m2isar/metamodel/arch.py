# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""This module contains classes for modeling the architectural part
of an M2-ISA-R model. The architectural part is anything but the functional
behavior of functions and instructions.
"""

import dataclasses
import itertools
from collections import defaultdict
from typing import TYPE_CHECKING, Union
from m2isar.frontends.coredsl2.expr_interpreter import ExprInterpreterVisitor
from m2isar.metamodel import type_info, attribute_info

from .. import M2TypeError
from .behav import BaseNode, Operation, Literal

if TYPE_CHECKING:
	from .code_info import FunctionInfo
exprInterpretVisitor = ExprInterpreterVisitor()

def get_const_or_val(arg) -> int:
	if isinstance(arg, Constant):
		return arg.value

	if isinstance(arg, Literal):
		arg = int(arg.value)

	if isinstance(arg, BaseNode):
		arg = exprInterpretVisitor.generate(arg, None)

	return arg

class Named:
	"""A simple base class for a named object."""

	name: str
	"""The name of the object."""

	def __init__(self, name: str):
		self.name = name

	def __str__(self) -> str:
		return f'<{type(self).__name__} object>: name={self.name}'

	def __repr__(self) -> str:
		return f'<{type(self).__name__} object>: name={self.name}'

ValOrConst = Union[int, "Constant"]

class SizedRefOrConst(Named):
	"""A simple base class for an object with a name and a size.
	Size can be either an int, a Constant or a statically resolvable
	expression, expressed by a BaseNode.
	"""

	_size: Union[int, "Constant", "BaseNode"]
	"""The size of the object"""

	def __init__(self, name, size: ValOrConst):
		self._size = size
		super().__init__(name)

	@property
	def size(self) -> int:
		"""Returns the resolved size, by calling get_const_or_val on _size."""

		ret = get_const_or_val(self._size)
		if ret is None:
			return None
		return int(ret)

	def __str__(self) -> str:
		return f'{super().__str__()}, size={self.size}'

class Constant(SizedRefOrConst):
	"""An object holding a constant value. Should have a value at some point, also holds attributes
	and signedness information.
	"""

	_value: Union[int, "Constant", "BaseNode"]
	"""The value this object holds. Can be an int, another constant or a statically resolvable BaseNode."""

	attributes: "dict[type_info.ConstAttribute, list[BaseNode]]"
	"""A dictionary of attributes, mapping attribute type to a list of attribute arguments."""

	signed: bool
	"""The signedness of this constant."""

	def __init__(self, name, value: Union[int, "Constant", "BaseNode"], attributes: "dict[type_info.ConstAttribute, list[BaseNode]]", size=None, signed=False):
		self._value = value
		self.attributes = attributes if attributes else {}
		self.signed = signed
		super().__init__(name, size)

	@property
	def value(self):
		"""Returns the resolved value this constant holds."""
		return get_const_or_val(self._value)

	@value.setter
	def value(self, value):
		self._value = value

	def __str__(self) -> str:
		return f'{super().__str__()}, value={self.value}'

	def __repr__(self) -> str:
		return f'{super().__repr__()}, value={self.value}'

class RangeSpec:
	"""A class holding a range to denote a range of indices or width of a memory bank."""

	_upper_base: Union[int, "Constant", "BaseNode"]
	"""The upper bound of the range. Can be an int, a constant or a statically resolvable BaseNode."""
	_lower_base: Union[int, "Constant", "BaseNode"]
	"""The lower bound of the range. Can be an int, a constant or a statically resolvable BaseNode."""
	_upper_power: Union[int, "Constant", "BaseNode"]
	"""Obsolete, do not use"""
	_lower_power: Union[int, "Constant", "BaseNode"]
	"""Obsolete, do not use"""

	def __init__(self, upper_base: ValOrConst, lower_base: ValOrConst=None, upper_power: ValOrConst=1, lower_power: ValOrConst=1):
		self._upper_base = upper_base
		self._lower_base = lower_base

		self._upper_power = upper_power
		self._lower_power = lower_power

	@property
	def upper_power(self):
		"""Returns the resolved upper bound power."""
		return get_const_or_val(self._upper_power)

	@property
	def lower_power(self):
		"""Returns the resolved lower bound power."""
		return get_const_or_val(self._lower_power)

	@property
	def upper_base(self):
		"""Returns the resolved upper bound base."""
		return get_const_or_val(self._upper_base)

	@property
	def lower_base(self):
		"""Returns the resolved lower bound base."""
		return get_const_or_val(self._lower_base)

	@property
	def upper(self) -> Union[int, None]:
		"""Returns the resolved upper power."""
		if self.upper_base is None or self.upper_power is None:
			return None
		ret = self.upper_base ** self.upper_power
		if self.lower_base is None or self.lower_power is None:
			return ret - 1
		return ret

	@property
	def lower(self) -> int:
		"""Returns the resolved lower power."""
		if self.lower_base is None or self.lower_power is None:
			return 0
		return self.lower_base ** self.lower_power

	@property
	def length(self):
		"""Returns the length of the range using following algorithm:
		if self.upper is None: return None
		elif self.lower is None: return self.upper
		else return self.upper - self.lower + 1
		"""

		if self.upper is None:
			return None

		if self.lower is None:
			return self.upper

		return self.upper - self.lower + 1

	def __str__(self) -> str:
		return f'<RangeSpec object>, len {self.length}: {self.upper_base}:{self.lower_base}'


class FnParam(Named):
	"""A function parameter."""

	ty: type_info.IntegerType
	_width: Union[int, "Constant", "BaseNode"]
	"""The array width of this parameter."""

	def __init__(self, name, size, kind: type_info.TypeKind, width=1):
		self.ty = type_info.IntegerType(size, kind)
		self._width = width
		super().__init__(name)

	@property
	def width(self):
		"""Returns the resolved array width value."""

		return get_const_or_val(self._width)

	def __str__(self) -> str:
		return f'{super().__str__()}, type={self.ty}'

class Scalar(Named):
	"""A scalar variable object, used mainly in behavior descriptions."""

	ty: Union[type_info.PrimitiveType]
	static: attribute_info.StaticAttribute
	value: int

	def __init__(self,
			name,
			kind : Union[type_info.TypeKind, type_info.IntegerType, type_info.FloatType],
			size : int,
			value: int, # Compile Time information
			static: attribute_info.StaticAttribute,
        	storage=None
			):
		self.ty = type_info.PrimitiveType(kind, size) if isinstance(kind, type_info.TypeKind) else kind

		self.static = static

		# optional: only for constants/literals
		self.value = value

        # optional: backend info (register, memory, etc.)
		self.storage = storage
		super().__init__(name)


class Array(Named):
	"""A variable object for an Array, used mainly in behavior descriptions."""

	ty: type_info.ArrayType
	static: attribute_info.StaticAttribute
	values: list[int]

	def __init__(self,
			name,
			kind : Union[type_info.TypeKind, type_info.IntegerType, type_info.FloatType],
			size : int,
			length : int,
			values: list[int],
			static: attribute_info.StaticAttribute, # Compile Time information
        	storage=None
			):
		# Explcit casting for now allowed???
		self.ty = type_info.ArrayType(type_info.PrimitiveType(kind, size), length) if isinstance(kind, type_info.TypeKind) else kind

		self.static = static

		# optional: only for constants/literals
		self.values = values

        # optional: backend info (register, memory, etc.)
		self.storage = storage
		super().__init__(name)


class Intrinsic(Named):

	value: int
	ty: type_info.PrimitiveType

	def __init__(self, name, size: ValOrConst, kind: type_info.TypeKind, value: int = None):
		self.ty = type_info.PrimitiveType(kind, get_const_or_val(size))
		self.value = value
		super().__init__(name)

class Memory(Named):
	"""A generic memory object. Can have children, which alias to specific indices
	of their parent memory. Has a variable array size, can therefore represent both
	scalar and array registers and/or memories.
	"""

	ty : type_info.MemoryType
	range: RangeSpec
	attributes: "dict[attribute_info.MemoryAttribute, list[BaseNode]]"
	children: "list[Memory]"
	parent: Union['Memory', None]
	_initval: "dict[int, Union[int, Constant, BaseNode]]"

	def __init__(self, name, range_: RangeSpec, size, attributes: "dict[attribute_info.MemoryAttribute, list[BaseNode]]"):
		self.ty = type_info.MemoryType(size)
		self.attributes = attributes if attributes else {}
		self.range = range_
		self.children = []
		self.parent = None
		self._initval = {}
		super().__init__(name)

	def initval(self, idx=None):
		"""Return the initial value for the given index."""

		return get_const_or_val(self._initval[idx])

	@property
	def data_range(self):
		"""Returns a RangeSpec object with upper=range.upper-range.lower, lower=0."""

		if self.range.upper is None or self.range.lower is None:
			return None

		return RangeSpec(self.range.upper - self.range.lower, 0)

	@property
	def is_pc(self):
		"""Return true if this memory is tagged as being the program counter."""
		return attribute_info.MemoryAttribute.IS_PC in self.attributes

	@property
	def is_main_mem(self):
		"""Return true if this memory is tagged as being the main memory array."""
		return attribute_info.MemoryAttribute.IS_MAIN_MEM in self.attributes

@dataclasses.dataclass
class BitVal:
	"""A class representing a fixed bit sequence in an instruction encoding.
	Modeled as length and integral value.
	"""

	length: int
	value: int

class BitField(Named):
	"""A class representing an operand in an instruction encoding. Can be split
	into multiple parts, if the operand is split over two or more bit ranges.
	"""

	range: RangeSpec
	kind: type_info.TypeKind

	def __init__(self, name, _range: RangeSpec, kind: type_info.TypeKind):
		self.range = _range
		self.ty = type_info.BitFieldType(kind)
		if not kind:
			self.ty = type_info.BitFieldType(type_info.TypeKind.UINT)

		super().__init__(name)

	def __str__(self) -> str:
		return f'{super().__repr__()}, range={self.range}, data_type={self.kind}'

	def __repr__(self):
		return self.__str__()

class BitFieldDescr(Named):
	"""A class representing a full instruction operand. Has no information about
	the actual bits it is composed of, for that use BitField.
	"""
	def __init__(self, name, size: ValOrConst, kind: type_info.TypeKind):
		self.ty = type_info.IntegerType(get_const_or_val(size), kind)

		super().__init__(name)

class Instruction(SizedRefOrConst):
	"""A class representing an instruction."""

	attributes: "dict[InstrAttribute, list[BaseNode]]"
	encoding: "list[Union[BitField, BitVal]]"
	mnemonic: str
	assembly: str
	operation: Operation

	ext_name: str
	fields: "dict[str, BitFieldDescr]"
	scalars: "dict[str, Scalar]"
	throws: bool

	mask: int
	code: int

	def __init__(self, name, attributes: "dict[InstrAttribute, list[BaseNode]]", encoding: "list[Union[BitField, BitVal]]",
			mnemonic: str, assembly: str, operation: Operation, function_info: "FunctionInfo"):

		self.ext_name = ""
		self.attributes = attributes if attributes else {}
		self.encoding = encoding
		self.fields: "dict[str, BitFieldDescr]" = {}
		self.scalars = {}
		self.mnemonic = name.lower() if mnemonic is None else mnemonic
		self.assembly = assembly
		self.operation = operation if operation is not None else Operation([])
		self.throws = False
		self.function_info = function_info

		self.mask = 0
		self.code = 0

		super().__init__(name, 0)

		for e in reversed(self.encoding):
			if isinstance(e, BitField):
				self._size += e.range.length

				if e.name in self.fields:
					f = self.fields[e.name]
					if f.ty.kind != e.ty.kind:
						raise M2TypeError(f'non-matching datatypes for BitField {e.name} in instruction {name}')
					if e.range.upper + 1 > f.ty.size:
						f.ty.size = e.range.upper + 1
				else:
					f = BitFieldDescr(e.name, e.range.upper + 1, e.ty.kind)
					self.fields[e.name] = f
			else:
				self.mask |= (2**e.length - 1) << self._size
				self.code |= e.value << self._size

				self._size += e.length

	def __str__(self) -> str:
		code_and_mask = f'code={self.code:#0{self.size+2}x}, mask={self.mask:#0{self.size+2}x}'
		return f'{super().__str__()}, ext_name={self.ext_name}, {code_and_mask}'

class Function(Named):
	"""A class representing a function."""

	attributes: "dict[attribute_info.FunctionAttribute, list[BaseNode]]"
	ty: type_info.FunctionType
	args: "list[FnParam]"
	operation: "Operation"
	extern: bool

	ext_name: str
	scalars: "dict[str, Scalar]"
	throws: bool
	static: attribute_info.StaticAttribute

	def __init__(self, name, attributes: "dict[attribute_info.FunctionAttribute, list[BaseNode]]", return_len, kind: type_info.TypeKind, args: "list[FnParam]",
			operation: "Operation", extern: bool=False, function_info: "FunctionInfo"=None):

		self.ext_name = ""
		self.attributes = attributes if attributes else {}
		self.ty = type_info.FunctionType(return_len, kind)
		self.scalars = {}
		self.throws = False
		if args is None:
			args = []

		self.args: "dict[str, FnParam]" = {}

		self.function_info = function_info

		for idx, arg in enumerate(args):
			if arg.name is None:
				arg_name = f"anon_{idx}"
			else:
				arg_name = arg.name

			self.args[arg_name] = arg

		self.operation = operation if operation is not None else Operation([])
		self.static = attribute_info.StaticAttribute.NONE
		self.extern = extern

		super().__init__(name)

	def __str__(self) -> str:
		return f'{super().__str__()}, type={self.ty}'

def extract_memory_alias(memories: "list[Memory]"):
	"""Extract and separate parent and children memories from the given list
	of memory objects."""

	parents = {}
	aliases = {}
	for m in memories:
		for c in m.children:
			aliases[c.name] = c

		p, a = extract_memory_alias(m.children)

		parents.update(p)
		aliases.update(a)

		if m.parent is None:
			parents[m.name] = m

	return parents, aliases

class AlwaysBlock(Named):
	attributes: "dict[attribute_info.FunctionAttribute, list[BaseNode]]"
	operation: "Operation"

	def __init__(self, name: str, attributes, operation):
		self.attributes = attributes
		self.operation = operation

		super().__init__(name)

class InstructionSet(Named):
	"""A class representing an InstructionSet collection. Bundles constants, memories, functions
	and instructions under a common name.
	"""

	def __init__(self, name, extension: "list[str]", constants: "dict[str, Constant]", memories: "dict[str, Memory]",
			functions: "dict[str, Function]", instructions: "dict[tuple[int, int], Instruction]"):

		self.extension = extension
		self.constants = constants
		self.memories, self.memory_aliases = extract_memory_alias(memories.values())
		self.functions = functions
		self.instructions = instructions

		super().__init__(name)

class CoreDef(Named):
	"""A class representing an entire CPU core. Contains the collected attributes of multiple InstructionSets."""

	def __init__(self, name, contributing_types: "list[str]", template: str, constants: "dict[str, Constant]", memories: "dict[str, Memory]",
			memory_aliases: "dict[str, Memory]", functions: "dict[str, Function]", instructions: "dict[tuple[int, int], Instruction] | list[Instruction]",
			instr_classes: "set[int]", intrinsics: "dict[str, Intrinsic]"):

		self.contributing_types = contributing_types
		self.template = template
		self.constants = constants
		self.memories = memories
		self.memory_aliases = memory_aliases
		self.functions = functions
		self.instructions = instructions
		self.instr_classes = instr_classes
		self.main_reg_file = None
		self.float_reg_file = None
		self.vector_reg_file = None
		self.csr_reg_file = None
		self.main_memory = None
		self.pc_memory = None
		self.global_irq_en_memory = None
		self.global_irq_en_mask = None
		self.procno_memory = None
		self.irq_en_memory = None
		self.irq_pending_memory = None
		self.intrinsics = intrinsics

		self._instructions_by_ext = None
		self.functions_by_ext = defaultdict(dict)
		self._instructions_by_class = None

		for fn_name, fn_def in self.functions.items():
			self.functions_by_ext[fn_def.ext_name][fn_name] = fn_def

		for mem in itertools.chain(self.memories.values(), self.memory_aliases.values()):
			if attribute_info.MemoryAttribute.IS_MAIN_REG in mem.attributes:
				self.main_reg_file = mem
			elif attribute_info.MemoryAttribute.IS_FLOAT_REG in mem.attributes:
				self.float_reg_file = mem
			elif attribute_info.MemoryAttribute.IS_VECTOR_REG in mem.attributes:
				self.vector_reg_file = mem
			elif attribute_info.MemoryAttribute.IS_CSR_REG in mem.attributes or mem.name.upper() == "CSR":
				self.csr_reg_file = mem
			elif attribute_info.MemoryAttribute.IS_PC in mem.attributes:
				self.pc_memory = mem
			elif attribute_info.MemoryAttribute.IS_MAIN_MEM in mem.attributes:
				self.main_memory = mem
			elif attribute_info.MemoryAttribute.ETISS_IS_GLOBAL_IRQ_EN in mem.attributes:
				self.global_irq_en_memory = mem
			elif attribute_info.MemoryAttribute.ETISS_IS_PROCNO in mem.attributes:
				self.procno_memory = mem
			elif attribute_info.MemoryAttribute.ETISS_IS_IRQ_EN in mem.attributes:
				self.irq_en_memory = mem
			elif attribute_info.MemoryAttribute.ETISS_IS_IRQ_PENDING in mem.attributes:
				self.irq_pending_memory = mem

		super().__init__(name)

	@property
	def instructions_by_ext(self):
		if self._instructions_by_ext is not None:
			return self._instructions_by_ext
		assert isinstance(self.instructions, dict)
		self._instructions_by_ext = defaultdict(dict)
		for (code, mask), instr_def in self.instructions.items():
			self._instructions_by_ext[instr_def.ext_name][(code, mask)] = instr_def
		return self._instructions_by_ext

	@property
	def instructions_by_class(self):
		if self._instructions_by_class is not None:
			return self._instructions_by_class
		assert isinstance(self.instructions, dict)
		self._instructions_by_class = defaultdict(dict)
		for (code, mask), instr_def in self.instructions.items():
			self._instructions_by_class[instr_def.size][(code, mask)] = instr_def
		return self._instructions_by_class
