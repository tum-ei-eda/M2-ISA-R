import pathlib
import sys

import antlr4

from CoreDSL2Lexer import CoreDSL2Lexer
from CoreDSL2Listener import CoreDSL2Listener
from CoreDSL2Parser import CoreDSL2Parser
from CoreDSL2Visitor import CoreDSL2Visitor


class Visitor(CoreDSL2Visitor):
	def visitDescription_content(self, ctx: CoreDSL2Parser.Description_contentContext):
		imports = [self.visit(i) for i in ctx.imports]
		definitions = [self.visit(i) for i in ctx.definitions]
		pass

	def visitImport_file(self, ctx: CoreDSL2Parser.Import_fileContext):
		return ctx.RULE_STRING().getText().replace('"', '')
	def visitInstruction_set(self, ctx: CoreDSL2Parser.Instruction_setContext):
		return (ctx.name, ctx.extension)
	def visitCore_def(self, ctx: CoreDSL2Parser.Core_defContext):
		return (ctx.name, ctx.contributing_types)

class Listener(CoreDSL2Listener):
	def enterInstruction_set(self, ctx: CoreDSL2Parser.Instruction_setContext):
		id = ctx.RULE_ID()
		id2 = ctx.name
		ext = ctx.extension
		print("ISA: " + ctx.name.text)
	def enterCore_def(self, ctx: CoreDSL2Parser.Core_defContext):
		print("Core: " + ctx.name.text)


class Importer(CoreDSL2Listener):
	def __init__(self, search_path) -> None:
		super().__init__()
		self.imported = set()
		self.new_children = []
		self.new_defs = []
		self.got_new = True
		self.search_path = search_path

	def enterImport_file(self, ctx: CoreDSL2Parser.Import_fileContext):
		filename = ctx.RULE_STRING().getText().replace('"', '')
		if filename not in self.imported:
			print(f"importing file {filename}")
			self.got_new = True
			self.imported.add(filename)

			input_stream = antlr4.FileStream(self.search_path/filename)
			lexer = CoreDSL2Lexer(input_stream)
			stream = antlr4.CommonTokenStream(lexer)
			parser = CoreDSL2Parser(stream)

			tree = parser.description_content()

			self.new_children.extend(tree.children)
			self.new_defs.extend(tree.definitions)
		pass

def main(argv):
	app_dir = pathlib.Path(__file__).parent.resolve()
	top_level = pathlib.Path(argv[1])
	abs_top_level = top_level.resolve()
	search_path = abs_top_level.parent

	input_stream = antlr4.FileStream(top_level)
	lexer = CoreDSL2Lexer(input_stream)
	stream = antlr4.CommonTokenStream(lexer)
	parser = CoreDSL2Parser(stream)
	tree = parser.description_content()
	#print(tree.toStringTree(recog=parser))

	importer = Importer(search_path)
	walker = antlr4.ParseTreeWalker()

	while importer.got_new:
		importer.new_children.clear()
		importer.got_new = False

		walker.walk(importer, tree)

		tree.definitions = importer.new_defs + tree.definitions
		tree.children = importer.new_children + [x for x in tree.children if not isinstance(x, CoreDSL2Parser.Import_fileContext)]

	listener = Listener()
	walker.walk(listener, tree)

	visitor = Visitor()
	a = visitor.visit(tree)

	pass

if __name__ == '__main__':
    main(sys.argv)
