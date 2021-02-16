import argparse
import pathlib
import pickle

import etiss_instruction_generator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('top_level')
    parser.add_argument('-s', '--separate', action='store_true')

    args = parser.parse_args()

    top_level = pathlib.Path(args.top_level)
    abs_top_level = top_level.resolve()
    search_path = abs_top_level.parent
    model_path = search_path.joinpath('gen_model')

    if not model_path.exists():
        raise FileNotFoundError('Models not generated!')

    output_path = search_path.joinpath('gen_output')
    output_path.mkdir(exist_ok=True)

    print('INFO: loading models')
    with open(model_path / (abs_top_level.stem + '_model.pickle'), 'rb') as f:
        models = pickle.load(f)

    functions = {}
    instructions = {}

    for core_name, (mt, core) in models.items():
        print(f'INFO: processing model {core_name}')

        functions[core_name] = dict(etiss_instruction_generator.generate_functions(core))
        instructions[core_name] = {(code, mask): (instr_name, ext_name, templ_str) for instr_name, (code, mask), ext_name, templ_str in etiss_instruction_generator.generate_instructions(core)}

    with open(output_path / f'{core_name}.pickle', 'wb') as f:
        pickle.dump(functions, f)
        pickle.dump(instructions, f)

    pass

if __name__ == "__main__":
    main()
