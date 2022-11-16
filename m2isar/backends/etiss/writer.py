# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Main entrypoint for the etiss_writer program."""

import argparse
import logging
import pathlib
import pickle
import shutil
import time

from m2isar.metamodel.arch import CoreDef

from ...metamodel.utils.expr_preprocessor import (process_functions,
												  process_instructions)
from . import BlockEndType
from .architecture_writer import (write_arch_cmake, write_arch_cpp,
								  write_arch_gdbcore, write_arch_header,
								  write_arch_lib, write_arch_specific_cpp,
								  write_arch_specific_header,
								  write_arch_struct)
from .instruction_writer import write_functions, write_instructions


class BooleanOptionalAction(argparse.Action):
	"""A boolean optional action for argparse, supports automatic generation of --no-x flags."""

	def __init__(self,
				 option_strings,
				 dest,
				 default=None,
				 type_=None,
				 choices=None,
				 required=False,
				 help=None,
				 metavar=None):

		_option_strings = []
		for option_string in option_strings:
			_option_strings.append(option_string)

			if option_string.startswith('--'):
				option_string = '--no-' + option_string[2:]
				_option_strings.append(option_string)

		if help is not None and default is not None and default is not argparse.SUPPRESS:
			help += " (default: %(default)s)"

		super().__init__(
			option_strings=_option_strings,
			dest=dest,
			nargs=0,
			default=default,
			type=type_,
			choices=choices,
			required=required,
			help=help,
			metavar=metavar)

	def __call__(self, parser, namespace, values, option_string=None):
		if option_string in self.option_strings:
			setattr(namespace, self.dest, not option_string.startswith('--no-'))

	def format_usage(self):
		return ' | '.join(self.option_strings)


def setup():
	"""Setup a M2-ISA-R metamodel consumer. Create an argument parser, unpickle the model
	and generate output file structure.
	"""

	# read command line arguments
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .m2isarmodel file containing the models to generate.")
	parser.add_argument('--separate', action=BooleanOptionalAction, default=True, help="Generate separate .cpp files for each instruction set.")
	parser.add_argument("--static-scalars", action=BooleanOptionalAction, default=True, help="Enable static detection for scalars.")
	parser.add_argument("--block-end-on", default="none", choices=[x.name.lower() for x in BlockEndType],
		help="Force end translation blocks on no instructions, uncoditional jumps or all jumps.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	args = parser.parse_args()

	# configure logging
	logging.basicConfig(level=getattr(logging, args.log.upper()))
	logger = logging.getLogger("etiss_writer")

	# resolve model paths
	top_level = pathlib.Path(args.top_level)
	abs_top_level = top_level.resolve()
	search_path = abs_top_level.parent.parent
	model_fname = abs_top_level

	if abs_top_level.suffix == ".core_desc":
		logger.warning(".core_desc file passed as input. This is deprecated behavior, please change your scripts!")
		search_path = abs_top_level.parent
		model_path = search_path.joinpath('gen_model')

		if not model_path.exists():
			raise FileNotFoundError('Models not generated!')
		model_fname = model_path / (abs_top_level.stem + '.m2isarmodel')

	# create top level output directory
	spec_name = abs_top_level.stem
	output_base_path = search_path.joinpath('gen_output')
	output_base_path.mkdir(exist_ok=True)

	logger.info("loading models")

	with open(model_fname, 'rb') as f:
		models: "dict[str, CoreDef]" = pickle.load(f)

	start_time = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.localtime())

	return (models, logger, output_base_path, spec_name, start_time, args)

def main():
	"""etiss_writer main entrypoint function."""

	# setup etiss writer
	models, logger, output_base_path, spec_name, start_time, args = setup()

	# preprocess all models
	for core_name, core in models.items():
		logger.info("preprocessing model %s", core_name)
		process_functions(core)
		process_instructions(core)

	# generate each core in the model
	for core_name, core in models.items():
		logger.info("processing model %s", core_name)

		# create output files path
		output_path = output_base_path / spec_name / core_name
		try:
			output_path.mkdir(parents=True)
		except FileExistsError:
			shutil.rmtree(output_path)
			output_path.mkdir(parents=True)

		# generate and write files
		write_arch_struct(core, start_time, output_path)
		write_arch_header(core, start_time, output_path)
		write_arch_cpp(core, start_time, output_path, False)
		write_arch_specific_header(core, start_time, output_path)
		write_arch_specific_cpp(core, start_time, output_path)
		write_arch_lib(core, start_time, output_path)
		write_arch_cmake(core, start_time, output_path, args.separate)
		write_arch_gdbcore(core, start_time, output_path)
		write_functions(core, start_time, output_path, args.static_scalars)
		write_instructions(core, start_time, output_path, args.separate, args.static_scalars, BlockEndType[args.block_end_on.upper()])

if __name__ == "__main__":
	main()
