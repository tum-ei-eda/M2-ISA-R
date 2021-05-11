from collections import namedtuple
from enum import Enum, auto
from typing import Iterable, List, Mapping, Set, Tuple, Union


class Named:
	def __init__(self, name: str):
		self.name = name

	def __str__(self) -> str:
		return f'<{type(self).__name__} object>: name={self.name}'

	def __repr__(self) -> str:
		return f'<{type(self).__name__} object>: name={self.name}'

class Constant(Named):
	def __init__(self, name, value: int, attributes: Iterable[str]):
		self.value = value
		self.attributes = attributes if attributes else []
		super().__init__(name)

	def __str__(self) -> str:
		return f'{super().__str__()}, value={self.value}'

val_or_const = Union[int, Constant]

class SizedRefOrConst(Named):
	def __init__(self, name, size: val_or_const):
		self._size = size
		super().__init__(name)

	@property
	def size(self):
		if isinstance(self._size, Constant):
			return self._size.value
		else:
			return self._size

	@property
	def actual_size(self):
		if self.size is None: return None

		temp = 1 << (self.size - 1).bit_length()
		return temp if temp >= 8 else 8

	def __str__(self) -> str:
		return f'{super().__str__()}, size={self.size}, actual_size={self.actual_size}'


class RangeSpec:
	def __init__(self, upper_base: val_or_const, lower_base: val_or_const, upper_power: val_or_const=1, lower_power: val_or_const=1):
		self._upper_base = upper_base
		self._lower_base = lower_base

		self._upper_power = upper_power
		self._lower_power = lower_power

	@property
	def upper_power(self):
		if isinstance(self._upper_power, Constant):
			return self._upper_power.value
		return self._upper_power

	@property
	def lower_power(self):
		if isinstance(self._lower_power, Constant):
			return self._lower_power.value
		return self._lower_power

	@property
	def upper_base(self):
		if isinstance(self._upper_base, Constant):
			return self._upper_base.value
		return self._upper_base

	@property
	def lower_base(self):
		if isinstance(self._lower_base, Constant):
			return self._lower_base.value
		return self._lower_base

	@property
	def upper(self):
		if self.upper_base is None or self.upper_power is None: return None

		return self.upper_base ** self.upper_power

	@property
	def lower(self):
		if self.lower_base is None or self.lower_power is None: return None

		return self.lower_base ** self.lower_power

	@property
	def length(self):
		if self.upper is None or self.lower is None: return None
		return self.upper - self.lower + 1

	def __str__(self) -> str:
		return f'<RangeSpec object>, len {self.length}: {self.upper_base}:{self.lower_base}'

class MemoryAttribute(Enum):
	IS_PC = auto()
	IS_MAIN_MEM = auto()
	IS_MAIN_REG = auto()

class RegAttribute(Enum):
	IS_PC = auto()
	DELETE = auto()
	IS_MAIN_REG = auto()

class SpaceAttribute(Enum):
	IS_MAIN_MEM = auto()

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


class FnParam(SizedRefOrConst):
	def __init__(self, name, size, data_type: DataType):
		self.data_type = data_type
		super().__init__(name, size)

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

	def __init__(self, name, range: RangeSpec, size, attributes: List[Union[SpaceAttribute, MemoryAttribute, RegAttribute]]):
		self.attributes = attributes if attributes else []
		self.range = range
		self.children = []
		self.parent = None
		super().__init__(name, size)

	@property
	def data_range(self):
		if self.range.upper is None or self.range.lower is None: return None

		return RangeSpec(self.range.upper - self.range.lower, 0)

	@property
	def is_pc(self):
		return RegAttribute.IS_PC in self.attributes

	@property
	def is_main_mem(self):
		return SpaceAttribute.IS_MAIN_MEM in self.attributes

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

class BitFieldDescr(Named):
	def __init__(self, name, size: val_or_const, data_type: DataType):
		self.size = size
		self.data_type = data_type
		self.upper = 0

		super().__init__(name)

