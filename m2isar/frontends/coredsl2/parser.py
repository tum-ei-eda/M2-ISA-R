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
from ...metamodel.utils.expr_simplifier import ExprSimplifierVisitor
from ...metamodel.code_info import CodeInfoBase
from .architecture_model_builder import ArchitectureModelBuilder
from .behavior_model_builder import BehaviorModelBuilder
from .importer import recursive_import
from .load_order import LoadOrder
from .utils import make_parser
from ...backends.etiss.writer import BooleanOptionalAction  # TODO: refactor
from ...transforms.infer_types.transform import infer_types
from ...transforms.validate_behav.validate import validate_behav
from ...warnings import add_warnings_flags, KNOWN_WARNINGS

def try_eval_bool(operation, parameters: "dict[str, arch.Parameter]", memories: "dict[str, arch.Memory]", memory_aliases: "dict[str, arch.Memory]",
	fields: "dict[str, arch.BitFieldDescr]", functions: "dict[str, arch.Function]", warned_fns: "set[str]"):
	simplifier = ExprSimplifierVisitor()
	# TODO: switch to ExprInterpreterVisitor?
	op = simplifier.generate(operation, None)
	if not isinstance(op, behav.Literal):
		return None
	return op.value != 0


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("top_level", help="The top-level CoreDSL file.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	parser.add_argument("-I", dest="includes", action="append", default=[], help="Extra include directories")
	parser.add_argument('--infer-types', action=BooleanOptionalAction, default=True, help="Run type inference after parsing.")
	parser.add_argument('--validate', action=BooleanOptionalAction, default=False, help="Run validator after parsing.")
	add_warnings_flags(parser, KNOWN_WARNINGS, KNOWN_WARNINGS)  # only if --validate

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

	for core_name, core_def in cores.items():
		logger.info('building architecture model for core %s', core_name)
		try:
			arch_builder = ArchitectureModelBuilder()
			c = arch_builder.visit(core_def)
		except M2Error as e:
			logger.critical("Error building architecture model of core %s: %s", core_name, e)

		# for orig, overwritten in arch_builder._overwritten_instrs:
		# 	logger.warning("instr %s from extension %s was overwritten by %s from %s", orig.name, orig.ext_name, overwritten.name, overwritten.ext_name)

		temp_save[core_name] = (c, arch_builder)
		models[core_name] = c[-1]

	for core_name, core_def in models.items():
		logger.info('building behavior model for core %s', core_name)

		warned_fns = set()

		logger.debug("checking core parameters")
		unassigned_const = False
		for const in core_def.parameters.values():
			if const.value is None:
				logger.critical("constant %s in core %s has no value assigned!", const.name, core_name)
				unassigned_const = True
				#sys.exit(-1)
		if unassigned_const:
			sys.exit(-1)

		logger.debug("evaluating core parameters")

		for const_def in core_def.parameters.values():
			const_def._value = const_def.value

		for mem_def in itertools.chain(core_def.memories.values(), core_def.memory_aliases.values()):
			if isinstance(mem_def.ty, type_info.ArrayType):
				size = arch.get_const_or_val(mem_def.ty.element_type.size)
			elif isinstance(mem_def.ty, type_info.PrimitiveType):
				size = arch.get_const_or_val(mem_def.ty.size)
			else:
				assert(isinstance(mem_def.ty, type_info.PointerType)) # TODO: PointerType handlind looks like cancer!!!!
				if isinstance(mem_def.ty.ty, type_info.ArrayType):
					size = arch.get_const_or_val(mem_def.ty.ty.element_type.size)
				else:
					size = arch.get_const_or_val(mem_def.ty.ty.size)

			mem_def.ty.size = size
			for attr_name, attr_ops in mem_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:

						behav_builder = BehaviorModelBuilder(core_def.parameters, core_def.memories, core_def.memory_aliases,
							{}, {}, {}, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of memory \"%s\": %s", attr_name, fn_def.name, e)
						sys.exit(1)

				mem_def.attributes[attr_name] = ops

		for reg_def in itertools.chain(core_def.register_banks.values(), core_def.register_aliases.values()):
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

						behav_builder = BehaviorModelBuilder(core_def.parameters, {}, {},core_def.register_banks,
										    core_def.register_aliases, {}, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of memory \"%s\": %s", attr_name, fn_def.name, e)
						sys.exit(1)

				reg_def.attributes[attr_name] = ops

		for fn_def in core_def.functions.values():
			if isinstance(fn_def.operation, behav.Operation) and not fn_def.extern:
				raise M2SyntaxError(f"non-extern function {fn_def.name} has no body")

			fn_def.ty.size = arch.get_const_or_val(fn_def.ty.size)
			fn_def._size = fn_def.ty.size
			for fn_arg in fn_def.args.values():
				fn_arg._size = fn_arg.ty.size
				fn_arg._width = fn_arg.width

		logger.debug("generating function behavior")

		for fn_name, fn_def in core_def.functions.items():
			logger.debug("generating function %s", fn_name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in fn_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(core_def.parameters, core_def.memories, core_def.memory_aliases,
							core_def.register_banks, core_def.register_aliases, fn_def.args, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of function \"%s\": %s", attr_name, fn_def.name, e)
						sys.exit(1)

				fn_def.attributes[attr_name] = ops

			behav_builder = BehaviorModelBuilder(core_def.parameters, core_def.memories, core_def.memory_aliases,
					core_def.register_banks, core_def.register_aliases, fn_def.args, core_def.functions, warned_fns)

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
						behav_builder = BehaviorModelBuilder(core_def.parameters, core_def.memories, core_def.memory_aliases,
							core_def.register_banks, core_def.register_aliases, {}, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of instruction \"%s\": %s", attr_name, block_def.name, e)
						sys.exit(1)

				block_def.attributes[attr_name] = ops

			behav_builder = BehaviorModelBuilder(core_def.parameters, core_def.memories, core_def.memory_aliases,
				core_def.register_banks, core_def.register_aliases, {}, core_def.functions, warned_fns)

			try:
				op = behav_builder.visit(block_def.operation)
			except M2Error as e:
				logger.critical("error building behavior for always block %s: %s", block_def.name, e)
				sys.exit(1)

			always_block_statements.append(op)

		logger.debug("generating instruction behavior")

		assert isinstance(core_def.instructions, list)
		instructions_by_enc = {}
		overwritten_instrs: "list[tuple[arch.Instruction, arch.Instruction]]" = []
		# for instr_def in core_def.instructions.values():
		for instr_def in core_def.instructions:
			logger.debug("generating instruction %s", instr_def.name)
			logger.debug("generating attributes")

			for attr_name, attr_ops in instr_def.attributes.items():
				ops = []
				for attr_op in attr_ops:
					try:
						behav_builder = BehaviorModelBuilder(core_def.parameters, core_def.memories, core_def.memory_aliases,
							core_def.register_banks, core_def.register_aliases, instr_def.fields, core_def.functions, warned_fns)
						op = behav_builder.visit(attr_op)
						ops.append(op)
					except M2Error as e:
						logger.critical("error processing attribute \"%s\" of instruction \"%s\": %s", attr_name, instr_def.name, e)
						sys.exit(1)

				instr_def.attributes[attr_name] = ops
			if attribute_info.InstrAttribute.ENABLE in instr_def.attributes:
				enable_attr = instr_def.attributes[attribute_info.InstrAttribute.ENABLE]
				assert isinstance(enable_attr, list)
				assert len(enable_attr) == 1
				enable_attr = enable_attr[0]
				enable = try_eval_bool(enable_attr, core_def.parameters, core_def.memories, core_def.memory_aliases, instr_def.fields, core_def.functions, warned_fns)
				if enable is not None:
					assert isinstance(enable, bool)
					instr_def.attributes.pop(attribute_info.InstrAttribute.ENABLE)
					if not enable:
						continue

			behav_builder = BehaviorModelBuilder(core_def.parameters, core_def.memories, core_def.memory_aliases,
				core_def.register_banks, core_def.register_aliases, instr_def.fields, core_def.functions, warned_fns)

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
					behav.Literal(int(instr_def.size/8), type_info.TypeKind.UINT)
				)
			)

			#op.statements.insert(0, pc_inc)
			op.statements = always_block_statements + op.statements
			instr_def.operation = op
			instr_id = (instr_def.code, instr_def.mask)
			# check for duplicate instructions
			if instr_id in instructions_by_enc:
				overwritten_instrs.append((instructions_by_enc[instr_id], instr_def))
			instructions_by_enc[instr_id] = instr_def
		core_def.instructions = instructions_by_enc
		assert isinstance(core_def.instructions, dict)
		for orig, overwritten in overwritten_instrs:
			logger.warning("instr %s from extension %s was overwritten by %s from %s", orig.name, orig.ext_name, overwritten.name, overwritten.ext_name)

	model_obj = M2Model(
		M2_METAMODEL_VERSION,
		models,
		{},
		CodeInfoBase.database
	)

	warnings_info = args.warnings
	if args.infer_types or args.validate:
		logger.info("Running type inference")
		model_obj = infer_types(model_obj, warnings_info=warnings_info)
	if args.validate:
		logger.info("Running validator")
		validate_behav(model_obj, warnings_info)

	logger.info("dumping model")
	with open(model_path / (abs_top_level.stem + '.m2isarmodel'), 'wb') as f:

		pickle.dump(model_obj, f)


if __name__ == '__main__':
	main()
