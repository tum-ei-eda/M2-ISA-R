import logging
from typing import List, Mapping, Set, Tuple, Union

from ...metamodel import arch
from .parser_gen import CoreDSL2Listener, CoreDSL2Parser, CoreDSL2Visitor


class ArchitectureModelBuilder(CoreDSL2Visitor):
	_constants: Mapping[str, arch.Constant]
	_instructions: Mapping[str, arch.Instruction]
	_functions: Mapping[str, arch.Function]
	_instruction_sets: Mapping[str, arch.InstructionSet]
	_read_types: Mapping[str, str]
	_memories: Mapping[str, arch.Memory]
	_memory_aliases: Mapping[str, arch.Memory]
	_overwritten_instrs: List[Tuple[arch.Instruction, arch.Instruction]]
	_instr_classes: Set[int]
	_main_reg_file: Union[arch.Memory, None]

	def __init__(self):
		super().__init__()
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

	def visitBit_field(self, ctx: CoreDSL2Parser.Bit_fieldContext):
		range = arch.RangeSpec(ctx.left, ctx.right)
		return arch.BitField()
		return "bitfield"
	
	def visitBit_value(self, ctx: CoreDSL2Parser.Bit_valueContext):
		return "bitvalue"

	def visitInstruction(self, ctx: CoreDSL2Parser.InstructionContext):
		#a=self.visitChildren(ctx)
		encoding = [self.visit(obj) for obj in ctx.encoding]
		return arch.Instruction(ctx.name.text, None, None, ctx.disass.text, ctx.behavior)
		