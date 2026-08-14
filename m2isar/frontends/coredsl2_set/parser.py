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
from ...metamodel import M2_METAMODEL_VERSION, M2Model, arch, behav, type_info, attribute_info
from ...metamodel.code_info import CodeInfoBase
from ..coredsl2.parser import try_eval_bool
from ..coredsl2.importer import recursive_import
from ..coredsl2.utils import make_parser
from ..coredsl2.behavior_model_builder import BehaviorModelBuilder
from ..coredsl2.architecture_model_builder import ArchitectureModelBuilder
from .load_order import LoadOrder

from ...backends.etiss.writer import BooleanOptionalAction  # TODO: refactor
from ...transforms.infer_types.transform import infer_types
from ...transforms.validate_behav.validate import validate_behav
from ...warnings import add_warnings_flags, KNOWN_WARNINGS


def parse_define(value):
	if "=" in value:
		name, raw_value = value.split("=", 1)
	else:
		name, raw_value = value, "1"
	if not name:
		raise argparse.ArgumentTypeError("define name must not be empty")
	try:
		parsed_value = int(raw_value, 0)
	except ValueError:
		raise argparse.ArgumentTypeError(
			f"invalid value for -D{name}: {raw_value!r}; expected an integer"
		)
	return name, parsed_value


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("top_level", help="The CoreDSL file.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	parser.add_argument("-I", dest="includes", action="append", default=[], help="Extra include directories")
	parser.add_argument('--infer-types', action=BooleanOptionalAction, default=True, help="Run type inference after parsing.")
	parser.add_argument('--validate', action=BooleanOptionalAction, default=False, help="Run validator after parsing.")
	parser.add_argument(
		"-D",
		dest="defines",
		action="append",
		type=parse_define,
		default=[],
		metavar="NAME[=VALUE]",
		help="Define a CoreDSL constant (default VALUE: 1), e.g. -DXLEN=32",
	)
	add_warnings_flags(parser, KNOWN_WARNINGS, KNOWN_WARNINGS)  # only if --validate
	parser.add_argument("--output", "-o", type=str, default=None)

	args = parser.parse_args()
	defines = dict(args.defines)

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
		sets = lo.visit(tree)
	except M2Error as e:
		logger.critical("Error during load order building: %s", e)
		sys.exit(1)

	if args.output is None:
		model_path = abs_top_level.parent.joinpath('gen_model')
	else:
		model_path = pathlib.Path(args.output)
	model_path.mkdir(exist_ok=True)

	temp_save = {}

	for set_name, set_def in sets.items():
		logger.info(f"building architecture model for set %s", set_name)
		try:
			arch_builder = ArchitectureModelBuilder(merge=True)
			s = arch_builder.visit(set_def)
			if not isinstance(s, list):
				s = [s]
			# print("s", s)
		except M2Error as e:
			logger.critical("Error building architecture model of set %s: %s", set_name, e)

		# for orig, overwritten in arch_builder._overwritten_instrs:
		# 	logger.warning(
		# 		"instr %s from extension %s was overwritten by %s from %s",
		# 		orig.name,
		# 		orig.ext_name,
		# 		overwritten.name,
		# 		overwritten.ext_name,
		# 	)

		temp_save[set_name] = (s, arch_builder)

		sets[set_name] = s[-1]

	for set_name, set_def in sets.items():
		logger.info("building behavior model for set %s", set_name)
		# print("set", set_name, set_def, dir(set_def))

		warned_fns = set()

		logger.debug("checking core parameters")
		unassigned_const = False
		for const in set_def.parameters.values():
			# print("const", const)
			if const.name in defines:
				logger.debug(
					"setting constant %s in set %s to %s from command line",
					const.name,
					set_name,
					defines[const.name],
				)
				const.value = defines[const.name]
			allow_undefined_const = True
			if const.value is None:
				if allow_undefined_const:
					pass
				logger.critical("constant %s in set %s has no value assigned!", const.name, set_name)
				unassigned_const = True
		if unassigned_const:
			sys.exit(-1)

		logger.debug("evaluating set parameters")

		for const_def in set_def.parameters.values():
			const_def._value = const_def.value

		for mem_def in itertools.chain(set_def.memories.values(), set_def.memory_aliases.values()):
			if isinstance(mem_def.ty, type_info.ArrayType):
				size = arch.get_const_or_val(mem_def.ty.element_type.size)
			elif isinstance(mem_def.ty, type_info.PrimitiveType):
				size = arch.get_const_or_val(mem_def.ty.size)
			else:
				assert(isinstance(mem_def.ty, type_info.PointerType))
				if isinstance(mem_def.ty.ty, type_info.ArrayType):
					size = arch.get_const_or_val(mem_def.ty.ty.element_type.size)
				else:
					size = arch.get_const_or_val(mem_def.ty.ty.size)
			mem_def.ty.size = size

			for attr_name, attr_ops in mem_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(
							set_def.parameters,
							set_def.memories,
							set_def.memory_aliases,
							set_def.register_banks,
							set_def.register_aliases,
							{},
							set_def.functions,
							warned_fns,
						)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical(
							'error processing attribute "%s" of memory "%s": %s', attr_name, mem_def.name, e
						)
						sys.exit(1)

				mem_def.attributes[attr_name] = ops

		for reg_def in itertools.chain(set_def.register_banks.values(), set_def.register_aliases.values()):
			if isinstance(reg_def.ty, type_info.ArrayType):
				reg_def.ty.element_type.size = arch.get_const_or_val(reg_def.ty.element_type.size)
				reg_def.ty.length = arch.get_const_or_val(reg_def.ty.length)
			elif isinstance(reg_def.ty, type_info.PrimitiveType):
				reg_def.ty.size = arch.get_const_or_val(reg_def.ty.size)
			else:
				assert(isinstance(reg_def.ty, type_info.PointerType)) # TODO: PointerType handlind looks like cancer!!!!
				pass
				# if isinstance(reg_def.ty.ty, type_info.ArrayType):
				# 	reg_def.ty.size = arch.get_const_or_val(reg_def.ty.ty.element_type.size)
				# else:
				# 	reg_def.ty.size = arch.get_const_or_val(reg_def.ty.ty.size)

			for attr_name, attr_ops in reg_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:

						behav_builder = BehaviorModelBuilder(set_def.parameters, {}, {}, set_def.register_banks, set_def.register_aliases, {}, set_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of memory \"%s\": %s", attr_name, reg_def.name, e)
						sys.exit(1)

				reg_def.attributes[attr_name] = ops

		for fn_def in set_def.functions.values():
			if isinstance(fn_def.operation, behav.Operation) and not fn_def.extern:
				raise M2SyntaxError(f"non-extern function {fn_def.name} has no body")

			fn_def.ty.size = arch.get_const_or_val(fn_def.ty.size)

		logger.debug("generating function behavior")

		for fn_name, fn_def in set_def.functions.items():
			logger.debug("generating function %s", fn_name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in fn_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(
							set_def.parameters,
							set_def.memories,
							set_def.memory_aliases,
							set_def.register_banks,
							set_def.register_aliases,
							fn_def.args,
							set_def.functions,
							warned_fns,
						)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical(
							'error processing attribute "%s" of function "%s": %s', attr_name, fn_def.name, e
						)
						sys.exit(1)

				fn_def.attributes[attr_name] = ops

			behav_builder = BehaviorModelBuilder(
				set_def.parameters, set_def.memories, set_def.memory_aliases, set_def.register_banks, set_def.register_aliases, fn_def.args, set_def.functions, warned_fns
			)

			if not isinstance(fn_def.operation, behav.Operation):
				try:
					op = behav_builder.visit(fn_def.operation)
				except M2Error as e:
					logger.critical("Error building behavior for function %s: %s", fn_name, e)
					sys.exit()

				fn_def.vars = behav_builder._vars

				if isinstance(op, list):
					fn_def.operation = behav.Operation(op)
				else:
					fn_def.operation = behav.Operation([op])

		logger.debug("generating always blocks")

		always_block_statements = []

		arch_builder = temp_save[set_name][1]
		for block_def in arch_builder._always_blocks.values():
			logger.debug("generating always block %s", block_def.name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in block_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(
							set_def.parameters,
							set_def.memories,
							set_def.memory_aliases,
							set_def.register_banks,
							set_def.register_aliases,
							{},
							set_def.functions,
							warned_fns,
						)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical(
							'error processing attribute "%s" of instruction "%s": %s', attr_name, block_def.name, e
						)
						sys.exit(1)

				block_def.attributes[attr_name] = ops

			behav_builder = BehaviorModelBuilder(
				set_def.parameters, set_def.memories, set_def.memory_aliases, set_def.register_banks, set_def.register_aliases, {}, set_def.functions, warned_fns
			)

			try:
				op = behav_builder.visit(block_def.operation)
			except M2Error as e:
				logger.critical("error building behavior for always block %s: %s", block_def.name, e)
				sys.exit(1)

			always_block_statements.append(op)

		logger.debug("generating instruction behavior")
		instructions_by_enc = {}
		assert isinstance(set_def.instructions, list)
		overwritten_instrs: "list[tuple[arch.Instruction, arch.Instruction]]" = []
		# for instr_def in set_def.instructions.values():
		for instr_def in set_def.instructions:

			logger.debug("generating instruction %s", instr_def.name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in instr_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(
							set_def.parameters,
							set_def.memories,
							set_def.memory_aliases,
							set_def.register_banks,
							set_def.register_aliases,
							instr_def.fields,
							set_def.functions,
							warned_fns,
						)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical(
							'error processing attribute "%s" of instruction "%s": %s', attr_name, instr_def.name, e
						)
						sys.exit(1)

				instr_def.attributes[attr_name] = ops
			if attribute_info.InstrAttribute.ENABLE in instr_def.attributes:
				enable_attr = instr_def.attributes[attribute_info.InstrAttribute.ENABLE]
				assert isinstance(enable_attr, list)
				assert len(enable_attr) == 1
				enable_attr = enable_attr[0]
				enable = try_eval_bool(enable_attr, set_def.parameters, set_def.memories, set_def.memory_aliases, instr_def.fields, set_def.functions, warned_fns)
				if enable is not None:
					assert isinstance(enable, bool)
					instr_def.attributes.pop(attribute_info.InstrAttribute.ENABLE)
					if not enable:
						continue

			print("set_def.parameters", set_def.parameters)
			print("set_def.memories", set_def.memories)
			print("set_def.memory_aliases", set_def.memory_aliases)
			print("set_def.register_banks", set_def.register_banks)
			print("set_def.register_aliases", set_def.register_aliases)
			behav_builder = BehaviorModelBuilder(
				set_def.parameters,
				set_def.memories,
				set_def.memory_aliases,
				set_def.register_banks,
				set_def.register_aliases,
				instr_def.fields,
				set_def.functions,
				warned_fns,
			)

			try:
				op = behav_builder.visit(instr_def.operation)
			except M2Error as e:
				logger.critical(
					"error building behavior for instruction %s::%s: %s", instr_def.ext_name, instr_def.name, e
				)
				raise e
				sys.exit(1)

			instr_def.vars = behav_builder._vars

			if isinstance(op, list):
				op = behav.Operation(op)
			else:
				op = behav.Operation([op])

			# pc_inc = behav.Assignment(
			#	behav.NamedReference(set_def.pc_memory),
			#	behav.BinaryOperation(
			#		behav.NamedReference(set_def.pc_memory),
			#		behav.Operator("+"),
			#		behav.IntLiteral(int(instr_def.size/8))
			#	)
			# )

			# op.statements.insert(0, pc_inc)
			op.statements = always_block_statements + op.statements
			instr_def.operation = op
			instr_id = (instr_def.code, instr_def.mask)
			# check for duplicate instructions
			if instr_id in instructions_by_enc:
				overwritten_instrs.append((instructions_by_enc[instr_id], instr_def))
			instructions_by_enc[instr_id] = instr_def
		set_def.instructions = instructions_by_enc
		assert isinstance(set_def.instructions, dict)
		for orig, overwritten in overwritten_instrs:
			logger.warning("instr %s from extension %s was overwritten by %s from %s", orig.name, orig.ext_name, overwritten.name, overwritten.ext_name)
	model_obj = M2Model(M2_METAMODEL_VERSION, {}, sets, CodeInfoBase.database)
	warnings_info = args.warnings
	if args.infer_types or args.validate:
		logger.info("Running type inference")
		model_obj = infer_types(model_obj, warnings_info=warnings_info)
	if args.validate:
		logger.info("Running validator")
		validate_behav(model_obj, warnings_info)

	logger.info("dumping model")
	with open(model_path / (abs_top_level.stem + ".m2isarmodel"), "wb") as f:
		pickle.dump(model_obj, f)


if __name__ == "__main__":
	main()
