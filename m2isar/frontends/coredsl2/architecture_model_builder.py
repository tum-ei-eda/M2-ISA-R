import logging
from typing import List, Mapping, Set, Tuple, Union

from ...metamodel import arch
from .parser_gen import CoreDSL2Listener, CoreDSL2Parser, CoreDSL2Visitor, CoreDSL2Lexer

RADIX = {
	'b': 2,
	'h': 16,
	'd': 10,
	'o': 8
}

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
		a = self.visitChildren(ctx)
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)
		range = arch.RangeSpec(ctx.left, ctx.right)
		#return arch.BitField()
		return "bitfield"
	
	def visitBit_value(self, ctx: CoreDSL2Parser.Bit_valueContext):
		return "bitvalue"

	def visitInstruction(self, ctx: CoreDSL2Parser.InstructionContext):
		#a=self.visitChildren(ctx)
		encoding = [self.visit(obj) for obj in ctx.encoding]
		#return arch.Instruction(ctx.name.text, None, None, ctx.disass.text, ctx.behavior)
	
	def visitTerminal(self, node):
		if node.symbol.type == CoreDSL2Lexer.INTEGER:
			tick_pos = node.symbol.text.find("'")
			text = node.symbol.text
			if tick_pos != -1:
				width = text[:tick_pos]
				radix = text[tick_pos+1]
				value = text[tick_pos+2:]

				width = int(width)
				value = int(value, RADIX[radix])

				return value, width
			
			value = int(node.symbol.text, 0)
			return value, value.bit_length()

		
		return super().visitTerminal(node)
	
	def aggregateResult(self, aggregate, nextResult):
		ret = aggregate
		if nextResult is not None:
			if ret is None:
				ret = [nextResult]
			else:
				ret += [nextResult]
		return ret