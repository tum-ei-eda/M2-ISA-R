# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Functions for generating auxillary ETISS ArchImpl files."""

import logging
import pathlib

from mako.template import Template

from ... import M2TypeError
from ...metamodel import arch, behav
from . import BlockEndType
from .instruction_generator import (generate_fields,
                                    generate_instruction_callback)
from .templates import template_dir

logger = logging.getLogger("arch_writer")

def write_child_reg_def(reg: arch.Memory, regs: "list[str]"):
	"""Recursively generate register declarations"""

	logger.debug("processing register %s", reg)
	if arch.MemoryAttribute.IS_PC in reg.attributes or arch.MemoryAttribute.IS_MAIN_MEM in reg.attributes:
		logger.debug("this register is either the PC or main memory, skipping")
		return

	array_txt = f"[{reg.data_range.length}]" if reg.data_range.length > 1 else ""

	if len(reg.children) > 0:
		logger.debug("processing children")
		for child in reg.children:
			write_child_reg_def(child, regs)

		# registers with children (aliases) are defined as two arrays:
		# 1) array of pointers, used for actual access
		# 2) array of actual data type, for every index which is not aliased
		regs.append(f"etiss_uint{reg.actual_size} *{reg.name}{array_txt}")
		regs.append(f"etiss_uint{reg.actual_size} ins_{reg.name}{array_txt}")
	else:
		regs.append(f"etiss_uint{reg.actual_size} {reg.name}{array_txt}")

def write_arch_struct(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_struct_template = Template(filename=str(template_dir/'etiss_arch_struct.mako'))
	regs = []

	logger.info("writing architecture struct")

	for _, mem_desc in core.memories.items():
		write_child_reg_def(mem_desc, regs)

	txt = arch_struct_template.render(
		start_time=start_time,
		core_name=core.name,
		regs=regs
	)

	with open(output_path / f"{core.name}.h", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_header(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_h.mako'))

	logger.info("writing architecture class header")

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		instr_classes=sorted(core.instr_classes)
	)

	with open(output_path / f"{core.name}Arch.h", "w", encoding="utf-8") as f:
		f.write(txt)

def build_reg_hierarchy(reg: arch.Memory, ptr_regs: "list[arch.Memory]", actual_regs: "list[arch.Memory]",
		alias_regs: "dict[arch.Memory, arch.Memory]", initval_regs: "list[arch.Memory]"):
	"""Populate the passed lists with memory objects of their category.

	ptr_regs: Registers that need to be a pointer within ETISS
	actual_regs: Registers that are not a pointer
	alias_regs: Registers which are an alias to some other register
	initval_regs: Registers which have initial value(s) defined in the model
	"""

	# pylint: disable=protected-access
	if reg._initval:
		initval_regs.append(reg)

	if len(reg.children) > 0:
		for child in reg.children:
			if child.is_main_mem:
				logger.warning("main memory is a child memory of %s", reg)
				continue
			build_reg_hierarchy(child, ptr_regs, actual_regs, alias_regs, initval_regs)
			alias_regs[child] = reg
		ptr_regs.append(reg)
	else:
		actual_regs.append(reg)

def write_arch_cpp(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, aliased_regnames: bool=True):
	"""Generate {CoreName}Arch.cpp file. Contains mainly register initialization code."""

	arch_header_template = Template(filename=str(template_dir/'etiss_arch_cpp.mako'))

	ptr_regs = []
	actual_regs = []
	alias_regs = {}
	initval_regs = []

	logger.info("writing architecture class file")

	# determine memory types
	for _, mem_desc in core.memories.items():
		if mem_desc.is_main_mem:
			continue
		build_reg_hierarchy(mem_desc, ptr_regs, actual_regs, alias_regs, initval_regs)

	# generate main register file names for ETISS's 'char* reg_name[]'
	reg_names = [f"{core.main_reg_file.name}{n}" for n in range(core.main_reg_file.data_range.length)]

	# if main register file entries have aliases optionally use these for 'char* reg_name[]'
	if aliased_regnames:
		for child in core.main_reg_file.children:
			reg_names[child.range.lower] = child.name

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		instr_classes=sorted(core.instr_classes),
		reg_init_code="",
		reg_names=reg_names,
		ptr_regs=ptr_regs,
		actual_regs=actual_regs,
		alias_regs=alias_regs,
		initval_regs=initval_regs,
		procno_memory=core.procno_memory
	)

	with open(output_path / f"{core.name}Arch.cpp", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_lib(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_lib.mako'))

	logger.info("writing architecture lib")

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name
	)

	with open(output_path / f"{core.name}ArchLib.cpp", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_specific_header(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_specific_h.mako'))

	logger.info("writing architecture specific header")

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file
	)

	with open(output_path / f"{core.name}ArchSpecificImp.h", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_specific_cpp(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_specific_cpp.mako'))

	error_fn = None

	for fn in core.functions.values():
		if arch.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn.attributes:
			error_fn = fn
			break

	for fn in core.functions.values():
		if arch.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN in fn.attributes:
			error_fn = fn
			break

	error_callbacks: "dict[int, str]" = {}

	if error_fn is not None:
		for bitsize in core.instr_classes:
			error_bitfield = arch.BitField("error_code", arch.RangeSpec(31, 0), arch.DataType.U)
			error_instr = arch.Instruction(f"trap_entry {bitsize}", {arch.InstrAttribute.NO_CONT: None}, [error_bitfield], "", "", None, None)
			error_bitfield_descr = error_instr.fields.get("error_code")
			error_op = behav.Operation([
				behav.ProcedureCall(error_fn, [behav.NamedReference(error_bitfield_descr)])
			])
			error_instr.operation = error_op
			error_instr.throws = True
			error_instr._size = bitsize # pylint: disable=protected-access

			error_fields = generate_fields(32, error_instr)
			error_callbacks[bitsize] = generate_instruction_callback(core, error_instr, error_fields, True, BlockEndType.NONE, False)

	logger.info("writing architecture specific file")

	global_irq_en_mask = None
	if core.global_irq_en_memory is not None:
		attr = core.global_irq_en_memory.attributes[arch.MemoryAttribute.ETISS_IS_GLOBAL_IRQ_EN][0]
		if not isinstance(attr, behav.IntLiteral):
			raise M2TypeError(f"IRQ enable mask of {core.global_irq_en_memory.name} is not compile static")
		global_irq_en_mask = attr.value

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file,
		irq_en_reg=core.irq_en_memory,
		irq_pending_reg=core.irq_pending_memory,
		global_irq_en_reg=core.global_irq_en_memory,
		global_irq_en_mask=global_irq_en_mask,
		error_callbacks=error_callbacks,
		error_fn=error_fn
	)

	with open(output_path / f"{core.name}ArchSpecificImp.cpp", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_gdbcore(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_gdbcore.mako'))

	logger.info("writing gdbcore")

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file
	)

	with open(output_path / f"{core.name}GDBCore.h", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_cmake(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, separate: bool):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_cmake.mako'))

	logger.info("writing CMakeLists")

	arch_files = [f'{core.name}Instr.cpp']

	# if generation of one instr.cpp per extension is desired, only generate extensions which actually
	# contain instructions
	if separate:
		arch_files += [f'{core.name}_{ext_name}Instr.cpp' for ext_name in core.contributing_types if len(core.instructions_by_ext[ext_name]) > 0]

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		arch_files=arch_files
	)

	with open(output_path / "CMakeLists.txt", "w", encoding="utf-8") as f:
		f.write(txt)
