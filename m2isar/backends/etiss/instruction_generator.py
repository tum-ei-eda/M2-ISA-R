# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import logging
from string import Template as strfmt

from mako.template import Template

from ...metamodel import arch, patch_model
from . import BlockEndType, instruction_transform, instruction_utils
from .templates import template_dir

logger = logging.getLogger("instruction_generator")

def generate_arg_str(arg: arch.FnParam):
	arg_name = f" {arg.name}" if arg.name is not None else ""
	return f'{instruction_utils.data_type_map[arg.data_type]}{arg.actual_size}{arg_name}'

def generate_functions(core: arch.CoreDef, static_scalars: bool):
	"""Return a generator object to generate function behavior code. Uses function
	definitions in the core object.
	"""

	patch_model(instruction_transform)

	fn_template = Template(filename=str(template_dir/'etiss_function.mako'))

	core_default_width = core.constants['XLEN'].value
	core_name = core.name

	for fn_name, fn_def in core.functions.items():
		logger.debug("setting up function generator for %s", fn_name)

		#if fn_def.extern:
		#	continue

		return_type = instruction_utils.data_type_map[fn_def.data_type]
		if fn_def.size:
			return_type += f'{fn_def.actual_size}'

		context = instruction_utils.TransformerContext(core.constants, core.memories, core.memory_aliases, fn_def.args, fn_def.attributes, core.functions, 0, core_default_width, core_name, static_scalars, True)

		logger.debug("generating code for %s", fn_name)

		out_code = fn_def.operation.generate(context)
		out_code = strfmt(out_code).safe_substitute(ARCH_NAME=core_name)

		#fn_def.static = not context.used_arch_data

		logger.debug("generating header for %s", fn_name)

		args_list = [generate_arg_str(arg) for arg in fn_def.args.values()]
		if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn_def.attributes or (not fn_def.extern and not fn_def.static):
			args_list = ['ETISS_CPU * const cpu', 'ETISS_System * const system', 'void * const * const plugin_pointers'] + args_list

		fn_args = ', '.join(args_list)

		logger.debug("rendering template for %s", fn_name)

		templ_str = fn_template.render(
			return_type=return_type,
			fn_name=fn_name,
			args_list=fn_args,
			static=fn_def.static,
			operation=out_code
		)

		yield (fn_name, templ_str)

def generate_fields(core_default_width, instr_def: arch.Instruction):
	"""Generate the extraction code for all fields of an instr_def"""

	enc_idx = 0

	seen_fields = {}

	fields_code = ""
	asm_printer_code = []

	logger.debug("generating instruction parameters for %s", instr_def.name)

	for enc in reversed(instr_def.encoding):
		if isinstance(enc, arch.BitField):
			logger.debug("adding parameter %s", enc.name)
			if enc.name not in seen_fields:
				seen_fields[enc.name] = 255
				fields_code += f'{instruction_utils.data_type_map[enc.data_type]}{core_default_width} {enc.name} = 0;\n'

			lower = enc.range.lower
			upper = enc.range.upper
			length = enc.range.length

			if seen_fields[enc.name] > lower:
				seen_fields[enc.name] = lower

			fields_code += f'static BitArrayRange R_{enc.name}_{lower}({enc_idx+length-1}, {enc_idx});\n'
			fields_code += f'{enc.name} += R_{enc.name}_{lower}.read(ba) << {lower};\n'

			enc_idx += length
		else:
			logger.debug("adding fixed encoding part")
			enc_idx += enc.length

	logger.debug("generating asm_printer and sign extensions")
	for field_name, field_descr in reversed(instr_def.fields.items()):
		# generate asm_printer code
		asm_printer_code.append(f'{field_name}=" + std::to_string({field_name}) + "')

		# generate sign extension if necessary
		if field_descr.data_type == arch.DataType.S and field_descr.size < core_default_width:
			fields_code += '\n'
			fields_code += f'struct {{etiss_int{core_default_width} x:{field_descr.size};}} {field_name}_ext;\n'
			fields_code += f'{field_name} = {field_name}_ext.x = {field_name};'

	asm_printer_code = f'ss << "{instr_def.name.lower()}" << " # " << ba << (" [' + ' | '.join(reversed(asm_printer_code)) + ']");'

	return (fields_code, asm_printer_code, seen_fields, enc_idx)

def generate_instructions(core: arch.CoreDef, static_scalars: bool, block_end_on: BlockEndType):
	"""Return a generator object to generate instruction behavior code. Uses instruction
	definitions in the core object.
	"""

	patch_model(instruction_transform)

	instr_template = Template(filename=str(template_dir/'etiss_instruction.mako'))

	temp_var_count = 0
	mem_var_count = 0

	core_default_width = core.constants['XLEN'].value
	core_name = core.name

	for (code, mask), instr_def in core.instructions.items():
		logger.debug("setting up instruction generator for %s", instr_def.name)

		instr_name = instr_def.name
		misc_code = []

		if instr_def.attributes == None:
			instr_def.attributes = []

		fields_code, asm_printer_code, seen_fields, enc_idx = generate_fields(core.constants['XLEN'].value, instr_def)

		context = instruction_utils.TransformerContext(core.constants, core.memories, core.memory_aliases, instr_def.fields, instr_def.attributes, core.functions, enc_idx, core_default_width, core_name, static_scalars)

		if ((arch.InstrAttribute.NO_CONT in instr_def.attributes and arch.InstrAttribute.COND not in instr_def.attributes and block_end_on == BlockEndType.UNCOND)
				or (arch.InstrAttribute.NO_CONT in instr_def.attributes and block_end_on == BlockEndType.ALL)):
			logger.debug("adding forced block end")
			misc_code.append('ic.force_block_end_ = true;')

		code_string = f'{code:#0{int(enc_idx/4)}x}'
		mask_string = f'{mask:#0{int(enc_idx/4)}x}'

		# generate instruction behavior code
		logger.debug("generating behavior code for %s", instr_def.name)

		out_code = instr_def.operation.generate(context)
		out_code = strfmt(out_code).safe_substitute(ARCH_NAME=core_name)

		if context.temp_var_count > temp_var_count:
			temp_var_count = context.temp_var_count

		if context.mem_var_count > mem_var_count:
			mem_var_count = context.mem_var_count

		logger.debug("rendering template for %s", instr_def.name)
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
