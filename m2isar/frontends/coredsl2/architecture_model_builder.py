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
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)
		range = arch.RangeSpec(left.value, right.value)
		return arch.BitField(ctx.name.text, range, arch.DataType.U)

	def visitBit_value(self, ctx: CoreDSL2Parser.Bit_valueContext):
		val = self.visit(ctx.value)
		return arch.BitVal(val.bit_size, val.value)

	def visitInstruction(self, ctx: CoreDSL2Parser.InstructionContext):
		encoding = [self.visit(obj) for obj in ctx.encoding]
		attributes = [self.visit(obj) for obj in ctx.attributes]
		i = arch.Instruction(ctx.name.text, attributes, encoding, ctx.disass.text, ctx.behavior)
		self._instructions[ctx.name.text] = i
		return i

	def visitAttribute(self, ctx: CoreDSL2Parser.AttributeContext):
		return super().visitAttribute(ctx)

	def visitInteger_constant(self, ctx: CoreDSL2Parser.Integer_constantContext):
		text: str = ctx.value.text.lower()

		tick_pos = text.find("'")

		if tick_pos != -1:
			width = int(text[:tick_pos])
			radix = text[tick_pos+1]
			value = int(text[tick_pos+2:], RADIX[radix])

		else:
			value = int(text, 0)
			if text.startswith("0b"):
				width = len(text) - 2
			elif text.startswith("0x"):
				width = (len(text) - 2) * 4
			elif text.startswith("0") and len(text) > 1:
				width = (len(text) - 1) * 3
			else:
				width = value.bit_length()

		return arch.IntLiteral(value, width)

	def visitDeclaration(self, ctx: CoreDSL2Parser.DeclarationContext):
		return super().visitDeclaration(ctx)

	def visitAssignment_expression(self, ctx: CoreDSL2Parser.Assignment_expressionContext):
		return super().visitAssignment_expression(ctx)

	def visitTerminal(self, node):
		if node.symbol.type == CoreDSL2Lexer.MEM_ATTRIBUTE:
			return arch.MemoryAttribute[node.symbol.text.upper()]
		elif node.symbol.type == CoreDSL2Lexer.INSTR_ATTRIBUTE:
			return arch.InstrAttribute[node.symbol.text.upper()]
		return super().visitTerminal(node)

	def visitChildren(self, node):
		ret = super().visitChildren(node)
		if isinstance(ret, list) and len(ret) == 1:
			return ret[0]
		return ret

	def aggregateResult(self, aggregate, nextResult):
		ret = aggregate
		if nextResult is not None:
			if ret is None:
				ret = [nextResult]
			else:
				ret += [nextResult]
		return ret