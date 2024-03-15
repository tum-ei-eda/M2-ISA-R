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

from ...metamodel import M2_METAMODEL_VERSION, M2Model, patch_model
from ...metamodel.code_info import CodeInfoBase, FunctionInfo, LineInfo
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
	parser.add_argument('top_level', help="A .m2isar file containing model.")
	parser.add_argument('line_data', help="The CSV line data files matching the model.", nargs="+")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	parser.add_argument("--legacy", action="store_true", help="Generate data for LOCV version < 2.0")
	parser.add_argument("-o", "--outfile", required=True)
	parser.add_argument("-a", "--target-arch", action="append")
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

	if args.target_arch is not None:
		models_to_use = {arch_name: model_obj.models[arch_name] for arch_name in args.target_arch}
		model_obj.models = models_to_use

	logger.info("preprocessing models")

	for core_name, core_obj in model_obj.models.items():
		process_functions(core_obj)
		process_instructions(core_obj)
		process_attributes(core_obj)

	logger.info("building model-specific coverage database")

	patch_model(id_transform)

	ctx = IdMatcherContext()

	for core_name, core_obj in model_obj.models.items():
		ctx.arch_name = core_name

		for fn_name, fn_obj in core_obj.functions.items():
			if fn_obj.function_info is not None:
				ctx.id_to_obj_map[core_name][fn_obj.function_info.id] = fn_obj

			fn_obj.operation.generate(ctx)

		for instr_name, instr_obj in core_obj.instructions.items():
			ctx.id_to_obj_map[core_name][instr_obj.function_info.id] = instr_obj

			instr_obj.operation.generate(ctx)


	logger.info("initializing coverage counters")

	linedata_by_core_and_file = defaultdict(lambda: defaultdict(dict))
	fndata_by_core_and_file = defaultdict(lambda: defaultdict(dict))
	fnmeta_by_core_and_file = defaultdict(lambda: defaultdict(dict))

	for core_name, objs in ctx.id_to_obj_map.items():
		for id, owner in objs.items():
			codeinfo = model_obj.code_infos[id]

			if isinstance(codeinfo, LineInfo):
				linedata_by_core_and_file[core_name][codeinfo.file_path][codeinfo.start_line_no] = 0

			elif isinstance(codeinfo, FunctionInfo):
				fndata_by_core_and_file[core_name][codeinfo.file_path][codeinfo.fn_name] = 0
				fnmeta_by_core_and_file[core_name][codeinfo.file_path][codeinfo.fn_name] = (codeinfo.start_line_no, codeinfo.stop_line_no)


	logger.info("generating coverage")

	for line_data_fname in tqdm(args.line_data):
		line_data_path = pathlib.Path(line_data_fname)

		logger.debug("processing file %s", line_data_path.name)


		logger.debug("reading line data")

		linedata: "dict[CodeInfoBase, int]" = {}
		with open(line_data_path, 'r') as f:
			core_name = f.readline().strip()
			f.readline()
			for line in f:
				l_id, count = line.strip().split(";")
				linedata[model_obj.code_infos[int(l_id)]] = int(count)

		checked_lineinfo = {}
		checked_fninfo = {}

		def already_checked(to_check, l: LineInfo, count):
			for l2, count2 in to_check.items():
				if l.line_eq(l2):
					if count > count2:
						return False
					elif count < count2:
						return True
					else:
						return True

			return False

		linedata_of_this_file = defaultdict(dict)

		for lineinfo, count in linedata.items():
			if isinstance(lineinfo, LineInfo):
				if already_checked(checked_lineinfo, lineinfo, count):
					continue

				checked_lineinfo[lineinfo] = count

				linedata_of_this_file[lineinfo.file_path][lineinfo.start_line_no] = count

			elif isinstance(lineinfo, FunctionInfo):
				if already_checked(checked_fninfo, lineinfo, count):
					continue

				checked_fninfo[lineinfo] = count

				fndata_by_core_and_file[core_name][lineinfo.file_path][lineinfo.fn_name] += count

		for filepath, lines in linedata_of_this_file.items():
			for line_no, line_count in lines.items():
				linedata_by_core_and_file[core_name][filepath][line_no] += line_count

	logger.info("writing output")
	for core_name, linedata_by_file in linedata_by_core_and_file.items():
		with open(f"{core_name}.{args.outfile}", 'w') as f:
			for filepath, lines in linedata_by_file.items():
				f.write("TN:\n")
				f.write(f"SF:{filepath}\n")

				line_hit_counter = 0
				fn_hit_counter = 0

				for line_no, line_count in sorted(lines.items()):
					f.write(f"DA:{line_no},{line_count}\n")

					if line_count > 0:
						line_hit_counter += 1

				f.write(f"LF:{len(lines)}\n")
				f.write(f"LH:{line_hit_counter}\n")

				for fn_name, (fn_start, fn_stop) in fnmeta_by_core_and_file[core_name][filepath].items():
					if args.legacy:
						f.write(f"FN:{fn_start},{fn_name}\n")
					else:
						f.write(f"FN:{fn_start},{fn_stop},{fn_name}\n")

				for fn_name, fn_count in fndata_by_core_and_file[core_name][filepath].items():
					f.write(f"FNDA:{fn_count},{fn_name}\n")

					if fn_count > 0:
						fn_hit_counter += 1

				f.write(f"FNF:{len(fnmeta_by_core_and_file[core_name][filepath])}\n")
				f.write(f"FNH:{fn_hit_counter}\n")

				f.write("end_of_record\n")

if __name__ == "__main__":
	main()
