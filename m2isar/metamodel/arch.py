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
from .behav import BaseNode, IndexedReference, Operation, Literal

if TYPE_CHECKING:
	from .code_info import FunctionInfo
exprInterpretVisitor = ExprInterpreterVisitor()

def get_const_or_val(arg) -> int:
	if isinstance(arg, Parameter):
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

ValOrConst = Union[int, "Parameter"]

class SizedRefOrConst(Named):
	"""A simple base class for an object with a name and a size.
	Size can be either an int, a Parameter or a statically resolvable
	expression, expressed by a BaseNode.
	"""

	_size: Union[int, "Parameter", "BaseNode"]
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

class Parameter(SizedRefOrConst):
	"""An object holding a ("Parameter") Parameter value.
	Should have a value at some point, also holds attributes and signedness information.
	"""

	_value: Union[int, "Parameter", "BaseNode"]
	"""The value this object holds. Can be an int, another constant or a statically resolvable BaseNode."""

	attributes: "dict[attribute_info.ConstAttribute, list[BaseNode]]"
	"""A dictionary of attributes, mapping attribute type to a list of attribute arguments."""

	signed: bool
	"""The signedness of this constant."""

	def __init__(self, name, value: Union[int, "Parameter", "BaseNode"], attributes: "dict[attribute_info.ConstAttribute, list[BaseNode]]", size=None, signed=False):
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

	_upper_base: Union[int, "Parameter", "BaseNode"]
	"""The upper bound of the range. Can be an int, a constant or a statically resolvable BaseNode."""
	_lower_base: Union[int, "Parameter", "BaseNode"]
	"""The lower bound of the range. Can be an int, a constant or a statically resolvable BaseNode."""
	_upper_power: Union[int, "Parameter", "BaseNode"]
	"""Obsolete, do not use"""
	_lower_power: Union[int, "Parameter", "BaseNode"]
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

	ty: type_info.PrimitiveType
	_width: Union[int, "Parameter", "BaseNode"]
	"""The array width of this parameter."""

	def __init__(self, name, size, kind: type_info.TypeKind, width=1):
		self.ty = type_info.PrimitiveType(kind, size)
		self._width = width
		super().__init__(name)

	@property
	def width(self):
		"""Returns the resolved array width value."""

		return get_const_or_val(self._width)

	def __str__(self) -> str:
		return f'{super().__str__()}, type={self.ty}'

# ===========================================================
# START
# ARCHITECTURE used within the functional
# behavior of instructions and functions.
# ===========================================================
class Symbol(Named):
    """A simple base class for a symbol, which is a named object that
	can be used as an operand in an instruction or function."""
    def __init__(
        self,
        name: str,
        ty: Union[type_info.PrimitiveType, type_info.FloatType, type_info.ArrayType, type_info.BitFieldType, type_info.PointerType],
        attributes : dict = {}
    ):
        self.ty = ty
        self.attributes = attributes
        super().__init__(name)


class Variable(Symbol):
    """A variable is only defined in the functional behavior of a function, but not in the architectural part.
	Archtiectural Parts are depicted as Register Banks or Memories, but not as variables.
	However, we need to define variables for intermediate results, ..."""
    def __init__(
        self,
        name: str,
        ty: Union[type_info.PrimitiveType, type_info.FloatType, type_info.ArrayType],
		attributes: dict = {"static": attribute_info.AccessAttribute.RW},
		value=None, # Compile Time information
		children=[] # Array support might require this
    ):
        assert isinstance(ty, (type_info.PrimitiveType, type_info.ArrayType))

        if isinstance(ty, type_info.PrimitiveType):
            assert ty.kind.is_scalar
        elif isinstance(ty, type_info.ArrayType):
			# only allow 1D arrays for now
            assert ty.element_type.kind.is_scalar

        # optional: only for parameters/literals
        self.value = value
        self.children = children
        assert (len(self.children) == 0 or isinstance(ty, type_info.ArrayType))

        super().__init__(name, ty, attributes)

class Intrinsic(Symbol):

	value: int

	def __init__(self, name, size: ValOrConst, kind: type_info.TypeKind, value: int = None):
		self.value = value
		super().__init__(name, type_info.PrimitiveType(kind, get_const_or_val(size)))


