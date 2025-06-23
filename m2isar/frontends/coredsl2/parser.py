# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import argparse
import itertools
import logging
import pathlib
import pickle
import sys

from ... import M2Error, M2SyntaxError
from ...metamodel import (M2_METAMODEL_VERSION, M2Model, arch, behav,
                          patch_model)
from ...metamodel.code_info import CodeInfoBase
from . import expr_interpreter
from .architecture_model_builder import ArchitectureModelBuilder
from .behavior_model_builder import BehaviorModelBuilder
from .importer import recursive_import
from .load_order import LoadOrder
from .utils import make_parser


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("top_level", help="The top-level CoreDSL file.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	parser.add_argument("-I", dest="includes", action="append", default=[], help="Extra include directories")

	args = parser.parse_args()

	logging.basicConfig(level=getattr(logging, args.log.upper()))
	logger = logging.getLogger("parser")

	top_level = pathlib.Path(args.top_level)
	abs_top_level = top_level.resolve()
	extra_includes = args.includes
	extra_includes = list(map(lambda x: x.resolve(), map(pathlib.Path, extra_includes)))
	search_paths = [abs_top_level.parent] + extra_includes

	parser = make_parser(abs_top_level)

	try:
		logger.info("parsing top level")
		tree = parser.description_content()

		recursive_import(tree, search_paths)
	except M2SyntaxError as e:
		logger.critical("Error during parsing: %s", e)
		sys.exit(1)

	logger.info("reading instruction load order")
	lo = LoadOrder()
	try:
		cores = lo.visit(tree)
	except M2Error as e:
		logger.critical("Error during load order building: %s", e)
		sys.exit(1)

	model_path = abs_top_level.parent.joinpath('gen_model')
	model_path.mkdir(exist_ok=True)

	temp_save = {}
	models: "dict[str, arch.CoreDef]" = {}

	patch_model(expr_interpreter)

	for core_name, core_def in cores.items():
		logger.info('building architecture model for core %s', core_name)
		try:
			arch_builder = ArchitectureModelBuilder()
			c = arch_builder.visit(core_def)
		except M2Error as e:
			logger.critical("Error building architecture model of core %s: %s", core_name, e)

		for orig, overwritten in arch_builder._overwritten_instrs:
			logger.warning("instr %s from extension %s was overwritten by %s from %s", orig.name, orig.ext_name, overwritten.name, overwritten.ext_name)

		temp_save[core_name] = (c, arch_builder)
		models[core_name] = c[-1]

	for core_name, core_def in models.items():
		logger.info('building behavior model for core %s', core_name)

		warned_fns = set()

		logger.debug("checking core constants")
		unassigned_const = False
		for const in core_def.constants.values():
			if const.value is None:
				logger.critical("constant %s in core %s has no value assigned!", const.name, core_name)
				unassigned_const = True
				#sys.exit(-1)
		if unassigned_const:
			sys.exit(-1)

		logger.debug("evaluating core parameters")

		for const_def in core_def.constants.values():
			const_def._value = const_def.value

		for mem_def in itertools.chain(core_def.memories.values(), core_def.memory_aliases.values()):
			mem_def._size = mem_def.size
			mem_def.range._lower_base = mem_def.range.lower_base
			mem_def.range._upper_base = mem_def.range.upper_base

			for attr_name, attr_ops in mem_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
							{}, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of memory \"%s\": %s", attr_name, fn_def.name, e)
						sys.exit(1)

				mem_def.attributes[attr_name] = ops

		for fn_def in core_def.functions.values():
			if isinstance(fn_def.operation, behav.Operation) and not fn_def.extern:
				raise M2SyntaxError(f"non-extern function {fn_def.name} has no body")

			fn_def._size = fn_def.size
			for fn_arg in fn_def.args.values():
				fn_arg._size = fn_arg.size
				fn_arg._width = fn_arg.width

		logger.debug("generating function behavior")

		for fn_name, fn_def in core_def.functions.items():
			logger.debug("generating function %s", fn_name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in fn_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
							fn_def.args, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of function \"%s\": %s", attr_name, fn_def.name, e)
						sys.exit(1)

				fn_def.attributes[attr_name] = ops

			behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
				fn_def.args, core_def.functions, warned_fns)

			if not isinstance(fn_def.operation, behav.Operation):
				try:
					op = behav_builder.visit(fn_def.operation)
				except M2Error as e:
					logger.critical("Error building behavior for function %s: %s", fn_name, e)
					sys.exit()

				fn_def.scalars = behav_builder._scalars

				if isinstance(op, list):
					fn_def.operation = behav.Operation(op)
				else:
					fn_def.operation = behav.Operation([op])

		logger.debug("generating always blocks")

		always_block_statements = []

		arch_builder = temp_save[core_name][1]
		for block_def in arch_builder._always_blocks.values():
			logger.debug("generating always block %s", block_def.name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in block_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
							{}, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of instruction \"%s\": %s", attr_name, block_def.name, e)
						sys.exit(1)

				block_def.attributes[attr_name] = ops

			behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
				{}, core_def.functions, warned_fns)

			try:
				op = behav_builder.visit(block_def.operation)
			except M2Error as e:
				logger.critical("error building behavior for always block %s: %s", block_def.name, e)
				sys.exit(1)

			always_block_statements.append(op)

		logger.debug("generating instruction behavior")

		for instr_def in core_def.instructions.values():
			logger.debug("generating instruction %s", instr_def.name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in instr_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
							instr_def.fields, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of instruction \"%s\": %s", attr_name, instr_def.name, e)
						sys.exit(1)

				instr_def.attributes[attr_name] = ops

			behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases,
				instr_def.fields, core_def.functions, warned_fns)

			try:
				op = behav_builder.visit(instr_def.operation)
			except M2Error as e:
				logger.critical("error building behavior for instruction %s::%s: %s", instr_def.ext_name, instr_def.name, e)
				sys.exit(1)

			instr_def.scalars = behav_builder._scalars

			if isinstance(op, list):
				op = behav.Operation(op)
			else:
				op = behav.Operation([op])

			pc_inc = behav.Assignment(
				behav.NamedReference(core_def.pc_memory),
				behav.BinaryOperation(
					behav.NamedReference(core_def.pc_memory),
					behav.Operator("+"),
					behav.IntLiteral(int(instr_def.size/8))
				)
			)

			#op.statements.insert(0, pc_inc)
			op.statements = always_block_statements + op.statements
			instr_def.operation = op

	logger.info("dumping model")
	with open(model_path / (abs_top_level.stem + '.m2isarmodel'), 'wb') as f:
		model_obj = M2Model(
			M2_METAMODEL_VERSION,
			models,
			{},
			CodeInfoBase.database
		)

		pickle.dump(model_obj, f)


if __name__ == '__main__':
	main()
