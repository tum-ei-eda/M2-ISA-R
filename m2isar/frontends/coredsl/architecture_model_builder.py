import logging
from typing import Union

from lark import Discard, Transformer, Tree

from ... import M2DuplicateError, M2NameError
from ...metamodel import arch

logger = logging.getLogger("architecture")

class ArchitectureModelBuilder(Transformer):
	"""Builds the architecture model of a Core from a lark parse tree"""

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

	def transform(self, tree: Tree):
		ret = super().transform(tree)
		for orig, overwritten in self._overwritten_instrs:
			logger.warning("instr %s from extension %s was overwritten by %s from %s", orig.name, orig.ext_name, overwritten.name, overwritten.ext_name)

		return ret

	def get_constant_or_val(self, name_or_val):
		"""Helper method to either return an int value or look
		up the named constant.
		"""

		if type(name_or_val) == int:
			return name_or_val
		else:
			return self._constants[name_or_val]

	def Base(self, args):
		return args

	def make_list(self, args):
		return args

	def make_set(self, args):
		return set(args)

	def constants(self, constants):
		return constants

	def address_spaces(self, address_spaces):
		return address_spaces

	def registers(self, registers):
		return registers

	def constant_defs(self, constants):
		return constants

	def functions(self, functions):
		return functions

	def instructions(self, instructions):
		return instructions

	def range_spec(self, args) -> arch.RangeSpec:
		"""Build a rangespec."""

		return arch.RangeSpec(*args)

	def CONST_ATTRIBUTE(self, args) -> arch.ConstAttribute:
		return arch.ConstAttribute[args.value.upper()]

	def const_attributes(self, args) -> "set[arch.ConstAttribute]":
		return set(args)

	def REG_ATTRIBUTE(self, args):
		return arch.MemoryAttribute[args.value.upper()]

	def reg_attributes(self, args):
		return set(args)

	def SPACE_ATTRIBUTE(self, args):
		return arch.MemoryAttribute[args.value.upper()]

	def space_attributes(self, args):
		return set(args)

	def INSTR_ATTRIBUTE(self, args):
		return arch.InstrAttribute[args.value.upper()]

	def instr_attributes(self, args):
		return set(args)

	def DATA_TYPE(self, args):
		return arch.DataType[args.value.upper()]

	def TEXT(self, args):
		return args.value

	def constant_decl(self, args):
		"""Constant declaration, optionally with default value."""

		name, default_value = args

		if name in self._constants:
			raise M2DuplicateError(f'Constant {name} already defined!')

		if name in self._constants: return self._constants[name]
		c = arch.Constant(name, default_value, set())
		self._constants[name] = c
		logger.debug(f'constant_decl {str(c)}')
		return c

	def constant_def(self, args):
		"""Constant definition, sets default value. Optionally creates constant, although this behavior
		is deprecated.
		"""

		name, value, attributes = args
		if name in self._constants:
			c = self._constants[name]
			c.value = value
			c.attributes = attributes

			logger.debug(f'constant_def {str(c)}, used existing')
		else:
			c = arch.Constant(name, value, attributes)
			self._constants[name] = c

			logger.debug(f'constant_def {str(c)}')

		return c

	def address_space(self, args):
		"""Creates an address space. Internally builds a Memory object with range and size. Use attribute
		IS_MAIN_MEM to specify this address space should be treated as main memory.
		"""

		name, size, length_base, length_power, attribs = args

		if name in self._memories:
			raise M2DuplicateError(f'Address space {name} already defined!')

		size = self.get_constant_or_val(size)
		length_base = self.get_constant_or_val(length_base)
		length_power = self.get_constant_or_val(length_power) if length_power is not None else 1

		m = arch.Memory(name, arch.RangeSpec(length_base, None, length_power), size, attribs)
		self._memories[name] = m

		logger.debug(f'address_space {str(m)}')
		return m

	def register(self, args):
		"""Creates a register. Internally builds a Memory object with range 1 and given size. Use attribute
		IS_PC to specify the program counter register.
		"""

		name, size, attributes = args

		if name in self._memories:
			raise M2DuplicateError(f'Register {name} already defined!')

		size = self.get_constant_or_val(size)

		m = arch.Memory(name, arch.RangeSpec(0, 0), size, attributes)
		self._memories[name] = m

		logger.debug(f'register {str(m)}')
		return m

	def register_file(self, args):
		"""Creates a register file. Internally builds a Memory object with range and size. Use attribute
		IS_MAIN_REG to specify this register file is the main CPU register bank.
		"""

		_range, name, size, attributes = args

		if name in self._memories:
			raise M2DuplicateError(f'Register file {name} already defined!')

		size = self.get_constant_or_val(size)

		m = arch.Memory(name, _range, size, attributes)
		self._memories[name] = m

		if attributes is not None and arch.MemoryAttribute.IS_MAIN_REG in attributes:
			self._main_reg_file = m

		logger.debug(f'register_file {str(m)}')
		return m

	def register_alias(self, args):
		"""Define a register alias to a register or register file. Has uses index as range, size should be
		equal to parent size. Internally builds a Memory object and assigns parent and child accordingly.
		"""

		name, size, actual, index, attributes = args

		if name in self._memory_aliases:
			raise M2DuplicateError(f'Register alias {name} already defined!')

		size = self.get_constant_or_val(size)

		if not isinstance(index, arch.RangeSpec):
			index = arch.RangeSpec(index, index)

		parent_mem = self._memories.get(actual) or self._memory_aliases.get(actual)
		if parent_mem is None:
			raise M2NameError(f'Parent register {actual} for alias {name} not defined!')

		m = arch.Memory(name, index, size, attributes)
		m.parent = parent_mem
		parent_mem.children.append(m)
		self._memory_aliases[name] = m

		logger.debug(f'register_alias {str(m)}, parent {str(parent_mem)}')
		return m

	def bit_field(self, args):
		name, _range, data_type = args
		if not data_type:
			data_type = arch.DataType.U

		b = arch.BitField(name, _range, data_type)

		logger.debug(f'bit_field {str(b)}')
		return b

	def BVAL(self, num):
		return arch.BitVal(len(num) - 1, int('0'+num, 2))

	def bit_size_spec(self, args):
		size, = args
		return size

	def encoding(self, args):
		return args

	def instruction(self, args):
		"""Define an instruction. Add attributes NO_CONT if program flow continues non-linearly
		after this instruction. Add attribute COND and NO_CONT if non-linear flow is conditional.
		Disass field is currently optional.
		"""

		name, attributes, encoding, disass, operation = args

		i = arch.Instruction(name, attributes, encoding, disass, operation)
		self._instr_classes.add(i.size)

		instr_id = (i.code, i.mask)

		if instr_id in self._instructions:
			self._overwritten_instrs.append((self._instructions[instr_id], i))

		self._instructions[instr_id] = i

		logger.debug(f'instruction {str(i)}')
		return i

	def fn_args_def(self, args):
		return args

	def fn_arg_def(self, args):
		"""Define a function argument. Has name, data type and size. If data type is omitted, unsigned
		is assumed. Size can be an integer value or a constant name.
		"""

		name, data_type, size = args
		if not data_type:
			data_type = arch.DataType.U

		size = self.get_constant_or_val(size)

		fp = arch.FnParam(name, size, data_type)
		logger.debug(f'fn_param {str(fp)}')
		return fp

	def function_def(self, args):
		"""Define a function or procedure. Add name, return type and return size. If type is omitted,
		unsigned is assumed. If both type and size is omitted, a procedure is assumed. Size can be an
		integer value or constant name.
		"""

		return_len, name, fn_args, data_type, attributes, operation = args

		if not data_type and not return_len:
			data_type = arch.DataType.NONE
		elif not data_type:
			data_type = arch.DataType.U

		return_len = self.get_constant_or_val(return_len) if return_len else None
		f = arch.Function(name, attributes, return_len, data_type, fn_args, operation)

		self._functions[name] = f

		logger.debug(f'function {str(f)}')
		return f

	def instruction_set(self, args):
		name, extension, constants, address_spaces, registers, functions, instructions = args
		constants = {obj.name: obj for obj in constants} if constants else None

		memories = {}
		for item in (address_spaces, registers):
			if item:
				memories.update({obj.name: obj for obj in item})

		instructions_dict = None
		if instructions:
			instructions_dict = {}
			for i in instructions:
				instr_id = (i.code, i.mask)
				instructions_dict[instr_id] = i
				i.ext_name = name

		functions_dict = None
		if functions:
			functions_dict = {}
			for f in functions:
				functions_dict[f.name] = f
				f.ext_name = name

		i_s = arch.InstructionSet(name, extension, constants, memories, functions_dict, instructions_dict)
		self._instruction_sets[name] = i_s
		self._read_types[name] = None

		logger.debug(f'instruction_set {str(i_s)}')
		raise Discard

	def register_default(self, args):
		name, index, value_or_ref = args

		reg = self._memories.get(name) or self._memory_aliases.get(name)
		assert reg

		val = self.get_constant_or_val(value_or_ref)

		if index is not None:
			idx = self.get_constant_or_val(index)
			if reg._initval is None:
				reg._initval = {}
			reg._initval[idx] = val
		else:
			reg._initval = val

		raise Discard

	def core_def(self, args):
		"""Define a Core. Collects all seen constants, memories, functions and instructions."""

		name, _, template, _, _, _, _, _, _ = args
		c = arch.CoreDef(name, list(self._read_types.keys()), template, self._constants, self._memories, self._memory_aliases, self._functions, self._instructions, self._instr_classes)

		logger.debug(f'core_def {str(c)}')
		return c
