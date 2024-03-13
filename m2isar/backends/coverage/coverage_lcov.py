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

logger = logging.getLogger("coverage_lcov")

def main():
	"""Main app entrypoint."""

	# read command line args
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .lineinfo file containing the line info database.")
	parser.add_argument('line_data', help="The CSV line data file matching the model.", nargs="+")
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
		line_data_path = pathlib.Path(line_data_fname)

		linedata: "dict[LineInfo, int]" = {}
		with open(line_data_path, 'r') as f:
			f.readline()
			for line in f:
				l_id, count = line.strip().split(";")
				linedata[lineinfos[int(l_id)]] = int(count)

		checked_lineinfo = {}

		def already_checked(l: LineInfo, count):
			for l2, count2 in checked_lineinfo.items():
				if l.line_eq(l2):
					return True
			return False

		for lineinfo, count in tqdm(linedata.items()):
			if already_checked(lineinfo, count):
				continue

			checked_lineinfo[lineinfo] = count

			linedata_by_file[lineinfo.file_path][lineinfo.start_line_no] += count

	with open(args.outfile, 'w') as f:
		for filepath, lines in tqdm(linedata_by_file.items()):
			f.write("TN:\n")
			f.write(f"SF:{filepath}\n")

			hit_counter = 0

			for line_no, line_count in sorted(lines.items()):
				f.write(f"DA:{line_no},{line_count}\n")

				if line_count > 0:
					hit_counter += 1

			f.write(f"LF:{len(lines)}\n")
			f.write(f"LH:{hit_counter}\n")
			f.write("end_of_record\n")




if __name__ == "__main__":
	main()
