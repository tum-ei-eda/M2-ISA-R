# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Simple disassembler backend for M2-ISA-R ISA metamodels. Not very
actively maintained, might break or otherwise not work as expected.
"""

import argparse
import logging
import pathlib
import pickle
from collections import defaultdict
from io import SEEK_CUR

from ...metamodel import arch
from .asm_formatter import AsmFormatter

logger = logging.getLogger("viewer")

def sort_instruction(entry):
	"""Key function for sorting instructions:

	Sorts by most restrictive mask first, to accurately distinguish
	overlapping opcodes
	"""

	(code, mask), _ = entry
	return bin(mask).count("1"), code

def find_instr(iw: int, instructions: "dict[tuple[int, int], arch.Instruction]"):
	"""Linear search for an instruction by its codeword."""

	for (code, mask), instr_def in instructions.items():
		if (iw & mask) == code:
			return instr_def

	return None

def slice_int(v: int, upper: int, lower: int):
	return (v & ((1 << upper + 1) - 1)) >> lower

def decode(iw: int, instr: arch.Instruction):
	"""Separate out operands of an instruction from its codeword."""

	enc_idx = 0

	operands = defaultdict(int)

	for enc in reversed(instr.encoding):
		if isinstance(enc, arch.BitField):
			lower = enc.range.lower
			length = enc.range.length

			operands[enc.name] += slice_int(iw, enc_idx+length-1, enc_idx) << lower

			enc_idx += length
		else:
			enc_idx += enc.length

	return operands

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .m2isarmodel file containing the models to generate.")
	parser.add_argument("core_name")
	parser.add_argument('bin')
	parser.add_argument("--format", action="store_true", help="Use assembly formatting string and mnemonic")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	args = parser.parse_args()

	logging.basicConfig(level=getattr(logging, args.log.upper()))

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

	output_base_path = search_path.joinpath('gen_output')
	output_base_path.mkdir(exist_ok=True)

	logger.info("loading models")

	with open(model_fname, 'rb') as f:
		models: "dict[str, arch.CoreDef]" = pickle.load(f)

	core = models[args.core_name]
	readlen = max(core.instr_classes) // 8
	steplen = min(core.instr_classes) // 8

	instrs_by_size = defaultdict(dict)

	# group instructions by their codeword width
	for k, v in core.instructions.items():
		instrs_by_size[v.size][k] = v

	# sort instructions by opcode
	for k, v in instrs_by_size.items():
		instrs_by_size[k] = dict(sorted(v.items(), key=sort_instruction, reverse=True))

	instrs_by_size = dict(sorted(instrs_by_size.items()))

	prev_count = 0

	with open(args.bin, "rb") as f:
		# read at most XLEN bytes at a time
		while iw_read := f.peek(readlen):
			# truncate read data as peek is not guaranteed to return exactly XLEN bytes
			iw = iw_read[:readlen]

			# look for instruction
			found_ins = None
			for cls in sorted(core.instr_classes):
				ii = int.from_bytes(iw[:cls // 8], "little")
				i = find_instr(ii, instrs_by_size[cls])
				if i is not None:
					found_ins = i

			if found_ins is None:
				ins_str = "unknown"
				step = steplen

				if prev_count > 2:
					print(f"\trepeated {prev_count-2} times.")
				prev_count = 0

			# decode instruction operands
			else:
				if found_ins and found_ins.name == "DII":
					prev_count += 1
					if prev_count > 1:
						bla = f.tell()
						f.seek(step, SEEK_CUR)
						continue
				else:
					if prev_count > 2:
						print(f"\trepeated {prev_count-2} times.")
					prev_count = 0

				operands = decode(ii, found_ins)
				if args.format:
					asm_name = found_ins.mnemonic
					assembly = found_ins.assembly
					fmt = AsmFormatter()
					if assembly is None:
						assembly = ""
					asm_args = fmt.format(assembly, **operands)
				else:
					asm_name = found_ins.name
					op_str = " | ".join([f"{k}={v}" for k, v in operands.items()])
					asm_args = f"[{op_str}]"
				ins_str = f"{asm_name}\t{asm_args}"
				step = found_ins.size // 8

			# print decoded instruction mnemonic
			iword = int.from_bytes(iw[:step], "little")
			iword = "{iword:0{step}x}".format(iword=iword, step=step*2)
			print(f"{f.tell():08x}: {iword:<16} {ins_str}")

			f.seek(step, SEEK_CUR)


if __name__ == "__main__":
	main()