class RegisterBank(Symbol):
	"""A class representing a register bank. A register bank combines structured registers,
	which is used to represent registers in the architectural part of an M2-ISA-R model."""
	children: "list[Memory]"
	_initval: "dict[int, Union[int, Parameter, BaseNode]]"

	def __init__(self, name, nr_ele: Union[int, Parameter], kind: type_info.TypeKind, size, attributes: "dict[attribute_info.MemoryAttribute, list[BaseNode]]"):
		self.children = []
		self._initval = {}
		ty = type_info.ArrayType(type_info.PrimitiveType(kind, size), nr_ele)

		super().__init__(name, ty, attributes)

	# TODO: Implement this
	def initval(self, idx=None):
		"""Return the initial value for the given index."""
		return get_const_or_val(self._initval[idx])


	@property
	def is_main_reg(self):
		"""Return true if this memory is tagged as being a general-purpose register."""
		return self._is_specific_register(attribute_info.RegisterAttribute.IS_MAIN_REG, "X")

	@property
	def is_float_reg(self) -> bool:
		"""Return true if this memory is tagged as being a float register array or named F."""
		return self._is_specific_register(attribute_info.RegisterAttribute.IS_FLOAT_REG, "F")

	@property
	def is_vector_reg(self) -> bool:
		"""Return true if this memory is tagged as being a vector register array or named V."""
		return self._is_specific_register(attribute_info.RegisterAttribute.IS_VECTOR_REG, "V")


	def _is_specific_register(self, register_type: attribute_info.RegisterAttribute, expected_name: str = "") -> bool:
		"""
		This is a helper function to ensure, that all checks are performed always the same.
		:param register_type: The register attribute qualifying for this check
		:param expected_name: The fixed name for this specific type of register
		:return: True if the register matches the constraints, False otherwise
		"""
		return register_type in self.attributes or expected_name.upper() == self.name.upper()




# be careful: This is only for single defined regs (No Alias or indexedReference)
class Register(Symbol):
	"""A class representing a register. A register is a single defined Symbols. Dont mix it up
	bit alias that are IndexedReference of already declared Symbols.
	This class should simplify different handling to register bank.
	And is used to represent registers in the architectural part of an M2-ISA-R model."""
	children: "list[Memory]"
	_initval: "dict[Union[int, Parameter, BaseNode]]"

	def __init__(self, name, kind: type_info.TypeKind, size, attributes: "dict[attribute_info.RegisterAttribute, list[BaseNode]]"):
		self.children = []
		self._initval = {}
		ty = type_info.PrimitiveType(kind, size)

		super().__init__(name, ty, attributes)

	# TODO: Implement this
	def initval(self):
		"""Return the initial value for the given index."""

		return get_const_or_val(self._initval)

	@property
	def is_pc(self):
		"""Return true if this memory is tagged as being the program counter."""
		return self._is_specific_register(attribute_info.RegisterAttribute.IS_PC)


	def _is_specific_register(self, register_type: attribute_info.RegisterAttribute, expected_name: str = "") -> bool:
		"""
		This is a helper function to ensure, that all checks are performed always the same.
		:param register_type: The register attribute qualifying for this check
		:param expected_name: The fixed name for this specific type of memory
		:return: True if the memory matches the constraints, False otherwise
		"""
		return register_type in self.attributes or expected_name.upper() == self.name.upper()



#Idea extern [const volatile]<- atleast store it
#class Port -> raise ...


class Memory(Symbol):
	"""A generic memory object. Can have children, which alias to specific indices
	of their parent memory. Has a variable array size, can therefore represent both
	scalar and array registers and/or memories.
	"""

	range: RangeSpec
	children: "list[Memory]"
	parent: "Union['Memory', None]"
	_initval: "dict[int, Union[int, Parameter, BaseNode]]"

	def __init__(self, name, kind : type_info.TypeKind, size, length, attributes: "dict[attribute_info.MemoryAttribute, list[BaseNode]]"):
		self.children = []
		self._initval = {}
		self.parent = None # Just Legacy
		assert kind.is_numeric
		super().__init__(name, type_info.ArrayType(type_info.PrimitiveType(kind, size), length), attributes)


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
	def is_csr_reg(self) -> bool:
		"""Return true if this memory is tagged as being a csr register array or named CSR."""
		return self._is_specific_memory(attribute_info.MemoryAttribute.IS_CSR_REG, "CSR")


	@property
	def is_main_mem(self):
		"""Return true if this memory is tagged as being the main memory array."""
		return self._is_specific_memory(attribute_info.MemoryAttribute.IS_MAIN_MEM)


	def _is_specific_memory(self, memory_type: attribute_info.MemoryAttribute, expected_name: str = "") -> bool:
		"""
		This is a helper function to ensure, that all checks are performed always the same.
		:param memory_type: The memory attribute qualifying for this check
		:param expected_name: The fixed name for this specific type of memory
		:return: True if the memory matches the constraints, False otherwise
		"""
		return memory_type in self.attributes or expected_name.upper() == self.name.upper()





