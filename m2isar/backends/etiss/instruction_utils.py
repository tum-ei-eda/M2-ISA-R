# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Utility classes and functions for instruction generation."""

from dataclasses import dataclass
from itertools import chain
from string import Template

from ... import M2ValueError
from ...metamodel import arch
from ...metamodel.utils import StaticType
from . import replacements

data_type_map = {
	arch.DataType.S: 'etiss_int',
	arch.DataType.U: 'etiss_uint',
	arch.DataType.NONE: 'void'
}


MEM_VAL_REPL = 'mem_val_'

def actual_size(size, min_=8, max_=128):
	"""Calculate a fitting c datatype width for any arbitrary size."""

	s = 1 << (size - 1).bit_length()
	if s > max_:
		raise M2ValueError("value too big")

	return s if s >= min_ else min_

class CodeString:
	"""Code string object. Tracks generate C++ code and various metadata for recursive
	code generation.
	"""

	mem_ids: "list[MemID]"
	def __init__(self, code, static, size, signed, is_mem_access, regs_affected=None):
		self.code = code
		self.static = StaticType(static)
		self.size = size
		self.signed = signed
		self.is_mem_access = is_mem_access
		self.mem_ids = []
		self.regs_affected = regs_affected if isinstance(regs_affected, set) else set()
		self.scalar = None
		self.mem_corrected = False
		self.is_literal = False

	@property
	def actual_size(self):
		return actual_size(self.size)

	def __str__(self):
		return self.code

	def __format__(self, format_spec):
		return self.code

@dataclass
class MemID:
	"""Track a memory access across recursive code generation."""
	mem_space: arch.Memory
	mem_id: int
	index: CodeString
	access_size: int

class TransformerContext:
	"""Track miscellaneous information throughout the code generation process. Also
	provides helper functions for staticness conversion etc.
	"""

	def __init__(self, constants: "dict[str, arch.Constant]", memories: "dict[str, arch.Memory]", memory_aliases: "dict[str, arch.Memory]",
			fields: "dict[str, arch.BitFieldDescr]", attributes: "list[arch.InstrAttribute]", functions: "dict[str, arch.Function]",
			instr_size: int, native_size: int, arch_name: str, static_scalars: bool, ignore_static=False):

		self.constants = constants
		self.memories = memories
		self.memory_aliases = memory_aliases
		self.fields = fields
		self.attributes = attributes if attributes else []
		self.scalars = {}
		self.functions = functions
		self.instr_size = instr_size
		self.native_size = native_size
		self.arch_name = arch_name
		self.static_scalars = static_scalars

		self.ignore_static = ignore_static

		self.code_lines = []

		self.pc_reg = None
		self.pc_mem = None

		for _, mem_descr in chain(self.memories.items(), self.memory_aliases.items()):
			if arch.MemoryAttribute.IS_PC in mem_descr.attributes:
				self.pc_mem = mem_descr
				break

		self.generates_exception = False
		self.is_exception = False
		self.temp_var_count = 0
		self.mem_var_count = 0
		self.affected_regs = set()
		self.dependent_regs = set()
		self.used_arch_data = False

	def make_static(self, val):
		"""Wrap a static expression."""

		if self.ignore_static:
			return val
		return Template(f'" + std::to_string({val}) + "').safe_substitute(**replacements.rename_static)

	def wrap_codestring(self, val):
		"""Wrap an entire static line."""

		if self.ignore_static:
			return val

		return f'partInit.code() += "{val}\\n";'

	def get_constant_or_val(self, name_or_val):
		"""Convenience accessor for constant values."""
		if isinstance(name_or_val, int):
			return name_or_val

		return self.constants[name_or_val]
