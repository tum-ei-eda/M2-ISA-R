from dataclasses import dataclass
from enum import Flag, auto
from itertools import chain
from string import Template
from typing import Iterable, List, Mapping

import etiss_replacements
import model_classes

data_type_map = {
	model_classes.DataType.S: 'etiss_int',
	model_classes.DataType.U: 'etiss_uint',
	model_classes.DataType.NONE: 'void'
}

class StaticType(Flag):
	NONE = 0
	READ = auto()
	WRITE = auto()
	RW = READ | WRITE

MEM_VAL_REPL = 'mem_val_'

class CodeString:
	mem_ids: List["MemID"]
	def __init__(self, code, static, size, signed, is_mem_access, regs_affected=None):
		self.code = code
		self.static = StaticType(static)
		self.size = size
		self.actual_size = 1 << (size - 1).bit_length()
		if self.actual_size < 8:
			self.actual_size = 8
		self.signed = signed
		self.is_mem_access = is_mem_access
		self.mem_ids = []
		self.regs_affected = regs_affected if isinstance(regs_affected, set) else set()
		self.scalar = None
		self.mem_corrected = False

	def __str__(self):
		return self.code

	def __format__(self, format_spec):
		return self.code

@dataclass
class MemID:
	mem_space: model_classes.Memory
	mem_id: int
	index: CodeString
	access_size: int

class TransformerContext:
	def __init__(self, constants: Mapping[str, model_classes.Constant], spaces: Mapping[str, model_classes.AddressSpace],
			registers: Mapping[str, model_classes.Register], register_files: Mapping[str, model_classes.RegisterFile],
			register_aliases: Mapping[str, model_classes.RegisterAlias], memories: Mapping[str, model_classes.Memory], memory_aliases: Mapping[str, model_classes.Memory], fields: Mapping[str, model_classes.BitFieldDescr],
			attribs: Iterable[model_classes.InstrAttribute], functions: Mapping[str, model_classes.Function],
			instr_size: int, native_size: int, arch_name: str, ignore_static=False):

		self.constants = constants
		self.spaces = spaces
		self.registers = registers
		self.register_files = register_files
		self.register_aliases = register_aliases
		self.memories = memories
		self.memory_aliases = memory_aliases
		self.fields = fields
		self.attribs = attribs if attribs else []
		self.scalars = {}
		self.functions = functions
		self.instr_size = instr_size
		self.native_size = native_size
		self.arch_name = arch_name

		self.ignore_static = ignore_static

		self.code_lines = []

		self.pc_reg = None
		self.pc_mem = None

		for _, mem_descr in chain(self.memories.items(), self.memory_aliases.items()):
			if model_classes.RegAttribute.IS_PC in mem_descr.attributes: # FIXME: change to MemAttribute
				self.pc_mem = mem_descr
				break

		for _, reg_descr in chain(self.registers.items(), self.register_aliases.items()):
			if model_classes.RegAttribute.IS_PC in reg_descr.attributes:
				self.pc_reg = reg_descr
				break

		self.generates_exception = False
		self.is_exception = False
		self.temp_var_count = 0
		self.mem_var_count = 0
		self.affected_regs = set()
		self.dependent_regs = set()
		self.used_arch_data = False

	def make_static(self, val):
		if self.ignore_static:
			return val
		return Template(f'" + std::to_string({val}) + "').safe_substitute(**etiss_replacements.rename_static)

	def get_constant_or_val(self, name_or_val):
		if type(name_or_val) == int:
			return name_or_val
		else:
			return self.constants[name_or_val]
