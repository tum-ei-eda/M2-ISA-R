import itertools
from collections import namedtuple
from enum import Enum, auto
from typing import Dict, Iterable, List, Mapping, Set, Tuple, Union

from .behav import BaseNode, Operation


def get_const_or_val(arg):
	if isinstance(arg, Constant):
		return arg.value
	elif isinstance(arg, BaseNode):
		return arg.generate(None)
	return arg

class Named:
	def __init__(self, name: str):
		self.name = name

	def __str__(self) -> str:
		return f'<{type(self).__name__} object>: name={self.name}'

	def __repr__(self) -> str:
		return f'<{type(self).__name__} object>: name={self.name}'

class Constant(Named):
	def __init__(self, name, value: int, attributes: Iterable[str]):
		self._value = value
		self.attributes = attributes if attributes else []
		super().__init__(name)

	@property
	def value(self):
		return get_const_or_val(self._value)

	@value.setter
	def value(self, value):
		self._value = value

	def __str__(self) -> str:
		return f'{super().__str__()}, value={self.value}'

val_or_const = Union[int, Constant]

class SizedRefOrConst(Named):
	def __init__(self, name, size: val_or_const):
		self._size = size
		super().__init__(name)

	@property
	def size(self):
		return get_const_or_val(self._size)

	@property
	def actual_size(self):
		if self.size is None:
			return None

		temp = 1 << (self.size - 1).bit_length()
		return temp if temp >= 8 else 8

	def __str__(self) -> str:
		return f'{super().__str__()}, size={self.size}, actual_size={self.actual_size}'


class RangeSpec:
	def __init__(self, upper_base: val_or_const, lower_base: val_or_const=None, upper_power: val_or_const=1, lower_power: val_or_const=1):
		self._upper_base = upper_base
		self._lower_base = lower_base

		self._upper_power = upper_power
		self._lower_power = lower_power

	@property
	def upper_power(self):
		return get_const_or_val(self._upper_power)

	@property
	def lower_power(self):
		return get_const_or_val(self._lower_power)

	@property
	def upper_base(self):
		return get_const_or_val(self._upper_base)

	@property
	def lower_base(self):
		return get_const_or_val(self._lower_base)

	@property
	def upper(self):
		if self.upper_base is None or self.upper_power is None:
			return None
		ret = self.upper_base ** self.upper_power
		if self.lower_base is None or self.lower_power is None:
			return ret - 1
		return ret

	@property
	def lower(self):
		if self.lower_base is None or self.lower_power is None:
			return 0
		return self.lower_base ** self.lower_power

	@property
	def length(self):
		if self.upper is None:
			return None
		elif self.lower is None:
			return self.upper
		return self.upper - self.lower + 1

	def __str__(self) -> str:
		return f'<RangeSpec object>, len {self.length}: {self.upper_base}:{self.lower_base}'

class MemoryAttribute(Enum):
	IS_PC = auto()
	IS_MAIN_MEM = auto()
	IS_MAIN_REG = auto()
	DELETE = auto()

class ConstAttribute(Enum):
	IS_REG_WIDTH = auto()
	IS_ADDR_WIDTH = auto()

class InstrAttribute(Enum):
	NO_CONT = auto()
	COND = auto()
	FLUSH = auto()
	SIM_EXIT = auto()

class DataType(Enum):
	NONE = auto()
	U = auto()
	S = auto()
	F = auto()
	D = auto()
	Q = auto()
	B = auto()

class DataType2:
	def __init__(self, ptr) -> None:
		self.ptr = ptr

class VoidType(DataType2):
	def __init__(self, ptr) -> None:
		super().__init__(ptr)

class IntegerType(DataType2):
	def __init__(self, width: int, signed: bool, ptr):
		self._width = width
		self.signed = signed

		super().__init__(ptr)

	@property
	def width(self):
		return get_const_or_val(self._width)

	@property
	def actual_width(self):
		if self._width is None:
			return None

		temp = 1 << (self.width - 1).bit_length()
		return temp if temp >= 8 else 8

class FnParam(SizedRefOrConst):
	def __init__(self, name, size, data_type: DataType, width=1):
		self.data_type = data_type
		self._width = width
		super().__init__(name, size)

	@property
	def width(self):
		return get_const_or_val(self._width)

	def __str__(self) -> str:
		return f'{super().__str__()}, data_type={self.data_type}'

