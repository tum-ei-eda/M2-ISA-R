import inspect
from string import Template as strfmt

from mako.template import Template

import etiss_instruction_transform
import etiss_instruction_utils
import model_classes
import model_classes.arch
import model_classes.behav


def patch_model():
    """Monkey patch transformation functions inside etiss_instruction_transform
    into model_classes.behav classes
    """

    for name, fn in inspect.getmembers(etiss_instruction_transform, inspect.isfunction):
        sig = inspect.signature(fn)
        param = sig.parameters.get("self")
        if not param:
            print(f"no \"self\" parameter found in {name}")
            continue
        if not param.annotation:
            print(f"\"self\" parameter not annotated")
            continue
        param.annotation.generate = fn

def generate_functions(core: model_classes.arch.CoreDef):
    """Return a generator object to generate function behavior code. Uses function
    definitions in the core object.
    """

    fn_template = Template(filename='templates/etiss_function.mako')

    core_default_width = core.constants['XLEN'].value
    core_name = core.name

    for fn_name, fn_def in core.functions.items():
        return_type = etiss_instruction_utils.data_type_map[fn_def.data_type]
        if fn_def.size:
            return_type += f'{fn_def.actual_size}'

        context = etiss_instruction_utils.TransformerContext(core.constants, core.address_spaces, core.registers, core.register_files, core.register_aliases, core.memories, core.memory_aliases, fn_def.args, [], core.functions, 0, core_default_width, core_name, True)

        out_code = fn_def.operation.generate(context)
        out_code = strfmt(out_code).safe_substitute(ARCH_NAME=core_name)

        fn_def.static = not context.used_arch_data

        args_list = [f'{etiss_instruction_utils.data_type_map[arg.data_type]}{arg.actual_size} {arg.name}' for arg in fn_def.args.values()]
        if not fn_def.static:
            args_list = ['ETISS_CPU * const cpu', 'ETISS_System * const system', 'void * const * const plugin_pointers'] + args_list

        fn_args = ', '.join(args_list)

        templ_str = fn_template.render(
            return_type=return_type,
            fn_name=fn_name,
            args_list=fn_args,
            operation=out_code
        )

        yield (fn_name, templ_str)

def generate_fields(core_default_width, instr_def: model_classes.arch.Instruction):
    """Generate the extraction code for all fields of an instr_def"""

    enc_idx = 0

    seen_fields = {}

    fields_code = ""
    asm_printer_code = []

    for enc in reversed(instr_def.encoding):
        if isinstance(enc, model_classes.arch.BitField):
            if enc.name not in seen_fields:
                seen_fields[enc.name] = 255
                fields_code += f'{etiss_instruction_utils.data_type_map[enc.data_type]}{core_default_width} {enc.name} = 0;\n'

            lower = enc.range.lower
            upper = enc.range.upper
            length = enc.range.length

            if seen_fields[enc.name] > lower:
                seen_fields[enc.name] = lower

            fields_code += f'static BitArrayRange R_{enc.name}_{lower}({enc_idx+length-1}, {enc_idx});\n'
            fields_code += f'{enc.name} += R_{enc.name}_{lower}.read(ba) << {lower};\n'

            if instr_def.fields[enc.name].upper < upper:
                instr_def.fields[enc.name].upper = upper

            enc_idx += length
        else:
            enc_idx += enc.length

    for field_name, field_descr in reversed(instr_def.fields.items()):
        # generate asm_printer code
        asm_printer_code.append(f'{field_name}=" + std::to_string({field_name}) + "')

        # generate sign extension if necessary
        if field_descr.data_type == model_classes.DataType.S and field_descr.upper + 1 < core_default_width:
            fields_code += '\n'
            fields_code += f'struct {{etiss_int{core_default_width} x:{field_descr.upper+1};}} {field_name}_ext;\n'
            fields_code += f'{field_name} = {field_name}_ext.x = {field_name};'

    asm_printer_code = f'ss << "{instr_def.name.lower()}" << " # " << ba << (" [' + ' | '.join(reversed(asm_printer_code)) + ']");'

    return (fields_code, asm_printer_code, seen_fields, enc_idx)

def generate_instructions(core: model_classes.arch.CoreDef):
    """Return a generator object to generate instruction behavior code. Uses instruction
    definitions in the core object.
    """

    instr_template = Template(filename='templates/etiss_instruction.mako')

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

        context = etiss_instruction_utils.TransformerContext(core.constants, core.address_spaces, core.registers, core.register_files, core.register_aliases, core.memories, core.memory_aliases, instr_def.fields, instr_def.attributes, core.functions, enc_idx, core_default_width, core_name)

        # add pc increment to operation tree
        if model_classes.InstrAttribute.NO_CONT not in instr_def.attributes:
            instr_def.operation.statements.append(
                model_classes.behav.Assignment(
                    model_classes.behav.NamedReference(context.pc_mem),
                    model_classes.behav.BinaryOperation(
                        model_classes.behav.NamedReference(context.pc_mem),
                        model_classes.behav.Operator("+"),
                        model_classes.behav.NumberLiteral(int(enc_idx/8))
                    )
                )
            )

        if model_classes.InstrAttribute.NO_CONT in instr_def.attributes and model_classes.InstrAttribute.COND not in instr_def.attributes:
            misc_code.append('ic.force_block_end_ = true;')

        code_string = f'{code:#0{int(enc_idx/4)}x}'
        mask_string = f'{mask:#0{int(enc_idx/4)}x}'

        # generate instruction behavior code
        out_code = instr_def.operation.generate(context)
        out_code = strfmt(out_code).safe_substitute(ARCH_NAME=core_name)

        if context.temp_var_count > temp_var_count:
            temp_var_count = context.temp_var_count

        if context.mem_var_count > mem_var_count:
            mem_var_count = context.mem_var_count

        # render code for whole instruction
        templ_str = instr_template.render(
            instr_name=instr_name,
            seen_fields=seen_fields,
            enc_idx=enc_idx,
            core_name=core_name,
            code_string=code_string,
            mask_string=mask_string,
            misc_code=misc_code,
            fields_code=fields_code,
            asm_printer_code=asm_printer_code,
            core_default_width=core_default_width,
            reg_dependencies=context.dependent_regs,
            reg_affected=context.affected_regs,
            operation=out_code
        )

        yield (instr_name, (code, mask), instr_def.ext_name, templ_str)
