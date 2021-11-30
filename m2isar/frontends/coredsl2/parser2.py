import argparse
import itertools
import logging
import pathlib
import pickle
import sys
from typing import Dict, Tuple

from ...metamodel import arch, behav
from .architecture_model_builder import ArchitectureModelBuilder
from .behavior_model_builder import BehaviorModelBuilder
from .importer import recursive_import
from .load_order import LoadOrder
from .utils import make_parser


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("top_level", help="The top-level CoreDSL file.")
	#parser.add_argument("-j", default=1, type=int, dest='parallel', help="Use PARALLEL threads while parsing.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])

	args = parser.parse_args()

	app_dir = pathlib.Path(__file__).parent.resolve()

	logging.basicConfig(level=getattr(logging, args.log.upper()))
	logger = logging.getLogger("parser")

	top_level = pathlib.Path(args.top_level)
	abs_top_level = top_level.resolve()
	search_path = abs_top_level.parent

	parser = make_parser(abs_top_level)

	logger.info("parsing top level")
	tree = parser.description_content()

	recursive_import(tree, search_path)

	logger.info("reading instruction load order")
	lo = LoadOrder()
	cores = lo.visit(tree)

	model_path = search_path.joinpath('gen_model')
	model_path.mkdir(exist_ok=True)

	temp_save = {}
	models: Dict[Tuple(int, int), arch.CoreDef] = {}

	for core_name, core_def in cores.items():
		logger.info(f'building architecture model for core {core_name}')
		arch_builder = ArchitectureModelBuilder()
		c = arch_builder.visit(core_def)

		temp_save[core_name] = (c, arch_builder)
		models[core_name] = c[-1]

	for core_name, core_def in models.items():
		logger.info('building behavior model for core %s', core_name)

		logger.info("checking core constants")
		unassigned_const = False
		for const in core_def.constants.values():
			if const.value is None:
				logger.critical("constant %s in core %s has no value assigned!", const.name, core_name)
				unassigned_const = True
				#sys.exit(-1)
		if unassigned_const:
			sys.exit(-1)

		logger.info("evaluating core parameters")

		for const_def in core_def.constants.values():
			const_def._value = const_def.value

		for mem_def in itertools.chain(core_def.memories.values(), core_def.memory_aliases.values()):
			mem_def._size = mem_def.size
			mem_def.range._lower_base = mem_def.range.lower_base
			mem_def.range._upper_base = mem_def.range.upper_base

		for fn_def in core_def.functions.values():
			fn_def._size = fn_def.size
			for fn_arg in fn_def.args.values():
				fn_arg._size = fn_arg.size
				fn_arg._width = fn_arg.width

		logger.info("generating function behavior")

		warned_fns = set()

		for fn_name, fn_def in core_def.functions.items():
			behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
				fn_def.args, core_def.functions, warned_fns)

			if not isinstance(fn_def.operation, behav.Operation):
				op = behav_builder.visit(fn_def.operation)
				if isinstance(op, list):
					fn_def.operation = behav.Operation(op)
				else:
					fn_def.operation = behav.Operation([op])

		logger.info("generating instruction behavior")

		for (code, mask), instr_def in core_def.instructions.items():
			behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
				instr_def.fields, core_def.functions, warned_fns)

			op = behav_builder.visit(instr_def.operation)
			if isinstance(op, list):
				op = behav.Operation(op)
			else:
				op = behav.Operation([op])

			pc_inc = behav.Assignment(
				behav.NamedReference(core_def.pc_memory),
				behav.BinaryOperation(
					behav.NamedReference(core_def.pc_memory),
					behav.Operator("+"),
					behav.NumberLiteral(int(instr_def.size/8))
				)
			)

			if arch.InstrAttribute.NO_CONT in instr_def.attributes and arch.InstrAttribute.COND in instr_def.attributes:
				op.statements.insert(0, pc_inc)
			elif arch.InstrAttribute.NO_CONT not in instr_def.attributes:
				op.statements.append(pc_inc)

			instr_def.operation = op

	logger.info("dumping model")
	with open(model_path / (abs_top_level.stem + '.m2isarmodel'), 'wb') as f:
		pickle.dump(models, f)

if __name__ == '__main__':
	main()
