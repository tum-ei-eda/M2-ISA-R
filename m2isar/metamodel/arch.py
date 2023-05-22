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
from enum import Enum, IntEnum, auto
from typing import TYPE_CHECKING, Any, Union

from .. import M2TypeError
from .behav import BaseNode, Operation

if TYPE_CHECKING:
	from .code_info import FunctionInfo


def get_const_or_val(arg) -> int:
	if isinstance(arg, Constant):
		return arg.value

	if isinstance(arg, BaseNode):
		return arg.generate(None)

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

		return get_const_or_val(self._size)

	@property
	def actual_size(self):
		"""Returns the bits needed in multiples of eight to represent the
		resolved size of the object.
		"""

		if self.size is None:
			return None

		temp = 1 << (self.size - 1).bit_length()
		return temp if temp >= 8 else 8

	def __str__(self) -> str:
		return f'{super().__str__()}, size={self.size}, actual_size={self.actual_size}'

class Constant(SizedRefOrConst):
	"""An object holding a constant value. Should have a value at some point, also holds attributes
	and signedness information.
	"""

	_value: Union[int, "Constant", "BaseNode"]
	"""The value this object holds. Can be an int, another constant or a statically resolvable BaseNode."""

	attributes: "dict[ConstAttribute, list[BaseNode]]"
	"""A dictionary of attributes, mapping attribute type to a list of attribute arguments."""

	signed: bool
	"""The signedness of this constant."""

	def __init__(self, name, value: Union[int, "Constant", "BaseNode"], attributes: "dict[ConstAttribute, list[BaseNode]]", size=None, signed=False):
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

class MemoryAttribute(Enum):
	IS_PC = auto()
	IS_MAIN_MEM = auto()
	IS_MAIN_REG = auto()
	DELETE = auto()
	ETISS_CAN_FAIL = auto()
	ETISS_IS_GLOBAL_IRQ_EN = auto()
	ETISS_IS_IRQ_EN = auto()
	ETISS_IS_IRQ_PENDING = auto()
	ETISS_IS_PROCNO = auto()

class ConstAttribute(Enum):
	IS_REG_WIDTH = auto()
	IS_ADDR_WIDTH = auto()

class InstrAttribute(Enum):
	NO_CONT = auto()
	COND = auto()
	FLUSH = auto()
	SIM_EXIT = auto()
	ENABLE = auto()
	ETISS_ERROR_INSTRUCTION = auto()

class FunctionAttribute(Enum):
	ETISS_STATICFN = auto()
	ETISS_NEEDS_ARCH = auto()
	ETISS_TRAP_ENTRY_FN = auto()
	ETISS_TRAP_TRANSLATE_FN = auto()

class FunctionThrows(IntEnum):
	NO = 0
	YES = 1
	MAYBE = 2

class DataType(Enum):
	NONE = auto()
	U = auto()
	S = auto()
	F = auto()
	D = auto()
	Q = auto()
	B = auto()

class DataType2:
	"""A datatype base class, only holds information on whether it is a pointer."""

	ptr: Any

	def __init__(self, ptr) -> None:
		self.ptr = ptr

class VoidType(DataType2):
	"""A void datatype, automatically assumes native size."""

class IntegerType(DataType2):
	"""An integer datatype with width and sign information."""

	_width: Union[int, "Constant", "BaseNode"]
	signed: bool

	def __init__(self, width: Union[int, "Constant", "BaseNode"], signed: bool, ptr):
		self._width = width
		self.signed = signed

		super().__init__(ptr)

	@property
	def width(self):
		"""Returns the resolved width value."""

		return get_const_or_val(self._width)

	@property
	def actual_width(self):
		"""Returns the resolved width value rounded to the nearest multiple of 8."""

		if self._width is None:
			return None

		temp = 1 << (self.width - 1).bit_length()
		return temp if temp >= 8 else 8

class FnParam(SizedRefOrConst):
	"""A function parameter."""

	data_type: DataType
	_width: Union[int, "Constant", "BaseNode"]
	"""The array width of this parameter."""

	def __init__(self, name, size, data_type: DataType, width=1):
		self.data_type = data_type
		self._width = width
		super().__init__(name, size)

	@property
	def width(self):
		"""Returns the resolved array width value."""

		return get_const_or_val(self._width)

	def __str__(self) -> str:
		return f'{super().__str__()}, data_type={self.data_type}'

class Scalar(SizedRefOrConst):
	"""A scalar variable object, used mainly in behavior descriptions."""

	value: int
	static: bool
	data_type: DataType

	def __init__(self, name, value: int, static: bool, size, data_type: DataType):
		self.value = value
		self.static = static
		self.data_type = data_type
		super().__init__(name, size)

class Intrinsic(SizedRefOrConst):

	value: int
	data_type: DataType

	def __init__(self, name, size: ValOrConst, data_type: DataType, value: int = None):
		self.data_type = data_type
		self.value = value
		super().__init__(name, size)