# TODO: decide later if you wanna keep lhs information :
# unsigned<XLEN>& S0 = X[8]; vs
# Intention: alias S0 <- X[8];
class Alias(Symbol):
    """A class representing an (potentially ranged) alias to a Register/Memory/RegisterBank entity,
	which refer to the architectural part of an M2-ISA-R model. This access might be ranged"""
    parent: Union[Memory, RegisterBank]
    _initval = 0

    def __init__(self, name, parent: Union[Memory, RegisterBank], range: RangeSpec, type: type_info.PointerType, attributes: dict = {}):
        self.parent = parent
        self.range = range
        self.ty = type
        assert isinstance(parent.ty, (type_info.ArrayType, type_info.PrimitiveType))
        super().__init__(name, type, attributes)


    @property
    def data_range(self):
        """Returns a RangeSpec object with upper=range.upper-range.lower, lower=0."""

        if self.range.upper is None or self.range.lower is None:
            return None

        return RangeSpec(self.range.upper - self.range.lower, 0)

    @property
    def length(self):
        """Returns the length of the range using following algorithm:
		if self.upper is None: return None
		elif self.lower is None: return self.upper
		else return self.upper - self.lower + 1
		"""

        if self.range.upper is None:
            return None

        if self.range.lower is None:
            return self.range.upper

        return self.range.upper - self.range.lower + 1

# ============================================================
# END
# ARCHITECTURE used within the functional
# behavior of instructions and functions.
# ===========================================================


class BitField(Symbol):
	"""A class representing an operand in an instruction encoding. Can be split
	into multiple parts, if the operand is split over two or more bit ranges.
	"""

	range: RangeSpec
	kind: type_info.TypeKind

	def __init__(self, name, _range: RangeSpec, kind: type_info.TypeKind):
		self.range = _range
		if not kind:
			self.ty = type_info.BitFieldType(type_info.TypeKind.UINT)

		super().__init__(name, type_info.BitFieldType(kind), attributes={})

	def __str__(self) -> str:
		return f'{super().__repr__()}, range={self.range}, data_type={self.kind}'

	def __repr__(self):
		return self.__str__()




@dataclasses.dataclass
class BitVal:
	"""A class representing a fixed bit sequence in an instruction encoding.
	Modeled as length and integral value.
	"""

	length: int
	value: int

class BitFieldDescr(Named):
	"""A class representing a full instruction operand. Has no information about
	the actual bits it is composed of, for that use BitField.
	"""
	def __init__(self, name, size: ValOrConst, kind: type_info.TypeKind):
		self.ty = type_info.PrimitiveType(kind, get_const_or_val(size))

		super().__init__(name)

class Instruction(SizedRefOrConst):
	"""A class representing an instruction."""

	attributes: "dict[attribute_info.InstrAttribute, list[BaseNode]]"
	encoding: "list[Union[BitField, BitVal]]"
	mnemonic: str
	assembly: str
	operation: Operation

	ext_name: str
	fields: "dict[str, BitFieldDescr]"
	vars: "dict[str, Symbol]"
	throws: bool

	mask: int
	code: int

	def __init__(self, name, attributes: "dict[attribute_info.InstrAttribute, list[BaseNode]]", encoding: "list[Union[BitField, BitVal]]",
			mnemonic: str, assembly: str, operation: Operation, function_info: "FunctionInfo"):

		self.ext_name = ""
		self.attributes = attributes if attributes else {}
		self.encoding = encoding
		self.fields: "dict[str, BitFieldDescr]" = {}
		self.vars = {}
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
	vars: "dict[str, Symbol]"
	throws: bool
	static: attribute_info.AccessAttribute

	def __init__(self, name, attributes: "dict[attribute_info.FunctionAttribute, list[BaseNode]]", return_len, kind: type_info.TypeKind, args: "list[FnParam]",
			operation: "Operation", extern: bool=False, function_info: "FunctionInfo"=None):

		self.ext_name = ""
		self.attributes = attributes if attributes else {}
		self.ty = type_info.FunctionType(return_len, kind)
		self.vars = {}
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
		self.static = attribute_info.AccessAttribute.NONE
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


