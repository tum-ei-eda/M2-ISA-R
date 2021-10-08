import antlr4
import antlr4.error.ErrorListener

from .parser_gen import CoreDSL2Lexer, CoreDSL2Parser


class MyErrorListener(antlr4.error.ErrorListener.ErrorListener):
	def __init__(self, filename=None) -> None:
		self.filename = filename
		super().__init__()

	def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
		raise ValueError(f"Syntax error in file {self.filename}, line {line}, column {column}: {msg}")


def make_parser(filename):
	input_stream = antlr4.FileStream(filename)
	lexer = CoreDSL2Lexer(input_stream)
	stream = antlr4.CommonTokenStream(lexer)
	parser = CoreDSL2Parser(stream)
	error_handler = MyErrorListener(filename)
	parser.removeErrorListeners()
	parser.addErrorListener(error_handler)
	return parser
