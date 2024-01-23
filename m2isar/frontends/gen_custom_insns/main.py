"""Generate a set of M2-ISA-R metamodel Instructions from a yaml file"""
import argparse
import pickle
import pathlib
import logging
from typing import List, Dict, Tuple

from .input_parser import parse
from .instructions_classes import Instruction
from ...metamodel import arch


logger = logging.getLogger("Instruction Gen")


def create_dummy_core(
	memories: Dict[str, arch.Memory],
	instructions: Dict[Tuple[int, int], arch.Instruction],
	constants: Dict[str, arch.Constant],
) -> arch.CoreDef:
	"""Create a dummy core for M2-ISA-R"""
	functions = {}
	intrinsics = {}
	name = "DummyCore"
	contributing_types = ["MySet"]  # TODO replace with groups specified in yaml
	dummy_core = arch.CoreDef(
		name=name,
		contributing_types=contributing_types,
		template=None,  # type: ignore
		constants=constants,
		memories=memories,
		memory_aliases={},
		functions=functions,
		instructions=instructions,
		instr_classes={32},
		intrinsics=intrinsics,
	)
	return dummy_core


def create_memories() -> Dict[str, arch.Memory]:
	"""create memory sections for the dummy core"""
	main_reg = arch.Memory(
		"X",
		arch.RangeSpec(32),
		size=32,
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
		size=32,
		attributes={arch.MemoryAttribute.IS_PC: []},
	)
	return {"X": main_reg, "MEM": main_mem, "PC": pc}


def generate_m2isar_sets(
	instructions: List[arch.Instruction], ext_name: str, extends: List[str]
) -> dict[str, arch.InstructionSet]:
	"""Create an M2isar metamodel Instruction set"""
	constants = {
		"XLEN": arch.Constant("XLEN", value=32, attributes={}, size=None, signed=False)
	}
	memories = create_memories()

	instructions_dict = {(inst.mask, inst.code): inst for inst in instructions}
	inst_set = arch.InstructionSet(
		name=ext_name,
		extension=extends,
		constants=constants,
		memories=memories,
		functions={},
		instructions=instructions_dict,
	)

	return {inst_set.name: inst_set}


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
		"-m",
		"--model",
		default="m2isar",
		choices=["m2isar", "cdsl"],
		help="""Choose the output format.\n
		The CoreDSL2 output is generated by first building the metamodel and then using the coredsl2_set backend""",
	)
	args = parser.parse_args()

	# Setting up basic logger
	logging.basicConfig(level=getattr(logging, args.log.upper()))

	# parse input
	logger.info("Parsing input...")
	filename = pathlib.Path(args.filename)
	metadata, raw_instructions = parse(filename)
	# generating instruction objects
	processed_instructions: List[Instruction] = []
	for inst in raw_instructions:
		processed_instructions.extend(inst.generate())
	logger.info("Created %i instructions.", len(processed_instructions))

	# parsing output path
	if args.output is None:
		out_path = filename.parent / (filename.stem)
	else:
		out_path = pathlib.Path(args.output)

	# output generated instructions
	if args.model == "m2isar":
		mm_instructions = [
			i.to_metamodel(metadata.prefix) for i in processed_instructions
		]

		# parse required extension into the coredsl equivalent
		cdsl_extensions = {
			"f": "RV32F",
			"m": "RV32M",
			"a": "RV32A",
			"d": "RV32D",
			"c": "RV32IC",
			"i": "RV32I",
		}
		if metadata.extends:
			extends = [
				cdsl_extensions.pop(ext)
				for ext in metadata.extends
				if ext in cdsl_extensions
			]
		else:
			extends = ["RISCVBase"]

		sets = generate_m2isar_sets(mm_instructions, metadata.ext_name, extends)
		models = {"sets": sets}

		if out_path.suffix != ".m2isarmodel":
			out_path = out_path.with_suffix(".m2isarmodel")
		with open(out_path, "wb") as file:
			logger.info("Saving instructions to '%s'", out_path.name)
			pickle.dump(models, file)

	if args.model == "cdsl2":
		raise NotImplementedError("Not currently supported!")
		# generate metamodel

		# run cdsl2 backend


if __name__ == "__main__":
	main()
