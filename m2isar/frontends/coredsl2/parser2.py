import pathlib
import sys

from .architecture_model_builder import ArchitectureModelBuilder
from .importer import recursive_import
from .load_order import LoadOrder
from .parser_gen import CoreDSL2Listener, CoreDSL2Parser, CoreDSL2Visitor
from .utils import make_parser


class Visitor2(CoreDSL2Visitor):
	def visitImport_file(self, ctx: CoreDSL2Parser.Import_fileContext):
		print("import")

class Visitor(CoreDSL2Visitor):
	def visitTerminal(self, node):
		return None
	def defaultResult(self):
		return []
	def aggregateResult(self, aggregate, nextResult):
		if nextResult is None:
			return None
		return aggregate + [nextResult]

	def visitDescription_content(self, ctx: CoreDSL2Parser.Description_contentContext):
		a = self.visitChildren(ctx)
		#imports = [self.visit(i) for i in ctx.imports]
		#definitions = [self.visit(i) for i in ctx.definitions]
		pass

	def visitImport_file(self, ctx: CoreDSL2Parser.Import_fileContext):
		a = self.visitChildren(ctx)
		return ctx.RULE_STRING().getText().replace('"', '')
	def visitInstruction_set(self, ctx: CoreDSL2Parser.Instruction_setContext):
		a = self.visitChildren(ctx)
		return (ctx.name, ctx.extension)
	def visitCore_def(self, ctx: CoreDSL2Parser.Core_defContext):
		a = self.visitChildren(ctx)
		return (ctx.name, ctx.contributing_types)

class Listener(CoreDSL2Listener):
	def enterInstruction_set(self, ctx: CoreDSL2Parser.Instruction_setContext):
		id = ctx.IDENTIFIER()
		id2 = ctx.name
		ext = ctx.extension
		print("ISA: " + ctx.name.text)
	def enterCore_def(self, ctx: CoreDSL2Parser.Core_defContext):
		print("Core: " + ctx.name.text)

def main(argv):
	app_dir = pathlib.Path(__file__).parent.resolve()
	top_level = pathlib.Path(argv[1])
	abs_top_level = top_level.resolve()
	search_path = abs_top_level.parent

	parser = make_parser(abs_top_level)

	tree = parser.description_content()

	recursive_import(tree, search_path)

	lo = LoadOrder()
	cores = lo.visit(tree)

	models = {}

	for core_name, core_def in cores.items():
		arch_builder = ArchitectureModelBuilder()
		arch_builder.visit(core_def)

		models[core_name] = arch_builder

	pass

if __name__ == '__main__':
	main(sys.argv)
