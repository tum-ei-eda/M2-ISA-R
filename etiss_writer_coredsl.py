import os
import argparse
import pickle
from etiss_instruction_writer import EtissInstructionWriter, data_type_map
import model_classes

parser = argparse.ArgumentParser()
parser.add_argument("top_level")

args = parser.parse_args()

abs_top_level = os.path.abspath(args.top_level)
search_path = os.path.dirname(abs_top_level)

print('INFO: loading parse tree')
with open(os.path.splitext(abs_top_level)[0] + '_parsed.pickle', 'rb') as f:
    converted_tree = pickle.load(f)

print('INFO: loading instruction set store')
with open(os.path.splitext(abs_top_level)[0] + '_iss.pickle', 'rb') as f:
    iss = pickle.load(f)

print('INFO: loading models')
with open(os.path.splitext(abs_top_level)[0] + '_model.pickle', 'rb') as f:
    models = pickle.load(f)

pass

for core_name, (mt, core) in models.items():
    print(f'INFO: processing model {core_name}')
    for instr_name, instr_def in core.instructions.items():
        print(f'INFO: processing instruction {instr_name}\n')

        enc_idx = 0
        mask = 0
        code = 0
        seen_fields = set()

        fields_code = ""

        for enc in reversed(instr_def.encoding):
            if isinstance(enc, model_classes.BitField):
                if enc.name not in seen_fields:
                    seen_fields.add(enc.name)
                    fields_code += f'{data_type_map[enc.data_type]} {enc.name} = 0;\n'
                
                lower = enc.range.lower
                upper = enc.range.upper
                length = upper - lower + 1

                fields_code += f'static BitArrayRange R_{enc.name}_{lower}({enc_idx+length-1}, {enc_idx});\n'
                fields_code += f'{enc.name} += R_{enc.name}_{lower}.read(ba) << {lower};\n'

                enc_idx += length
            else:
                mask |= (2**enc.length - 1) << enc_idx
                code |= enc.value << enc_idx

                enc_idx += enc.length
        
        print('\n--- fields:')
        print(fields_code)
        t = EtissInstructionWriter(core.constants, core.address_spaces, core.registers, core.register_files, core.register_aliases, instr_def.fields, instr_def.attributes, enc_idx, core.constants['XLEN'].value)
        out_code = t.transform(instr_def.operation)
        print('--- operation')
        print(out_code)
        print('\n')
        pass

pass