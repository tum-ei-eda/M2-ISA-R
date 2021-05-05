import argparse
import inspect
import pathlib
import pickle

from etiss_instruction_transformer import TransformerContext

import model_classes
from etiss_instruction_generator import generate_fields
from model_classes.behav import (Assignment, BinaryOperation, NamedReference,
                                 NumberLiteral, Operator)

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
with open(model_path / (abs_top_level.stem + '_model_new.pickle'), 'rb') as f:
    models = pickle.load(f)


import model_classes.etiss.behav

for name, fn in inspect.getmembers(model_classes.etiss.behav, inspect.isfunction):
    sig = inspect.signature(fn)
    param = sig.parameters.get("self")
    if not param:
        print(f"no \"self\" parameter found in {name}")
        continue
    if not param.annotation:
        print(f"\"self\" parameter not annotated")
        continue
    param.annotation.generate = fn

for core_name, (mt, core) in models.items():
    temp_var_count = 0
    mem_var_count = 0

    core_default_width = core.constants['XLEN'].value
    core_name = core.name
    for (code, mask), instr_def in core.instructions.items():
        instr_name = instr_def.name
        misc_code = []

        if instr_def.attributes == None:
            instr_def.attributes = []

        fields_code, asm_printer_code, seen_fields, enc_idx = generate_fields(core.constants['XLEN'].value, instr_def)

        context = TransformerContext(core.constants, core.address_spaces, core.registers, core.register_files, core.register_aliases, core.memories, core.memory_aliases, instr_def.fields, instr_def.attributes, core.functions, enc_idx, core_default_width, core_name)

        if model_classes.InstrAttribute.NO_CONT not in instr_def.attributes:
            instr_def.operation.statements.append(
                Assignment(
                    NamedReference(context.pc_mem),
                    BinaryOperation(
                        NamedReference(context.pc_mem),
                        Operator("+"),
                        NumberLiteral(int(enc_idx/8))
                    )
                )
            )

        if model_classes.InstrAttribute.NO_CONT in instr_def.attributes and model_classes.InstrAttribute.COND not in instr_def.attributes:
            misc_code.append('ic.force_block_end_ = true;')

        code_string = f'{code:#0{int(enc_idx/4)}x}'
        mask_string = f'{mask:#0{int(enc_idx/4)}x}'

        out = instr_def.operation.generate(context)

        print(instr_name)

        print(out)

        pass
