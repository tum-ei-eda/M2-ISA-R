#!/usr/bin/env python3

import pickle

import etiss_instruction_generator
from etiss_writer import setup


def main():
	models, logger, output_base_path, spec_name, _, _ = setup()
	functions = {}
	instructions = {}

	for core_name, core in models.items():
		logger.info("processing model %s", core_name)

		functions[core_name] = dict(etiss_instruction_generator.generate_functions(core))
		instructions[core_name] = {(code, mask): (instr_name, ext_name, templ_str) for instr_name, (code, mask), ext_name, templ_str in etiss_instruction_generator.generate_instructions(core)}

	output_path = output_base_path / spec_name
	output_path.mkdir(exist_ok=True, parents=True)

	with open(output_path / f'{spec_name}.pickle', 'wb') as f:
		pickle.dump(functions, f)
		pickle.dump(instructions, f)

if __name__ == "__main__":
	main()
