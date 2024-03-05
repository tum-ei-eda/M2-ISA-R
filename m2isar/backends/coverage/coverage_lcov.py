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

from ...metamodel import LineInfo

logger = logging.getLogger("coverage_lcov")

def main():
	"""Main app entrypoint."""

	# read command line args
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .lineinfo file containing the line info database.")
	parser.add_argument('line_data', help="The CSV line data file matching the model.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
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
		model_fname = model_path / (abs_top_level.stem + '.lineinfo')

	logger.info("loading models")

	with open(model_fname, 'rb') as f:
		lineinfos: "dict[int, LineInfo]" = pickle.load(f)

	line_data_path = pathlib.Path(args.line_data)
	abs_line_data = line_data_path.resolve()
	output_base_path = abs_line_data.parent


	linedata: "dict[LineInfo, int]" = {}
	with open(line_data_path, 'r') as f:
		f.readline()
		for line in f:
			l_id, count = line.strip().split(";")
			linedata[lineinfos[int(l_id)]] = int(count)

	linedata_by_file = defaultdict(dict)

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

		linedata_by_file[lineinfo.file_path][lineinfo.start_line_no] = count

	for lineinfo in tqdm(lineinfos.values()):
		if already_checked(lineinfo, 0):
			continue

		checked_lineinfo[lineinfo] = 0

		linedata_by_file[lineinfo.file_path][lineinfo.start_line_no] = 0

	with open(output_base_path / (abs_line_data.stem + '.info'), 'w') as f:
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
