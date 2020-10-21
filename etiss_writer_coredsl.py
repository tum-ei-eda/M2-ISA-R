import os
import argparse
import pickle
from lark import Tree, Token
from etiss_instruction_writer import EtissInstructionWriter, data_type_map
import model_classes
from string import Template as strfmt
from mako.template import Template

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

instr_template = Template(filename='etiss_instruction.mako')

for core_name, (mt, core) in models.items():
    core_default_width = core.constants['XLEN'].value
    print(f'INFO: processing model {core_name}')

    temp_var_count = 0
    mem_var_count = 0

    with open(f'{core_name}Arch.cpp', 'w') as instr_impl_f:

        for instr_name, instr_def in core.instructions.items():
            print(f'INFO: processing instruction {instr_name}\n')

            if instr_def.attributes == None:
                instr_def.attributes = []

            enc_idx = 0
            mask = 0
            code = 0
            seen_fields = {}

            fields_code = ""
            asm_printer_code = []

            for enc in reversed(instr_def.encoding):
                if isinstance(enc, model_classes.BitField):
                    if enc.name not in seen_fields:
                        seen_fields[enc.name] = 255
                        fields_code += f'{data_type_map[enc.data_type]}{core_default_width} {enc.name} = 0;\n'

                    lower = enc.range.lower
                    upper = enc.range.upper
                    length = upper - lower + 1

                    if seen_fields[enc.name] > lower:
                        seen_fields[enc.name] = lower

                    fields_code += f'static BitArrayRange R_{enc.name}_{lower}({enc_idx+length-1}, {enc_idx});\n'
                    fields_code += f'{enc.name} += R_{enc.name}_{lower}.read(ba) << {lower};\n'

                    if instr_def.fields[enc.name].upper < upper:
                        instr_def.fields[enc.name].upper = upper

                    enc_idx += length
                else:
                    mask |= (2**enc.length - 1) << enc_idx
                    code |= enc.value << enc_idx

                    enc_idx += enc.length

            for field_name, field_descr in reversed(instr_def.fields.items()):
                asm_printer_code.append(f'{field_name}=" + std::to_string({field_name}) + "')
                if field_descr.data_type == model_classes.DataType.S and field_descr.upper + 1 < core_default_width:
                    fields_code += '\n'
                    fields_code += f'struct {{etiss_int{core_default_width} x:{field_descr.upper+1};}} {field_name}_ext;\n'
                    fields_code += f'{field_name} = {field_name}_ext.x = {field_name};'

            asm_printer_code = f'ss << "{instr_name.lower()}" << " # " << ba << (" [' + ' | '.join(asm_printer_code) + ']");'

            if model_classes.InstrAttribute.NO_CONT not in instr_def.attributes:
                instr_def.operation.children.append(Tree('assignment', [Tree('named_reference', ['PC', None]), Tree('two_op_expr', [Tree('named_reference', ['PC', None]), Token('ADD_OP', '+'), Tree('number_literal', [int(enc_idx/8)])])]))

            code_string = f'{code:#0{int(enc_idx/4)}x}'
            mask_string = f'{mask:#0{int(enc_idx/4)}x}'

            print('\n--- fields:')
            print(fields_code)
            t = EtissInstructionWriter(core.constants, core.address_spaces, core.registers, core.register_files, core.register_aliases, instr_def.fields, instr_def.attributes, enc_idx, core_default_width, core_name)
            out_code = strfmt(t.transform(instr_def.operation)).safe_substitute(ARCH_NAME=core_name)

            if t.temp_var_count > temp_var_count:
                temp_var_count = t.temp_var_count

            if t.mem_var_count > mem_var_count:
                mem_var_count = t.mem_var_count

            print('--- operation')
            print(out_code)
            print('\n')

            templ_str = instr_template.render(
                instr_name=instr_name,
                seen_fields=seen_fields,
                enc_idx=enc_idx,
                core_name=core_name,
                code_string=code_string,
                mask_string=mask_string,
                fields_code=fields_code,
                asm_printer_code=asm_printer_code,
                core_default_width=core_default_width,
                reg_dependencies=t.dependent_regs,
                reg_affected = t.affected_regs,
                operation=out_code
            )

            instr_impl_f.write(templ_str)

            pass

pass