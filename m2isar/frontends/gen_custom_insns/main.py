import argparse
import pickle
import sys
from typing import List, Dict, Tuple

from .input_parser import parse
from .instructions_classes import Instruction
import m2isar
from ...metamodel import arch, behav


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


def main():
	"""Main app entrypoint"""
	# argument parsing
	parser = argparse.ArgumentParser(description="Instruction generator", add_help=True)
	parser.add_argument("filename", help="Name of the input file")
	parser.add_argument(
		"-o", "--output", default="instructions.m2isarmodel", help="Output path"
	)
	parser.add_argument(
		"-m",
		"--model",
		default="m2isar",
		choices=["m2isar", "cdsl2"],
		help="Choose the output format",
	)
	args = parser.parse_args()

	# parse input
	# TODO get the meta data from the spec, like the extensions name
	raw_instructions = parse(args.filename)

	# generate instruction objects
	processed_instructions: List[Instruction] = []
	for inst in raw_instructions:
		processed_instructions.extend(inst.generate())

	# output generated instructions
	if args.model == "m2isar":
		memories = create_memories()
		constants = {
			"XLEN": arch.Constant(
				"XLEN", value=32, attributes={}, size=None, signed=False
			)
		}
		# transform to metamodel
		m2isar_instr = [i.to_metamodel() for i in processed_instructions]
		# instrucitons_dict = {(instr.mask, instr.code): instr for instr in m2isar_instr}
		instrucitons_dict = {(i, i): instr for i, instr in enumerate(m2isar_instr)}

		# output/save generated instructions
		core_def = create_dummy_core(memories, instrucitons_dict, constants)
		models = {core_def.name: core_def}
		with open(args.output, "wb") as file:
			pickle.dump(models, file)

		sys.exit(0)

	if args.model == "cdsl2":
		raise NotImplementedError("Not currently supported!")
		# generate .core_desc files
		# output/save generated instructions


if __name__ == "__main__":
	main()
