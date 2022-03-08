from dataclasses import dataclass
from itertools import chain
from string import Template

from ...metamodel import arch
from .. import StaticType
from . import replacements

data_type_map = {
	arch.DataType.S: 'etiss_int',
	arch.DataType.U: 'etiss_uint',
	arch.DataType.NONE: 'void'
}


MEM_VAL_REPL = 'mem_val_'

def actual_size(size, min=8, max=128):
	s = 1 << (size - 1).bit_length()
	if s > max:
		raise ValueError("value too big")

	return s if s >= min else min

class CodeString:
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
	mem_space: arch.Memory
	mem_id: int
	index: CodeString
	access_size: int

class TransformerContext:
	def __init__(self, constants: "dict[str, arch.Constant]", memories: "dict[str, arch.Memory]", memory_aliases: "dict[str, arch.Memory]", fields: "dict[str, arch.BitFieldDescr]",
			attribs: "list[arch.InstrAttribute]", functions: "dict[str, arch.Function]",
			instr_size: int, native_size: int, arch_name: str, static_scalars: bool, ignore_static=False):

		self.constants = constants
		self.memories = memories
		self.memory_aliases = memory_aliases
		self.fields = fields
		self.attribs = attribs if attribs else []
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
			if arch.MemoryAttribute.IS_PC in mem_descr.attributes: # FIXME: change to MemAttribute
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
		if self.ignore_static:
			return val
		return Template(f'" + std::to_string({val}) + "').safe_substitute(**replacements.rename_static)

	def get_constant_or_val(self, name_or_val):
		if type(name_or_val) == int:
			return name_or_val
		else:
			return self.constants[name_or_val]
