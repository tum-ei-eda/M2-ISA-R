# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2024
# Chair of Electrical Design Automation
# Technical University of Munich

import argparse
import logging
import pathlib
import pickle
from collections import defaultdict

from tqdm import tqdm

from ...metamodel import M2_METAMODEL_VERSION, M2Model, arch, patch_model
from ...metamodel.code_info import FunctionInfo, LineInfo
from ...metamodel.utils.expr_preprocessor import (process_attributes,
                                                  process_functions,
                                                  process_instructions)
from . import id_transform
from .utils import IdMatcherContext

logger = logging.getLogger("coverage_lcov")

def main():
	"""Main app entrypoint."""

	# read command line args
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .lineinfo file containing the line info database.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	parser.add_argument("-o", "--outfile", required=True)
	args = parser.parse_args()

	# initialize logging
	logging.basicConfig(level=getattr(logging, args.log.upper()))

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

	logger.info("loading models")

	with open(model_fname, 'rb') as f:
		model_obj: "M2Model" = pickle.load(f)

	if model_obj.model_version != M2_METAMODEL_VERSION:
		logger.warning("Loaded model version mismatch")

	for core_name, core_obj in model_obj.cores.items():
		process_functions(core_obj)
		process_instructions(core_obj)
		process_attributes(core_obj)


	patch_model(id_transform)

	ctx = IdMatcherContext()

	for core_name, core_obj in model_obj.cores.items():
		ctx.arch_name = core_name

		for fn_name, fn_obj in core_obj.functions.items():
			if fn_obj.function_info is not None:
				ctx.id_to_obj_map[core_name][fn_obj.function_info.id] = fn_obj

			fn_obj.operation.generate(ctx)

		for instr_name, instr_obj in core_obj.instructions.items():
			ctx.id_to_obj_map[core_name][instr_obj.function_info.id] = instr_obj

			instr_obj.operation.generate(ctx)

	id_to_obj_map = {}

	for core_name, objs in ctx.id_to_obj_map.items():
		for id, owner in objs.items():
			id_to_obj_map[id] = owner

	linedata_by_file = defaultdict(dict)
	for lineinfo in tqdm(model_obj.code_infos.values()):
		if isinstance(lineinfo, LineInfo):
			type_str = "L"
		elif isinstance(lineinfo, FunctionInfo):
			type_str = "F"

		linedata_by_file[lineinfo.file_path][lineinfo.id] = (type_str, lineinfo.start_line_no, lineinfo.stop_line_no, id_to_obj_map.get(lineinfo.id))

	for core_name, objs in ctx.id_to_obj_map.items():

		with open(f"{core_name}.csv", "w") as f:
			for id in sorted(objs):
				f.write(f"{id}\n")

	with open(args.outfile, "w") as f:
		for fname, lines in sorted(linedata_by_file.items()):
			for info_id, (type_str, start_line_no, stop_line_no, owner) in sorted(lines.items()):
				f.write(f"{type_str};{fname.stem};{info_id};{start_line_no},{stop_line_no},{owner}\n")

if __name__ == "__main__":
	main()