class Memory(SizedRefOrConst):
	"""A generic memory object. Can have children, which alias to specific indices
	of their parent memory. Has a variable array size, can therefore represent both
	scalar and array registers and/or memories.
	"""

	attributes: "dict[MemoryAttribute, list[BaseNode]]"
	range: RangeSpec
	children: "list[Memory]"
	parent: Union['Memory', None]
	_initval: "dict[int, Union[int, Constant, BaseNode]]"

	def __init__(self, name, range_: RangeSpec, size, attributes: "dict[MemoryAttribute, list[BaseNode]]"):
		self.attributes = attributes if attributes else {}
		self.range = range_
		self.children = []
		self.parent = None
		self._initval = {}
		super().__init__(name, size)

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
		return MemoryAttribute.IS_PC in self.attributes

	@property
	def is_main_mem(self):
		"""Return true if this memory is tagged as being the main memory array."""
		return MemoryAttribute.IS_MAIN_MEM in self.attributes

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
	data_type: DataType

	def __init__(self, name, _range: RangeSpec, data_type: DataType):
		self.range = _range
		self.data_type = data_type
		if not self.data_type:
			self.data_type = DataType.U

		super().__init__(name)

	def __str__(self) -> str:
		return f'{super().__repr__()}, range={self.range}, data_type={self.data_type}'

	def __repr__(self):
		return self.__str__()

class BitFieldDescr(SizedRefOrConst):
	"""A class representing a full instruction operand. Has no information about
	the actual bits it is composed of, for that use BitField.
	"""

	def __init__(self, name, size: ValOrConst, data_type: DataType):
		self.data_type = data_type

		super().__init__(name, size)

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
					if f.data_type != e.data_type:
						raise M2TypeError(f'non-matching datatypes for BitField {e.name} in instruction {name}')
					if e.range.upper + 1 > f._size:
						f._size = e.range.upper + 1
				else:
					f = BitFieldDescr(e.name, e.range.upper + 1, e.data_type)
					self.fields[e.name] = f
			else:
				self.mask |= (2**e.length - 1) << self._size
				self.code |= e.value << self._size

				self._size += e.length

	def __str__(self) -> str:
		code_and_mask = f'code={self.code:#0{self.size+2}x}, mask={self.mask:#0{self.size+2}x}'
		return f'{super().__str__()}, ext_name={self.ext_name}, {code_and_mask}'

class Function(SizedRefOrConst):
	"""A class representing a function."""

	attributes: "dict[FunctionAttribute, list[BaseNode]]"
	data_type: DataType
	args: "list[FnParam]"
	operation: "Operation"
	extern: bool

	ext_name: str
	scalars: "dict[str, Scalar]"
	throws: bool
	static: bool

	def __init__(self, name, attributes: "dict[FunctionAttribute, list[BaseNode]]", return_len, data_type: DataType, args: "list[FnParam]",
			operation: "Operation", extern: bool=False, function_info: "FunctionInfo"=None):

		self.ext_name = ""
		self.data_type = data_type
		self.attributes = attributes if attributes else {}
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
		self.static = False
		self.extern = extern

		super().__init__(name, return_len)

	def __str__(self) -> str:
		return f'{super().__str__()}, data_type={self.data_type}'

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
	attributes: "dict[FunctionAttribute, list[BaseNode]]"
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
			memory_aliases: "dict[str, Memory]", functions: "dict[str, Function]", instructions: "dict[tuple[int, int], Instruction]",
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
		self.main_memory = None
		self.pc_memory = None
		self.global_irq_en_memory = None
		self.global_irq_en_mask = None
		self.procno_memory = None
		self.irq_en_memory = None
		self.irq_pending_memory = None
		self.intrinsics = intrinsics

		self.instructions_by_ext = defaultdict(dict)
		self.functions_by_ext = defaultdict(dict)
		self.instructions_by_class = defaultdict(dict)

		for (code, mask), instr_def in self.instructions.items():
			self.instructions_by_ext[instr_def.ext_name][(code, mask)] = instr_def
			self.instructions_by_class[instr_def.size][(code, mask)] = instr_def

		for fn_name, fn_def in self.functions.items():
			self.functions_by_ext[fn_def.ext_name][fn_name] = fn_def

		for mem in itertools.chain(self.memories.values(), self.memory_aliases.values()):
			if MemoryAttribute.IS_MAIN_REG in mem.attributes:
				self.main_reg_file = mem
			elif MemoryAttribute.IS_PC in mem.attributes:
				self.pc_memory = mem
			elif MemoryAttribute.IS_MAIN_MEM in mem.attributes:
				self.main_memory = mem
			elif MemoryAttribute.ETISS_IS_GLOBAL_IRQ_EN in mem.attributes:
				self.global_irq_en_memory = mem
			elif MemoryAttribute.ETISS_IS_PROCNO in mem.attributes:
				self.procno_memory = mem
			elif MemoryAttribute.ETISS_IS_IRQ_EN in mem.attributes:
				self.irq_en_memory = mem
			elif MemoryAttribute.ETISS_IS_IRQ_PENDING in mem.attributes:
				self.irq_pending_memory = mem

		super().__init__(name)
