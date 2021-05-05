import argparse
import pathlib
import pickle
import time

from etiss_architecture_writer import write_arch_struct
from etiss_instruction_writer import write_functions, write_instructions


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

    output_base_path = search_path.joinpath('gen_output')
    output_base_path.mkdir(exist_ok=True)

    print('INFO: loading models')
    with open(model_path / (abs_top_level.stem + '_model_new.pickle'), 'rb') as f:
        models = pickle.load(f)

    start_time = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.localtime())

    for core_name, core in models.items():
        print(f'INFO: processing model {core_name}')
        output_path = output_base_path / core_name
        output_path.mkdir(exist_ok=True)

        write_arch_struct(core, start_time, output_path)
        write_functions(core, start_time, output_path)
        write_instructions(core, start_time, output_path, args.separate)

if __name__ == "__main__":
    main()
