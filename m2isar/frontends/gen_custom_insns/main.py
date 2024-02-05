"""Generate a set of M2-ISA-R metamodel Instructions from a yaml file"""
import argparse
import logging
import pathlib
import pickle
import subprocess
from typing import Dict, List

from m2isar.frontends.gen_custom_insns import input_parser

from ...metamodel import arch
from .instructions_classes import Instruction

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
		default="cdsl",
		choices=["cdsl"],
		help="""Directly calls the coredsl backend""",  # Could add the other backends in the future
	)
	args = parser.parse_args()

	# Setting up basic logger
	logging.basicConfig(level=getattr(logging, args.log.upper()))

	# parse input
	logger.info("Parsing input...")
	filename = pathlib.Path(args.filename)
	metadata, raw_instructions = input_parser.parse(filename)
	logger.debug(metadata)

	# generating instruction objects
	processed_instructions: List[Instruction] = []
	for inst in raw_instructions:
		processed_instructions.extend(inst.generate())
	logger.info("Created %i instructions.", len(processed_instructions))
	# transforming into metamodel
	mm_instructions = [i.to_metamodel(metadata.prefix) for i in processed_instructions]

	# parsing output path
	if args.output is None:
		out_path = filename.parent / (filename.stem)
	else:
		out_path = pathlib.Path(args.output)

	# Generating m2isar models
	## parse required extension into the coredsl equivalent
	if metadata.extends is None:
		extends = []
	else:
		extends = to_coredsl_name(metadata.extends, metadata.xlen)

	constants = {
		"XLEN": arch.Constant(
			"XLEN", value=metadata.xlen, attributes={}, size=None, signed=False
		)
	}
	memories = create_memories(metadata.xlen)

	instructions_dict = {(inst.mask, inst.code): inst for inst in mm_instructions}

	model = {
		"sets": {
			metadata.ext_name: arch.InstructionSet(
				name=metadata.ext_name,
				extension=extends,
				constants=constants,
				memories=memories,
				functions={},
				instructions=instructions_dict,
			)
		}
	}

	# if enabled add a core to the dumped model
	if args.core:
		assert metadata.core_name is not None

		# std extensions
		contributing_types = to_coredsl_name(metadata.used_extensions, metadata.xlen)
		# generated instructions
		contributing_types.append(metadata.ext_name)
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

		instr_classes = set()
		if metadata.xlen == 32:
			instr_classes.add(32)
		if metadata.xlen == 64:
			instr_classes.add(64)
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
			instructions=instructions_dict,
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
