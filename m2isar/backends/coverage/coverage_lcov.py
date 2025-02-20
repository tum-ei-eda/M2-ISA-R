# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2024
# Chair of Electrical Design Automation
# Technical University of Munich

import argparse
import logging
import os
import pathlib
import pickle
from collections import defaultdict
from functools import partial

from tqdm.contrib.concurrent import process_map

from ...metamodel import M2_METAMODEL_VERSION, M2Model, patch_model
from ...metamodel.code_info import (BranchInfo, CodeInfoBase, FunctionInfo,
                                    LineInfo)
from ...metamodel.utils.expr_preprocessor import (process_attributes,
                                                  process_functions,
                                                  process_instructions)
from . import id_transform
from .utils import IdMatcherContext

logger = logging.getLogger("coverage_lcov")

def generate_coverage(line_data_fname: "pathlib.Path", code_infos: "dict[int, CodeInfoBase]", line_counts_by_core_and_file, fn_counts_by_core_and_file, branch_counts_by_core_and_file):
	line_data_path = pathlib.Path(line_data_fname)
	logger.debug("processing file %s", line_data_path.name)
	logger.debug("reading line data")

	linedata: "dict[CodeInfoBase, int]" = {}
	with open(line_data_path, 'r') as f:
		core_name = f.readline().strip()
		f.readline()
		for line in f:
			l_id, count = line.strip().split(";")
			linedata[code_infos[int(l_id)]] = int(count)

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
		if isinstance(lineinfo, BranchInfo):
			branch_counts_by_core_and_file[core_name][lineinfo.file_path][lineinfo.id] += count

		if isinstance(lineinfo, LineInfo):
			if already_checked(checked_lineinfo, lineinfo, count):
				continue

			checked_lineinfo[lineinfo] = count

			linedata_of_this_file[lineinfo.file_path][lineinfo.start_line_no] = count

		elif isinstance(lineinfo, FunctionInfo):
			if already_checked(checked_fninfo, lineinfo, count):
				continue

			checked_fninfo[lineinfo] = count

			fn_counts_by_core_and_file[core_name][lineinfo.file_path][lineinfo.fn_name] += count

	for filepath, lines in linedata_of_this_file.items():
		for line_no, line_count in lines.items():
			line_counts_by_core_and_file[core_name][filepath][line_no] += line_count

	return line_counts_by_core_and_file, fn_counts_by_core_and_file, branch_counts_by_core_and_file

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
	parser.add_argument("-j", "--parallel", type=int, default=os.cpu_count())
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
		cores_to_use = {arch_name: model_obj.cores[arch_name] for arch_name in args.target_arch}
		model_obj.cores = cores_to_use

	logger.info("preprocessing models")

	for core_name, core_obj in model_obj.cores.items():
		process_functions(core_obj)
		process_instructions(core_obj)
		process_attributes(core_obj)

	logger.info("building model-specific coverage database")

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


	logger.info("initializing coverage counters")

	line_counts_by_core_and_file: dict[str, dict[str, dict[int, int]]] = defaultdict(lambda: defaultdict(dict))
	fn_counts_by_core_and_file: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
	fnmeta_by_core_and_file: dict[str, dict[str, dict[str, tuple[int, int]]]] = defaultdict(lambda: defaultdict(dict))
	branch_counts_by_core_and_file: dict[str, dict[str, dict[int, int]]] = defaultdict(lambda: defaultdict(dict))
	branchmeta_by_core_and_file: dict[str, dict[str, dict[int, list[BranchInfo]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

	for core_name, objs in ctx.id_to_obj_map.items():
		for id, owner in objs.items():
			codeinfo = model_obj.code_infos[id]

			if isinstance(codeinfo, LineInfo):
				line_counts_by_core_and_file[core_name][codeinfo.file_path][codeinfo.start_line_no] = 0

			elif isinstance(codeinfo, FunctionInfo):
				fn_counts_by_core_and_file[core_name][codeinfo.file_path][codeinfo.fn_name] = 0
				fnmeta_by_core_and_file[core_name][codeinfo.file_path][codeinfo.fn_name] = (codeinfo.start_line_no, codeinfo.stop_line_no)

			if isinstance(codeinfo, BranchInfo):
				branch_counts_by_core_and_file[core_name][codeinfo.file_path][codeinfo.id] = 0
				branchmeta_by_core_and_file[core_name][codeinfo.file_path][codeinfo.branch_id].append(codeinfo)

	def dictconv(d: dict):
		ret = dict(d)

		for k, v in ret.items():
			if isinstance(v, dict):
				ret[k] = dictconv(v)

		return ret

	line_counts_by_core_and_file = dictconv(line_counts_by_core_and_file)
	fn_counts_by_core_and_file = dictconv(fn_counts_by_core_and_file)
	branch_counts_by_core_and_file = dictconv(branch_counts_by_core_and_file)

	logger.info("generating coverage")

	out = process_map(partial(generate_coverage, code_infos=model_obj.code_infos, line_counts_by_core_and_file=line_counts_by_core_and_file, fn_counts_by_core_and_file=fn_counts_by_core_and_file, branch_counts_by_core_and_file=branch_counts_by_core_and_file), args.line_data, max_workers=args.parallel)

	def update(d: dict[str, dict[str, dict[int, int]]], u: dict[str, dict[str, dict[int, int]]]):
		for core_name, data in u.items():
			for filepath, lines in data.items():
				for line_no, line_count in lines.items():
					d[core_name][filepath][line_no] += line_count

	for ret_line_data, ret_fn_data, ret_branch_data in out:
		update(line_counts_by_core_and_file, ret_line_data)
		update(fn_counts_by_core_and_file, ret_fn_data)
		update(branch_counts_by_core_and_file, ret_branch_data)

	logger.info("writing output")
	for core_name, linedata_by_file in line_counts_by_core_and_file.items():
		with open(f"{core_name}.{args.outfile}", 'w') as f:
			for filepath, lines in linedata_by_file.items():
				f.write("TN:\n")
				f.write(f"SF:{filepath}\n")

				branch_hit_counter = 0
				line_hit_counter = 0
				fn_hit_counter = 0

				for branch_id, branch_infos in branchmeta_by_core_and_file[core_name][filepath].items():
					total_count = branch_counts_by_core_and_file[core_name][filepath][branch_infos[0].id]
					taken_counts = [branch_counts_by_core_and_file[core_name][filepath][x.id] for x in branch_infos[1:]]

					remaining_count = total_count

					branch_data = []

					for count, branch_info in zip(taken_counts, branch_infos[1:]):
						# line no, taken, not taken
						d = (branch_info.start_line_no, count, remaining_count - count)

						branch_hit_counter += count > 0 + (remaining_count - count) > 0

						f.write(f"BRDA:{branch_info.start_line_no},0,0,{count if remaining_count > 0 else '-'}\n")
						f.write(f"BRDA:{branch_info.start_line_no},0,1,{remaining_count - count if remaining_count > 0 else '-'}\n")

						lines[branch_info.start_line_no] = remaining_count

						branch_data.append(d)
						remaining_count -= count


				f.write(f"BRF:{len(branchmeta_by_core_and_file[core_name][filepath])}\n")
				f.write(f"BRH:{branch_hit_counter}\n")

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

				for fn_name, fn_count in fn_counts_by_core_and_file[core_name][filepath].items():
					f.write(f"FNDA:{fn_count},{fn_name}\n")

					if fn_count > 0:
						fn_hit_counter += 1

				f.write(f"FNF:{len(fnmeta_by_core_and_file[core_name][filepath])}\n")
				f.write(f"FNH:{fn_hit_counter}\n")

				f.write("end_of_record\n")

if __name__ == "__main__":
	main()
