# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import argparse
import logging
import pathlib
import pickle
import sys

from lark import Lark, Tree

from ...metamodel import arch, behav
from .architecture_model_builder import ArchitectureModelBuilder
from .behavior_model_builder import BehaviorModelBuilder
from .instruction_set_storage import InstructionSetStorage
from .transformers import Importer, NaturalConverter, ParallelImporter, Parent

GRAMMAR_FNAME = 'coredsl.lark'

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

	logger.info('recursively importing files')
	imported_tree = tree.copy()

	if args.parallel == 1:
		i = Importer(search_path, p)
	else:
		i = ParallelImporter(search_path, args.parallel, **parser_args)

	while i.got_new:
		imported_tree = i.transform(imported_tree)

	logger.info('cleaning up tree')
	converted_tree = NaturalConverter().transform(imported_tree)
	converted_tree = Parent().visit(converted_tree)

	logger.info('reading instruction load order')
	iss = InstructionSetStorage()
	iss.visit(converted_tree)

	model_path = search_path.joinpath('gen_model')
	model_path.mkdir(exist_ok=True)

	models: "dict[str, arch.CoreDef]" = {}

	for core_name, instruction_sets in iss.core_defs.items():
		logger.info(f'building architecture model for core {core_name}')

		arch_builder = ArchitectureModelBuilder()
		mt : "list[arch.CoreDef]" = arch_builder.transform(Tree('make_list', instruction_sets))

		models[core_name] = mt[0]

	for core_name, core_def in models.items():
		logger.info(f'building behavior model for core {core_name}')

		unassigned_const = False
		for const in core_def.constants.values():
			if const.value is None:
				logger.critical("constant %s in core %s has no value assigned!", const.name, core_name)
				unassigned_const = True
				#sys.exit(-1)
		if unassigned_const:
			sys.exit(-1)

		warned_fns = set()

		# functions
		for fn_name, fn_def in core_def.functions.items():
			behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases, fn_def.args, core_def.functions, warned_fns)
			if isinstance(fn_def.operation, Tree):
				fn_def.operation = behav_builder.transform(fn_def.operation)

		# instructions
		for (code, mask), instr_def in core_def.instructions.items():
			behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases, instr_def.fields, core_def.functions, warned_fns)
			if isinstance(instr_def.operation, Tree):
				op = behav_builder.transform(instr_def.operation)

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

	logger.info('dumping model')
	with open(model_path / (abs_top_level.stem + '.m2isarmodel'), 'wb') as f:
		pickle.dump(models, f)

if __name__ == "__main__":
	main()
