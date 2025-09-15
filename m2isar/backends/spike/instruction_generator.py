# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2025
# Chair of Electrical Design Automation
# Technical University of Munich

"""Functions for generating patches for adding new instruction to spike."""

import logging

from mako.template import Template

# from ...metamodel import arch, behav, patch_model
from ...metamodel import arch, patch_model
from . import instruction_transform, instruction_utils
from .templates import template_dir

logger = logging.getLogger("instruction_generator")


def generate_arg_str(arg: arch.FnParam):
    arg_name = f" {arg.name}" if arg.name is not None else ""
    return f"{instruction_utils.data_type_map[arg.data_type]}{arg.actual_size}{arg_name}"


def generate_fields(set_default_width, instr_def: arch.Instruction):
    """Generate the extraction code for all fields of an instr_def"""

    enc_idx = 0

    seen_fields = {}

    fields_code = ""
    asm_printer_code = []

    logger.debug("generating instruction parameters for %s", instr_def.name)

    # iterate from LSB to MSB
    for enc in reversed(instr_def.encoding):
        if isinstance(enc, arch.BitField):
            # parameter field
            logger.debug("adding parameter %s", enc.name)

            if enc.name not in seen_fields:
                # first encounter of this parameter, instantiate a new integer for it
                seen_fields[enc.name] = 255
                width = instr_def.fields[enc.name].actual_size
                fields_code += f"{instruction_utils.data_type_map[enc.data_type]}{width} {enc.name} = 0;\n"

            lower = enc.range.lower
            length = enc.range.length

            if seen_fields[enc.name] > lower:
                seen_fields[enc.name] = lower

            # generate extraction code
            fields_code += f"static BitArrayRange R_{enc.name}_{lower}({enc_idx+length-1}, {enc_idx});\n"
            fields_code += f"{enc.name} += R_{enc.name}_{lower}.read(ba) << {lower};\n"

            # keep track of current position in encoding
            enc_idx += length
        else:
            # fixed encoding bits
            logger.debug("adding fixed encoding part")
            enc_idx += enc.length

    logger.debug("generating asm_printer and sign extensions")
    for field_name, field_descr in reversed(instr_def.fields.items()):
        # generate asm_printer code
        asm_printer_code.append(f'{field_name}=" + std::to_string({field_name}) + "')

        # generate sign extension if necessary
        if field_descr.data_type == arch.DataType.S and field_descr.size < set_default_width:
            fields_code += "\n"
            fields_code += f"struct {{etiss_int{set_default_width} x:{field_descr.size};}} {field_name}_ext;\n"
            fields_code += f"{field_name} = {field_name}_ext.x = {field_name};"

    asm_printer_code = (
        f'ss << "{instr_def.name.lower()}" << " # " << ba << (" [' + " | ".join(reversed(asm_printer_code)) + ']");'
    )

    return (fields_code, asm_printer_code, seen_fields, enc_idx)


def generate_instruction_callback(
    set_def: arch.InstructionSet,
    instr_def: arch.Instruction,
    fields,
):
    patch_model(instruction_transform)

    instr_name = instr_def.name
    set_name = set_def.name
    misc_code = []
    set_default_width = None
    fields_code, _, _, enc_idx = fields

    callback_template = Template(filename=str(template_dir / "spike_instruction_callback.mako"))

    context = instruction_utils.TransformerContext(
        set_def.constants,
        set_def.memories,
        set_def.memory_aliases,
        instr_def.fields,
        instr_def.attributes,
        set_def.functions,
        enc_idx,
        set_default_width,
        set_name,
        # set_def.intrinsics,
    )

    # generate instruction behavior code
    logger.debug("generating behavior code for %s", instr_def.name)

    out_code = instr_def.operation.generate(context)
    out_code.format(SET_NAME=set_name)

    logger.debug("rendering template for %s", instr_def.name)

    callback_str = callback_template.render(
        instr_name=instr_name,
        misc_code=misc_code,
        # fields_code=fields_code,
        operation=out_code,
        # reg_dependencies=[],  # context.dependent_regs,
        # reg_affected=[],  # context.affected_regs,
        # set_default_width=set_default_width,
    )

    return callback_str


def generate_instructions(set_def: arch.InstructionSet):
    """Return a generator object to generate instruction behavior code. Uses instruction
    definitions in the set object.
    """

    instr_template = Template(filename=str(template_dir / "spike_instruction.mako"))

    # set_name = set_def.name

    for (code, mask), instr_def in set_def.instructions.items():
        logger.debug("setting up instruction generator for %s", instr_def.name)

        instr_name = instr_def.name
        instr_name_lower = instr_name.lower()
        instr_name_upper = instr_name.upper()
        mk_str = f"       {instr_name_lower} \\\n"

        if instr_def.attributes is None:
            instr_def.attributes = []

        # generate instruction parameter extraction code
        fields = generate_fields(None, instr_def)
        # fields_code, asm_printer_code, seen_fields, enc_idx = fields

        code_string = f"{code:#08x}"
        mask_string = f"{mask:#08x}"
        compact = True
        if compact:
            enc_str = f"DECLARE_INSN({instr_name_lower}, {code_string}, {mask_string})\n"
        else:
            enc_str = f"""#define MATCH_{instr_name_upper} {code_string}
#define MASK_{instr_name_upper} {mask_string}
DECLARE_INSN({instr_name}, MATCH_{instr_name_upper}, MASK_{instr_name_upper})
"""

        if arch.InstrAttribute.ENABLE in instr_def.attributes:
            raise NotImplementedError("ENABLE attr")

        callback_str = generate_instruction_callback(set_def, instr_def, fields)
        print("callback_str", callback_str)

        # render code for whole instruction
        behav_str = instr_template.render(
            instr_name=instr_name,
            # TODO: assembly or pseudo code?
            # seen_fields=seen_fields,
            # enc_idx=enc_idx,
            # core_name=core_name,
            # code_string=code_string,
            # mask_string=mask_string,
            # fields_code=fields_code,
            # asm_printer_code=asm_printer_code,
            callback_code=callback_str,
        )

        yield (instr_name, (code, mask), instr_def.ext_name, enc_str, mk_str, behav_str)