def extract_register_alias(register_banks: "list[RegisterBank]"):
	"""Extract and separate parent and children register banks from the given list
	of register bank objects."""

	parents = {}
	aliases = {}
	for m in register_banks:
		for c in m.children:
			aliases[c.name] = c
			parents[c.name] = m

	return parents, aliases


class AlwaysBlock(Named):
	attributes: "dict[attribute_info.FunctionAttribute, list[BaseNode]]"
	operation: "Operation"

	def __init__(self, name: str, attributes, operation):
		self.attributes = attributes
		self.operation = operation

		super().__init__(name)

class InstructionSet(Named):
	"""A class representing an InstructionSet collection. Bundles parameters, memories, functions
	and instructions under a common name.
	"""

	def __init__(self, name, extension: "list[str]", parameters: "dict[str, Parameter]", memories: "dict[str, Memory]",
			register_banks: "dict[str, RegisterBank]", functions: "dict[str, Function]", instructions: "dict[tuple[int, int], Instruction]"):

		self.extension = extension
		self.combines = []
		self.parameters = parameters
		self.memories, self.memory_aliases = extract_memory_alias(memories.values())
		self.register_banks, self.register_aliases = extract_register_alias(register_banks.values())
		self.functions = functions
		self.instructions = instructions

		super().__init__(name)

class InstructionSetGroup(InstructionSet):
	"""A group of InstructionSet instances."""

	def __init__(self, name, combines: "list[str]"):
		super().__init__(name, [], {}, {}, {}, {})
		self.combines = combines

class CoreDef(Named):
	"""A class representing an entire CPU core. Contains the collected attributes of multiple InstructionSets."""

	def __init__(self, name, contributing_types: "list[str]", template: str, parameters: "dict[str, Parameter]", memories: "dict[str, Memory]",
			memory_aliases: "dict[str, Alias]", register_banks: "dict[str, Union[RegisterBank, Register]]", register_aliases: "dict[str, Alias]",
			functions: "dict[str, Function]", instructions: "dict[tuple[int, int], Instruction] | list[Instruction]", instr_classes: "set[int]",
			intrinsics: "dict[str, Intrinsic]"):

		self.contributing_types = contributing_types
		self.template = template
		self.parameters = parameters
		self.memories = memories
		self.memory_aliases = memory_aliases
		self.register_banks = register_banks
		self.register_aliases = register_aliases
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
			if isinstance(mem, (Memory)):
				if mem.is_main_mem:
					self.main_memory = mem
				elif mem.is_csr_reg:
					self.csr_reg_file = mem
				elif attribute_info.MemoryAttribute.ETISS_IS_GLOBAL_IRQ_EN in mem.attributes:
					self.global_irq_en_memory = mem
				elif attribute_info.MemoryAttribute.ETISS_IS_PROCNO in mem.attributes:
					self.procno_memory = mem
				elif attribute_info.MemoryAttribute.ETISS_IS_IRQ_EN in mem.attributes:
					self.irq_en_memory = mem
				elif attribute_info.MemoryAttribute.ETISS_IS_IRQ_PENDING in mem.attributes:
					self.irq_pending_memory = mem


		for regs in itertools.chain(self.register_banks.values(), self.register_aliases.values()):
			if isinstance(regs, RegisterBank):
				if regs.is_main_reg:
					self.main_reg_file = regs
				if regs.is_float_reg:
					self.float_reg_file = regs
				if regs.is_vector_reg:
					self.vector_reg_file = regs
			elif isinstance(regs, Register):
				if regs.is_pc:
					self.pc_memory = regs


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