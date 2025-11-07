# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Actual text output functions for functions and instructions."""

import logging
import pathlib
from contextlib import ExitStack

from mako.template import Template

from ...metamodel import arch
from . import BlockEndType
from .instruction_generator import generate_functions, generate_instructions
from .templates import template_dir

logger = logging.getLogger("instruction_writer")

def write_functions(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, static_scalars: bool, generate_coverage: bool):
	"""Generate and write the {CoreName}Funcs.h file for ETISS."""

	fn_set_header_template = Template(filename=str(template_dir/'etiss_function_set_header.mako'))
	fn_set_footer_template = Template(filename=str(template_dir/'etiss_function_set_footer.mako'))
	fn_impl_template = Template(filename=str(template_dir/"etiss_functions_c.mako"))

	core_name = core.name

	logger.info("writing functions")

	with open(output_path / f'{core_name}Funcs.h', 'w', encoding="utf-8") as funcs_f:
		# generate and write file header
		fn_set_str = fn_set_header_template.render(
			start_time=start_time,
			core_name=core_name,
			enable_coverage=generate_coverage,
		)

		funcs_f.write(fn_set_str)
		funcs_f.write("    // clang-format off\n")

		# generate and write function declarations
		for fn_name, templ_str in generate_functions(core, static_scalars, True, generate_coverage):
			logger.debug("writing function decl %s", fn_name)
			funcs_f.write(templ_str)

		fn_set_str = fn_set_footer_template.render()

		funcs_f.write("\n    // clang-format on\n")
		funcs_f.write(fn_set_str)

	with open(output_path / f'{core_name}Funcs.c', 'w', encoding="utf-8") as funcs_f:
		fn_impl_str = fn_impl_template.render(
			start_time=start_time,
			core_name=core_name
		)

		funcs_f.write(fn_impl_str)
		funcs_f.write("// clang-format off\n")

		# generate and write function definitions
		for fn_name, templ_str in generate_functions(core, static_scalars, False, generate_coverage):
			logger.debug("writing function def %s", fn_name)
			funcs_f.write(templ_str)
		funcs_f.write("// clang-format on\n")

def write_instructions(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, separate: bool, static_scalars: bool,
	block_end_on: BlockEndType, generate_coverage: bool):
	"""Generate and write the instruction model C++ files for ETISS."""

	instr_set_template = Template(filename=str(template_dir/'etiss_instruction_set.mako'))

	outfiles = {}
	core_name = core.name

	logger.info("writing instructions")

	with ExitStack() as stack:
		# if desired use one C++ file for each instruction set extension
		if separate:
			outfiles = {
				ext_name: stack.enter_context(open(output_path / f'{core_name}_{ext_name}Instr.cpp', 'w', encoding="utf-8"))
				for ext_name in core.contributing_types if len(core.instructions_by_ext[ext_name]) > 0
			}

		# open a default file
		outfiles['default'] = stack.enter_context(open(output_path / f'{core_name}Instr.cpp', 'w', encoding="utf-8"))
		for outfile in outfiles.values():
			outfile.write("// clang-format off\n")

		# generate file headers for each file
		for extension_name, out_f in outfiles.items():
			instr_set_str = instr_set_template.render(
				start_time=start_time,
				extension_name=extension_name,
				core_name=core_name
			)

			out_f.write(instr_set_str)

		# generate instruction behavior models
		for instr_name, _, ext_name, templ_str in generate_instructions(core, static_scalars, block_end_on, generate_coverage):
			logger.debug("writing instruction %s", instr_name)
			outfiles.get(ext_name, outfiles['default']).write(templ_str)
		for outfile in outfiles.values():
			outfile.write("// clang-format on\n")
