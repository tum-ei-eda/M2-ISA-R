import argparse
import logging
import pathlib
import pickle
import sys
from typing import List

from lark import Lark, Tree

from ...metamodel import arch
#from .architecture_model_builder import ArchitectureModelBuilder
#from .behavior_model_builder import BehaviorModelBuilder
#from .instruction_set_storage import InstructionSetStorage
#from .transformers import Importer, NaturalConverter, ParallelImporter, Parent


GRAMMAR_FNAME = 'coredsl2.lark'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("top_level", help="The top-level CoreDSL file.")
	parser.add_argument("-j", default=1, type=int, dest='parallel', help="Use PARALLEL threads while parsing.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])

	args = parser.parse_args()

	app_dir = pathlib.Path(__file__).parent.resolve()

	logging.basicConfig(level=getattr(logging, args.log.upper()))
	logger = logging.getLogger("parser")

	top_level = pathlib.Path(args.top_level)
	abs_top_level = top_level.resolve()
	search_path = abs_top_level.parent

	parser_args = {'grammar_filename': app_dir/GRAMMAR_FNAME, 'parser': 'earley', 'maybe_placeholders': True, 'debug': False}

	logger.info('reading grammar')
	p = Lark.open(**parser_args)

	logger.info('parsing top level')
	with open(abs_top_level, 'r') as f:
		tree = p.parse(f.read())
	print(tree.pretty("\t"))
	logger.info('recursively importing files')
	imported_tree = tree.copy()

if __name__ == "__main__":
	main()