class Instruction(SizedRefOrConst):
	def __init__(self, name, attributes: Iterable[InstrAttribute], encoding: Iterable[Union[BitField, BitVal]], disass: str, operation: "Operation"):
		self.ext_name = ""
		self.attributes = attributes if attributes else []
		self.encoding = encoding
		self.fields = {}
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
					f.size += e.range.upper - e.range.lower + 1
				else:
					f = BitFieldDescr(e.name, e.range.upper - e.range.lower + 1, e.data_type)
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
		self.args = {arg.name: arg for arg in args}
		self.operation = operation if operation is not None else Operation([])
		self.static = False

		super().__init__(name, return_len)

	def __str__(self) -> str:
		return f'{super().__str__()}, data_type={self.data_type}'

class InstructionSet(Named):
	def __init__(self, name, extension: Iterable[str], constants: Mapping[str, Constant], address_spaces: Mapping[str, Memory], registers: Mapping[str, Memory], functions: Mapping[str, Function], instructions: Mapping[Tuple[int, int], Instruction]):
		self.extension = extension
		self.constants = constants
		self.address_spaces = address_spaces
		self.registers = registers
		self.functions = functions
		self.instructions = instructions

		super().__init__(name)

class CoreDef(Named):
	def __init__(self, name, contributing_types: Iterable[str], template: str, constants: Mapping[str, Constant], memories: Mapping[str, Memory], memory_aliases: Mapping[str, Memory], functions: Mapping[str, Function], instructions: Mapping[Tuple[int, int], Instruction], instr_classes: Set[int], main_reg_file: Memory):
		self.contributing_types = contributing_types
		self.template = template
		self.constants = constants
		self.memories = memories
		self.memory_aliases = memory_aliases
		self.functions = functions
		self.instructions = instructions
		self.instr_classes = instr_classes
		self.main_reg_file = main_reg_file

		super().__init__(name)

class BaseNode:
	def generate(self, context):
		raise NotImplementedError()

class Operator(BaseNode):
	def __init__(self, op: str):
		self.value = op

class Operation(BaseNode):
	def __init__(self, statements: List[BaseNode]) -> None:
		self.statements = statements

class BinaryOperation(BaseNode):
	def __init__(self, left: BaseNode, op: Operator, right: BaseNode):
		self.left = left
		self.op = op
		self.right = right

class NumberLiteral(BaseNode):
	def __init__(self, value):
		self.value = value

class Assignment(BaseNode):
	def __init__(self, target: BaseNode, expr: BaseNode):
		self.target = target
		self.expr = expr

class Conditional(BaseNode):
	def __init__(self, cond: BaseNode, then_stmts: List[BaseNode], else_stmts: List[BaseNode]):
		self.cond = cond
		self.then_stmts = then_stmts if then_stmts is not None else []
		self.else_stmts = else_stmts if else_stmts is not None else []

class ScalarDefinition(BaseNode):
	def __init__(self, scalar: Scalar):
		self.scalar = scalar

class Return(BaseNode):
	def __init__(self, expr: BaseNode):
		self.expr = expr

class UnaryOperation(BaseNode):
	def __init__(self, op: Operator, right: BaseNode):
		self.op = op
		self.right = right

class NamedReference(BaseNode):
	def __init__(self, reference):
		self.reference = reference

class IndexedReference(BaseNode):
	def __init__(self, reference, index):
		self.reference = reference
		self.index = index

class TypeConv(BaseNode):
	def __init__(self, data_type, size, expr: BaseNode):
		self.data_type = data_type
		self.size = size
		self.expr = expr

class FunctionCall(BaseNode):
	def __init__(self, ref_or_name: Union[str, Function], args: List[BaseNode]) -> None:
		self.ref_or_name = ref_or_name
		self.args = args if args is not None else []

class Group(BaseNode):
	def __init__(self, expr: BaseNode):
		self.expr = expr

