"""Generate a set of M2-ISA-R metamodel Instructions from a yaml file"""

import argparse
import logging
import pathlib
import pickle
import subprocess
from typing import Dict, List

from . import input_parser
from .seal5_support import (
	GMIRLegalization,
	save_extensions_yaml,
	save_legalizations_yaml,
)

from ...metamodel import arch

logger = logging.getLogger("Instruction Gen")


def create_memories(xlen: int) -> Dict[str, arch.Memory]:
	"""create memory sections for the dummy core"""
	main_reg = arch.Memory(
		"X",
		arch.RangeSpec(32),
		size=xlen,
		attributes={arch.MemoryAttribute.IS_MAIN_REG: []},
	)
	main_mem = arch.Memory(
		"MEM",
		arch.RangeSpec(1 << 32),
		size=8,
		attributes={arch.MemoryAttribute.IS_MAIN_MEM: []},
	)
	pc = arch.Memory(
		"PC",
		arch.RangeSpec(0),
		size=xlen,
		attributes={arch.MemoryAttribute.IS_PC: []},
	)
	return {"X": main_reg, "MEM": main_mem, "PC": pc}


def main():
	"""Main app entrypoint"""
	# argument parsing
	parser = argparse.ArgumentParser(description="Instruction generator", add_help=True)
	parser.add_argument("filename", help="Name of the input file")
	parser.add_argument(
		"--log",
		default="info",
		choices=["critical", "error", "warning", "info", "debug"],
	)
	parser.add_argument("-o", "--output", default="instructions", help="Output path")
	parser.add_argument(
		"-c",
		"--core",
		action="store_true",
		help="Generate a M2-ISA-R Core. If set 'core_name' needs to be specified in the yaml file",
	)
	parser.add_argument(
		"-b",
		"--backend",
		choices=["cdsl"],
		help="Directly calls the coredsl backend",
	)
	parser.add_argument(
		"--no_seal5", action="store_true", help="Don't save legalizations for seal5"
	)
	args = parser.parse_args()

	# Setting up basic logger
	logging.basicConfig(level=getattr(logging, args.log.upper()))

	# parse input
	logger.info("Parsing input...")
	filepath = pathlib.Path(args.filename)
	metadata, raw_instruction_sets = input_parser.parse(filepath)
	logger.debug(metadata)

	# generating instruction objects
	inst_sets: dict[str, list[arch.Instruction]] = {}
	legalizations: dict[str, list[GMIRLegalization]] = {}
	inst_count = 0
	for set_name, inst_list in raw_instruction_sets.items():
		name = metadata.ext_name + "_" + set_name
		inst_sets[name] = []
		legalizations[name] = []
		for inst in inst_list:
			expanded_instructions = inst.generate()
			inst_count += len(expanded_instructions)
			for i in expanded_instructions:
				instruction, legalization = i.to_metamodel(metadata.prefix)
				inst_sets[name].append(instruction)
				if legalization:
					legalizations[name].append(legalization)

	logger.info("Created %i instructions in %i Sets.", inst_count, len(inst_sets))

	# parsing output path
	if args.output is None:
		out_path = filepath.parent / (filepath.stem)
	else:
		out_path = pathlib.Path(args.output)

	# Generating m2isar models
	## parse required extension into the coredsl equivalent
	if metadata.extends is None:
		extends = to_coredsl_name("i", metadata.xlen)
	else:
		extends = to_coredsl_name(metadata.extends, metadata.xlen)

	constants = {
		"XLEN": arch.Constant(
			"XLEN", value=metadata.xlen, attributes={}, size=None, signed=False
		)
	}
	memories = create_memories(metadata.xlen)

	m2_inst_sets = {}
	for name, mm_instructions in inst_sets.items():
		instructions_dict = {(inst.mask, inst.code): inst for inst in mm_instructions}
		
		m2_inst_sets[name] = arch.InstructionSet(
			name=name,
			extension=extends,
			constants=constants,
			memories=memories,
			functions={},
			instructions=instructions_dict,
		)

	model = {"sets": m2_inst_sets}

	# if enabled add a core to the dumped model
	if args.core:
		assert metadata.core_name is not None

		# std extensions
		contributing_types = to_coredsl_name(metadata.used_extensions, metadata.xlen)
		# generated instructions
		contributing_types.extend(m2_inst_sets.keys())
		# etiss extensions
		if metadata.core_template == "etiss":
			if metadata.xlen == 32:
				contributing_types.extend(
					["Zifencei", "tum_csr", "tum_ret", "tum_rva", "tum_semihosting"]
				)
			if metadata.xlen == 64:
				contributing_types.extend(
					[
						"Zifencei",
						"tum_csr",
						"tum_ret",
						"tum_rva64",
						"tum_rvm",
						"tum_semihosting",
					]
				)

		instr_classes = {32}
		# Not needed, dont support 64bit encodings
		# if metadata.xlen == 64:
		# 	instr_classes.add(64)
		if "c" in metadata.used_extensions:
			instr_classes.add(16)

		core = arch.CoreDef(
			name=metadata.core_name,
			contributing_types=contributing_types,
			template=None,  # type: ignore
			constants=constants,
			memories=memories,
			memory_aliases={},
			functions={},
			instructions={},  # is currently not used by the cdsl2 writer
			instr_classes=instr_classes,
			intrinsics={},
		)
		model[core.name] = core  # type: ignore , could add a 'TypedDict' to prevent this

	# output generated instructions
	if out_path.suffix != ".m2isarmodel":
		out_path = out_path.with_suffix(".m2isarmodel")
	with open(out_path, "wb") as file:
		logger.info("Saving instructions to '%s'", out_path.name)
		pickle.dump(model, file)

	if args.backend == "cdsl":
		# create model
		if out_path.suffix != ".core_desc":
			out_path = out_path.with_suffix(".core_desc")
		# run cdsl2 backend
		subprocess.run(
			[
				"python",
				"-m",
				"m2isar.backends.coredsl2_set.writer",
				out_path.with_suffix(".m2isarmodel").name,
			],
			check=True,
			text=True,
		)

	if not args.no_seal5:
		save_legalizations_yaml(
			extension=metadata.ext_name,
			legalizations=legalizations,
			path=out_path.parent,
		)
		save_extensions_yaml(
			extension_name=metadata.ext_name,
			extensions=list(m2_inst_sets.keys()),
			ext_prefix=metadata.prefix,
			path=out_path.parent,
		)


def to_coredsl_name(extensions: str, xlen: int) -> List[str]:
	"""Turns a string with standard extension names into a list with their CoreDSL2 equivalent"""
	extensions_list = []
	if "i" in extensions:
		extensions_list.append(f"RV{xlen}I")
		if "c" in extensions:
			extensions_list.append(f"RV{xlen}IC")
	if "m" in extensions:
		extensions_list.append(f"RV{xlen}M")
	if "a" in extensions:
		extensions_list.append(f"RV{xlen}A")
	if "f" in extensions:
		extensions_list.append(f"RV{xlen}F")
		if "c" in extensions:
			extensions_list.append("RV32FC")
	if "d" in extensions:
		extensions_list.append(f"RV{xlen}D")
		if "c" in extensions:
			extensions_list.append("RV32DC")

	return extensions_list


if __name__ == "__main__":
	main()
