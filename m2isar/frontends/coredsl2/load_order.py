from antlr4 import ParserRuleContext

from .parser_gen import CoreDSL2Parser, CoreDSL2Visitor


class CoreContainerContext(ParserRuleContext):
	pass

class LoadOrder(CoreDSL2Visitor):
	def __init__(self) -> None:
		super().__init__()
		self.instruction_sets: dict[str, CoreDSL2Parser.Instruction_setContext] = {}
		self.core_defs = {}

	def visitInstruction_set(self, ctx: CoreDSL2Parser.Instruction_setContext):
		name = ctx.name.text

		if name in self.instruction_sets:
			raise ValueError(f"instruction set {name} specified more than once")

		self.instruction_sets[name] = ctx

	def extend_ins_set(self, ins_set_name):
		extensions = [e.text for e in self.instruction_sets[ins_set_name].extension]
		if extensions:
			ret = [ins_set_name]
			for extension in extensions:
				ret = self.extend_ins_set(extension) + ret
			return ret
		else:
			return [ins_set_name]

	def visitCore_def(self, ctx: CoreDSL2Parser.Core_defContext):
		name = ctx.name.text
		contributing_types = [c.text for c in ctx.contributing_types]

		ins_set_queue = []
		known_sets = set()

		for ct in contributing_types:
			new_sets = self.extend_ins_set(ct)
			for new_set in new_sets:
				if new_set not in known_sets:
					known_sets.add(new_set)
					ins_set_queue.append(self.instruction_sets[new_set])

		ins_set_queue.append(ctx)
		self.core_defs[name] = ins_set_queue

	def visit(self, tree):
		_ = super().visit(tree)

		ret = {}

		for core_name, contents in self.core_defs.items():
			container = CoreContainerContext()
			container.children = contents
			container.name = core_name
			ret[core_name] = container

		return ret
