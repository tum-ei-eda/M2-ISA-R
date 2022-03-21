import argparse
import logging
import pathlib
import pickle
from collections import defaultdict
from io import SEEK_CUR

from bitarray.util import ba2int, int2ba

from ...metamodel import arch

logger = logging.getLogger("viewer")

def find_instr(iw: int, instructions: "dict[tuple[int, int], arch.Instruction]"):
	for (code, mask), instr_def in instructions.items():
		if (iw & mask) == code:
			return instr_def

	return None

def slice_int(v: int, upper: int, lower: int):
	return (v & ((1 << upper + 1) - 1)) >> lower

def decode(iw: int, instr: arch.Instruction):
	enc_idx = 0

	operands = defaultdict(int)

	for enc in reversed(instr.encoding):
		if isinstance(enc, arch.BitField):
			lower = enc.range.lower
			upper = enc.range.upper
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
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	args = parser.parse_args()

	logging.basicConfig(level=getattr(logging, args.log.upper()))
	logger = logging.getLogger("etiss_writer")

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

	spec_name = abs_top_level.stem
	output_base_path = search_path.joinpath('gen_output')
	output_base_path.mkdir(exist_ok=True)

	logger.info("loading models")

	with open(model_fname, 'rb') as f:
		models: "dict[str, arch.CoreDef]" = pickle.load(f)

	core = models[args.core_name]
	readlen = max(core.instr_classes) // 8
	steplen = min(core.instr_classes) // 8

	instrs_by_size = defaultdict(dict)

	for k, v in core.instructions.items():
		instrs_by_size[v.size][k] = v

	with open(args.bin, "rb", readlen) as f:
		while iw := f.peek(readlen):
			found_ins = None
			for cls in sorted(core.instr_classes):
				ii = int.from_bytes(iw[:cls // 8], "little")
				i = find_instr(ii, instrs_by_size[cls])
				if i is not None:
					found_ins = i

			if found_ins is None:
				ins_str = "unknown"
				step = steplen

			else:
				operands = decode(ii, found_ins)
				op_str = " | ".join([f"{k}={v}" for k, v in operands.items()])
				ins_str = f"{found_ins.name} [{op_str}]"
				step = found_ins.size // 8

			print(f"{f.tell():08x}: {iw[:step // 8].hex()} {ins_str}")

			f.seek(step, SEEK_CUR)



if __name__ == "__main__":
	main()