class Scalar(SizedRefOrConst):
	def __init__(self, name, value: int, static: bool, size, data_type: DataType):
		self.value = value
		self.static = static
		self.data_type = data_type
		super().__init__(name, size)

class Memory(SizedRefOrConst):
	children: List['Memory']
	parent: Union['Memory', None]

	def __init__(self, name, range: RangeSpec, size, attributes: List[Union[MemoryAttribute, MemoryAttribute, MemoryAttribute]]):
		self.attributes = attributes if attributes else []
		self.range = range
		self.children = []
		self.parent = None
		self._initval = {}
		super().__init__(name, size)

	def initval(self, idx=None):
		return get_const_or_val(self._initval[idx])

	@property
	def data_range(self):
		if self.range.upper is None or self.range.lower is None: return None

		return RangeSpec(self.range.upper - self.range.lower, 0)

	@property
	def is_pc(self):
		return MemoryAttribute.IS_PC in self.attributes

	@property
	def is_main_mem(self):
		return MemoryAttribute.IS_MAIN_MEM in self.attributes

	def __str__(self) -> str:
		return f'{super().__str__()}, size={self.size}'

BitVal = namedtuple('BitVal', ['length', 'value'])

class BitField(Named):
	def __init__(self, name, _range: RangeSpec, data_type: DataType):
		self.range = _range
		self.data_type = data_type
		if not self.data_type: self.data_type = DataType.U

		super().__init__(name)

	def __str__(self) -> str:
		return f'{super().__repr__()}, range={self.range}, data_type={self.data_type}'

	def __repr__(self):
		return self.__str__()

class BitFieldDescr(SizedRefOrConst):
	def __init__(self, name, size: val_or_const, data_type: DataType):
		self.data_type = data_type

		super().__init__(name, size)

class Instruction(SizedRefOrConst):
	def __init__(self, name, attributes: Iterable[InstrAttribute], encoding: Iterable[Union[BitField, BitVal]], disass: str, operation: Operation):
		self.ext_name = ""
		self.attributes = attributes if attributes else []
		self.encoding = encoding
		self.fields: Mapping[str, BitFieldDescr] = {}
		self.scalars = {}
		self.disass = disass
		self.operation = operation if operation is not None else Operation([])

		self.mask = 0
		self.code = 0

		super().__init__(name, 0)

		for e in reversed(self.encoding):
			if isinstance(e, BitField):
				self._size += e.range.length

				if e.name in self.fields:
					f = self.fields[e.name]
					if f.data_type != e.data_type:
						raise ValueError(f'non-matching datatypes for BitField {e.name} in instruction {name}')
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
	def __init__(self, name, return_len, data_type: DataType, args: Iterable[FnParam], operation: "Operation"):
		self.data_type = data_type
		if args is None:
			args = []

		self.args: Dict[str, FnParam] = {}

		for idx, arg in enumerate(args):
			if arg.name is None:
				arg_name = f"anon_{idx}"
			else:
				arg_name = arg.name

			self.args[arg_name] = arg

		self.operation = operation if operation is not None else Operation([])
		self.static = False

		super().__init__(name, return_len)

	def __str__(self) -> str:
		return f'{super().__str__()}, data_type={self.data_type}'

def extract_memory_alias(memories: Iterable[Memory]):
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

class InstructionSet(Named):
	def __init__(self, name, extension: Iterable[str], constants: Mapping[str, Constant], memories: Mapping[str, Memory], functions: Mapping[str, Function], instructions: Mapping[Tuple[int, int], Instruction]):
		self.extension = extension
		self.constants = constants
		self.memories, self.memory_aliases = extract_memory_alias(memories.values())
		self.functions = functions
		self.instructions = instructions

		super().__init__(name)

class CoreDef(Named):
	def __init__(self, name, contributing_types: Iterable[str], template: str, constants: Mapping[str, Constant], memories: Mapping[str, Memory], memory_aliases: Mapping[str, Memory], functions: Mapping[str, Function], instructions: Mapping[Tuple[int, int], Instruction], instr_classes: Set[int]):
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

		for mem in itertools.chain(self.memories.values(), self.memory_aliases.values()):
			if MemoryAttribute.IS_MAIN_REG in mem.attributes:
				self.main_reg_file = mem
			elif MemoryAttribute.IS_PC in mem.attributes:
				self.pc_memory = mem
			elif MemoryAttribute.IS_MAIN_MEM in mem.attributes:
				self.main_memory = mem

		super().__init__(name)



