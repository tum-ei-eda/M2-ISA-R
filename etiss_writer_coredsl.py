import argparse
import os
import pickle
import time
from contextlib import ExitStack
from string import Template as strfmt

from lark import Token, Tree
from mako.template import Template

import model_classes
from etiss_instruction_writer import EtissInstructionWriter, data_type_map

parser = argparse.ArgumentParser()
parser.add_argument('top_level')
parser.add_argument('-s', '--separate', action='store_true')

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

instr_set_template = Template(filename='templates/etiss_instruction_set.mako')
fn_set_template = Template(filename='templates/etiss_function_set.mako')
instr_template = Template(filename='templates/etiss_instruction.mako')
fn_template = Template(filename='templates/etiss_function.mako')

start_time = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.localtime())

for core_name, (mt, core) in models.items():
    core_default_width = core.constants['XLEN'].value
    print(f'INFO: processing model {core_name}')

    temp_var_count = 0
    mem_var_count = 0

    outfiles = {}

    # process functions
    with ExitStack() as stack:
        if args.separate:
            outfiles = {ext_name: [stack.enter_context(open(f'gen_output/{core_name}_{ext_name}Funcs.h', 'w')), ''] for ext_name in core.contributing_types}
        else:
            outfiles = {'default': [stack.enter_context(open(f'gen_output/{core_name}Funcs.h', 'w')), '']}

        for fn_name, fn_def in core.functions.items():
            print(f'INFO: processing function {fn_name}')

            return_type = data_type_map[fn_def.data_type]
            if fn_def.size:
                return_type += f'{fn_def.actual_size}'

            fn_args = ', '.join([f'{data_type_map[arg.data_type]}{arg.actual_size} {arg.name}' for arg in fn_def.args.values()])

            t = EtissInstructionWriter(core.constants, core.address_spaces, core.registers, core.register_files, core.register_aliases, fn_def.args, [], [], 0, core_default_width, core_name, True)
            out_code = strfmt(t.transform(fn_def.operation)).safe_substitute(ARCH_NAME=core_name)

            templ_str = fn_template.render(
                return_type=return_type,
                fn_name=fn_name,
                args_list=fn_args,
                operation=out_code
            )

            outfiles.get(fn_def.ext_name, outfiles['default'])[1] += templ_str

        for extension_name, (out_f, functions_code) in outfiles.items():
            fn_set_str = fn_set_template.render(
                start_time=start_time,
                extension_name=extension_name,
                core_name=core_name,
                functions_code=functions_code
            )

            out_f.write(fn_set_str)

    # process instructions
    with ExitStack() as stack:
        if args.separate:
            outfiles = {ext_name: stack.enter_context(open(f'gen_output/{core_name}_{ext_name}Instr.cpp', 'w')) for ext_name in core.contributing_types}
        else:
            outfiles = {'default': stack.enter_context(open(f'gen_output/{core_name}Arch.cpp', 'w'))}

        for extension_name, out_f in outfiles.items():
            instr_set_str = instr_set_template.render(
                start_time=start_time,
                extension_name=extension_name,
                core_name=core_name
            )

            out_f.write(instr_set_str)

        for instr_name, instr_def in core.instructions.items():
            print(f'INFO: processing instruction {instr_name}')

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

            #print('\n--- fields:')
            #print(fields_code)

            t = EtissInstructionWriter(core.constants, core.address_spaces, core.registers, core.register_files, core.register_aliases, instr_def.fields, instr_def.attributes, core.functions, enc_idx, core_default_width, core_name)
            out_code = strfmt(t.transform(instr_def.operation)).safe_substitute(ARCH_NAME=core_name)

            if t.temp_var_count > temp_var_count:
                temp_var_count = t.temp_var_count

            if t.mem_var_count > mem_var_count:
                mem_var_count = t.mem_var_count

            #print('--- operation')
            #print(out_code)
            #print('\n')

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

            outfiles.get(instr_def.ext_name, outfiles['default']).write(templ_str)
