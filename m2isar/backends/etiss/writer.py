# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Main entrypoint for the etiss_writer program."""

import re
import argparse
import logging
import pathlib
import pickle
import shutil
import time

from ...metamodel import M2_METAMODEL_VERSION, M2Model
from ...metamodel.utils.expr_preprocessor import (process_attributes,
                                                  process_functions,
                                                  process_instructions)
from . import BlockEndType, CodeInfoTracker
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
	parser.add_argument("--coverage", action=BooleanOptionalAction, default=False, help="Generate coverage tracking code into model.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	parser.add_argument("--gdb-xml-descr", nargs="+", default=[])
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
		model_obj: M2Model = pickle.load(f)

	if model_obj.model_version != M2_METAMODEL_VERSION:
		logger.warning("Loaded model version mismatch")

	start_time = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.localtime())

	assert len(model_obj.cores) > 0, "No cores found in metamodel"

	return (model_obj.cores, logger, output_base_path, spec_name, start_time, args)


def process_xml_descr(path):
	import xml.etree.ElementTree as ET
	from xml.etree import ElementTree, ElementInclude
	# print("process_xml_descr", path)
	tree = ElementTree.parse(path)
	# print("tree", tree)
	root = tree.getroot()
	# print("root", root)
	parent = pathlib.Path(path).parent
	def custom_loader(href, parse, encoding=None):
		if not pathlib.Path(href).is_file():
			href = parent / href
		if parse == "xml":
			with open(href, 'rb') as file:
				data = ElementTree.parse(file).getroot()
		else:
			if not encoding:
				encoding = 'UTF-8'
			with open(href, 'r', encoding=encoding) as file:
				data = file.read()
		return data
	ElementInclude.include(root, loader=custom_loader)
	mapping = {}
	num = 0
	for node in tree.iter():
		if node.tag == "reg":
			# print("node", node.tag, node.attrib)
			num = int(node.attrib.get("regnum", num + 1))
			name = node.attrib["name"]
			sz = int(node.attrib["bitsize"])
			mapping[num] = (name, sz)
	# print("mapping", mapping)
	# input(">>>")
	return mapping

def main():
	"""etiss_writer main entrypoint function."""

	# setup etiss writer
	cores, logger, output_base_path, spec_name, start_time, args = setup()
	descr_mapping = {}
	for descr in args.gdb_xml_descr:
		assert ":" in descr
		core, xml_path = descr.split(":", 1)
		print("core", core)
		assert core in cores
		mapping = process_xml_descr(xml_path)
		descr_mapping[core] = mapping

	# preprocess all models
	for core_name, core in cores.items():
		logger.info("preprocessing model %s", core_name)
		process_functions(core)
		process_instructions(core)
		process_attributes(core)

		renamed_fns = {}

		for fn_name, fn_def in core.functions.items():
			if fn_def.extern:
				renamed_fns[fn_name] = fn_def
			else:
				new_name = f"{core_name}_{fn_def.name}"
				fn_def.name = new_name
				renamed_fns[new_name] = fn_def

		core.functions = renamed_fns

	# generate each core in the model
	for core_name, core in cores.items():
		logger.info("processing model %s", core_name)
		# print("core.memories", core.memories)
		# print("core.memory_aliases", core.memory_aliases)
		mapping = descr_mapping.get(core_name)
		# print("mapping", mapping)
		# assert mapping is not None
		if mapping is not None:
			default_aliases = {"zero": "x0", "ra": "x1", "sp": "x2", "gp": "x3", "tp": "x4", "t0": "x5", "t1": "x6", "t2": "x7", "s0": "x8", "fp": "x8", "s1": "x9", "a0": "x10", "a1": "x11", "a2": "x12", "a3": "x13", "a4": "x14", "a5": "x15", "a6": "x16", "a7": "x17", "s2": "x18", "s3": "x19", "s4": "x20", "s5": "x21", "s6": "x22", "s7": "x23", "s8": "x24", "s9": "x25", "s10": "x26", "s11": "x27", "t3": "x28", "t4": "x29", "t5": "x30", "t6": "x31"}
			def resolve_reg(name, mems, aliases):
				split_name = lambda s: (m.group(1), int(m.group(2))) if (m:=re.fullmatch(r'([a-zA-Z]+)(\d+)', s)) else None
				# print("resolve_reg", name)
				idx = None
				ret = mems.get(name, mems.get(name.lower(), mems.get(name.upper())))
				if ret is None:
					ret = aliases.get(name, aliases.get(name.lower(), aliases.get(name.upper())))
				if ret is None:
					splitted = split_name(name)
					if splitted is not None:
						# print("splitted", splitted)
						name, idx = splitted
						# print("name", name)
						# print("idx", idx)
						ret = mems.get(name, mems.get(name.lower(), mems.get(name.upper())))
						# print("ret", ret)
						if ret is None:
								ret = aliases.get(name, aliases.get(name.lower(), aliases.get(name.upper())))
						# input("?")
				if ret is None:
					new_name = default_aliases.get(name, default_aliases.get(name.lower(), default_aliases.get(name.upper())))
					if new_name is not None:
						return resolve_reg(new_name, mems, aliases)
				return ret, idx
			for regnum, data in mapping.items():
				# print("regnum,data", regnum, data)
				name, sz = data
				resolved = resolve_reg(name, core.memories, core.memory_aliases)
				# print("resolved", resolved)
				# print("resolved[0]", dir(resolved[0]))
				# print("resolved[0].children", resolved[0].children)
				# print("resolved[0].parent", resolved[0].parent)
				# print("resolved[0].range", resolved[0].range)
				# print("resolved[0].size", resolved[0].size)
				assert resolved is not None
				if resolved is not None:
					mem, idx = resolved
					assert mem is not None
					if mem.parent is not None:  # alias
						rng = mem.range
						assert rng.length == 1
						assert idx is None
						idx = rng.lower
						mem = mem.parent
					assert mem.size == sz
					print("regnum,mem,idx", regnum, mem, idx)

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
		write_functions(core, start_time, output_path, args.static_scalars, args.coverage)
		write_instructions(core, start_time, output_path, args.separate, args.static_scalars, BlockEndType[args.block_end_on.upper()], args.coverage)

		with open(output_path / "coverage.csv", "w") as f:
			for c_id, c_info in sorted(CodeInfoTracker.tracker[core_name].items()):
				f.write(f"{c_id}\n")

if __name__ == "__main__":
	main()
