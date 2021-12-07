import argparse
import logging
import pathlib
import pickle
from typing import Dict
from ...metamodel import arch
from ...frontends.coredsl2 import expr_interpreter
import inspect

logger = logging.getLogger("viewer")

def patch_model():
	"""Monkey patch transformation functions inside instruction_transform
	into model_classes.behav classes
	"""

	for name, fn in inspect.getmembers(expr_interpreter, inspect.isfunction):
		sig = inspect.signature(fn)
		param = sig.parameters.get("self")
		if not param:
			logger.warning("no self parameter found in %s", fn)
			continue
		if not param.annotation:
			logger.warning("self parameter not annotated correctly for %s", fn)
			continue

		logger.debug("patching %s with fn %s", param.annotation, fn)
		param.annotation.generate = fn

#patch_model()

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .m2isarmodel file containing the models to generate.")
	parser.add_argument('-s', '--separate', action='store_true', help="Generate separate .cpp files for each instruction set.")
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
		models: Dict[str, arch.CoreDef] = pickle.load(f)

	for core_name, core_def in sorted(models.items()):
		print(f"core {core_name}")

		for const_name, const_def in sorted(core_def.constants.items()):
			print(f"constant {const_name} = {const_def.value}")

		for mem_name, mem_def in sorted(core_def.memories.items()):
			print(f"memory {mem_name}: {mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}")

		for mem_name, mem_def in sorted(core_def.memory_aliases.items()):
			print(f"memory alias {mem_name} ({mem_def.parent.name}): {mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}")

		for (code, mask), instr_def in sorted(core_def.instructions.items()):
			print(f"instruction {code:08x}:{mask:08x} ({instr_def.name})")
			enc_str = []
			for enc in instr_def.encoding:
				if isinstance(enc, arch.BitVal):
					enc_str.append(f"{enc.value:0{enc.length}b}")
				elif isinstance(enc, arch.BitField):
					enc_str.append(f"{enc.name}[{enc.range.upper}:{enc.range.lower}]")
			print(" ".join(enc_str))

	pass

if __name__ == "__main__":
	main()