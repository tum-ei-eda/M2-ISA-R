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
from itertools import chain
from typing import Union

from mako.template import Template


from .instruction_utils import actual_size, reg_type_info
from ... import M2TypeError
from ...metamodel import arch, behav, type_info, attribute_info
from . import BlockEndType
from .instruction_generator import (generate_fields,
                                    generate_instruction_callback)
from .templates import template_dir

logger = logging.getLogger("arch_writer")

def write_child_reg_def(reg: Union[arch.Memory, arch.RegisterBank, arch.Register], regs: "list[str]"):
	"""Recursively generate child declarations for Memories and Register(Banks)"""

	logger.debug("processing register %s", reg)
	if attribute_info.RegisterAttribute.IS_PC in reg.attributes or attribute_info.MemoryAttribute.IS_MAIN_MEM in reg.attributes:
		logger.debug("this register is either the PC or main memory, skipping")
		return

	assert(isinstance(reg.ty, (type_info.ArrayType, type_info.PrimitiveType, type_info.PointerType)))
	type_acc = reg_type_info(reg)
	if isinstance(reg.ty, type_info.ArrayType):
		array_txt = f"[{arch.get_const_or_val(reg.ty.length)}]"
		assert(reg.ty.element_type.kind in (type_info.TypeKind.UINT, type_info.TypeKind.INT))
	elif isinstance(reg.ty, type_info.PrimitiveType):
		assert(reg.ty.kind in (type_info.TypeKind.UINT, type_info.TypeKind.INT))
		array_txt = ""
	elif isinstance(reg.ty, type_info.PointerType):
			array_txt = f"[{arch.get_const_or_val(reg.data_range.length)}]" if arch.get_const_or_val(reg.data_range.length) > 1 else ""
	else:
		array_txt = ""

	if hasattr(reg, "children"):

		logger.debug("processing children")
		for child in reg.children:
			write_child_reg_def(child, regs)

		# registers with children (aliases) are defined as two arrays:
		# 1) array of pointers, used for actual access
		# 2) array of actual data type, for every index which is not aliased
		type_acc = reg_type_info(reg)
		if isinstance(reg.ty, type_info.ArrayType):
			assert(reg.ty.element_type.kind in (type_info.TypeKind.UINT, type_info.TypeKind.INT))
			size = actual_size(reg.ty.element_type.size)
		elif isinstance(reg.ty, type_info.PrimitiveType):
			assert(reg.ty.kind in (type_info.TypeKind.UINT, type_info.TypeKind.INT))
			size = actual_size(reg.ty.size)
		else:
			raise "Register Types needs to be of Array or PrimitiveType"

		if (len(reg.children) > 0):
			regs.append(f"{type_acc}{size} *{reg.name}{array_txt}")
			regs.append(f"{type_acc}{size} ins_{reg.name}{array_txt}")
		else:
			regs.append(f"{type_acc}{actual_size(size)} {reg.name}{array_txt}")

	else:
		size = None
		if isinstance(reg.ty, type_info.PointerType):
			assert(isinstance(reg.ty.ty, type_info.PrimitiveType))
			size = actual_size(reg.ty.ty.size)
		else:
			assert(isinstance(reg.ty, type_info.PrimitiveType))
			size = actual_size(reg.ty.size)
		regs.append(f"{type_acc}{size} {reg.name}{array_txt}")

def write_arch_struct(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_struct_template = Template(filename=str(template_dir/'etiss_arch_struct.mako'))
	regs = []
	mems = []

	logger.info("writing architecture struct")

	assert core.memories is not None and core.register_banks is not None
	for _, reg_desc in chain(core.register_banks.items()):
		write_child_reg_def(reg_desc, regs)
	for _, mem_desc in chain(core.memories.items()):
		write_child_reg_def(mem_desc, mems)

	txt = arch_struct_template.render(
		start_time=start_time,
		core_name=core.name,
		regs=regs,
		mems=mems
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

def build_reg_hierarchy(reg: Union[arch.Memory, arch.Alias, arch.Register, arch.RegisterBank],
						ptr_regs: "list[arch.Memory]", actual_regs: "list[arch.Memory]",
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

	if isinstance(reg, (arch.Memory, arch.Register, arch.RegisterBank)):
		if len(reg.children) > 0:
			for child in reg.children:
				if hasattr(child, "is_main_mem"):
					if child.is_main_mem:
						logger.warning("main memory is a child memory of %s", reg)
						continue
				build_reg_hierarchy(child, ptr_regs, actual_regs, alias_regs, initval_regs)
				alias_regs[child] = reg
			ptr_regs.append(reg)
		else:
			actual_regs.append(reg)
	else:
		assert isinstance(reg, arch.Alias)
		return

def write_arch_cpp(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, aliased_regnames: bool=True):
	"""Generate {CoreName}Arch.cpp file. Contains mainly register initialization code."""

	arch_cpp_template = Template(filename=str(template_dir/'etiss_arch_cpp.mako'))

	ptr_regs = []
	actual_regs = []
	alias_regs = {}
	initval_regs = []

	logger.info("writing architecture class file")

	# determine memory types
	for _, mem_desc in chain(core.memories.items(), core.register_banks.items(), core.memory_aliases.items(), core.register_aliases.items()):
		if  hasattr(mem_desc, "is_main_mem"):
			if mem_desc.is_main_mem:
				continue
		build_reg_hierarchy(mem_desc, ptr_regs, actual_regs, alias_regs, initval_regs)

	# generate main register file names for ETISS's 'char* reg_name[]'
	reg_names = [f"{core.main_reg_file.name}{n}" for n in range(core.main_reg_file.ty.length)]
	if core.float_reg_file is not None:
		reg_names += [f"{core.float_reg_file.name}{n}" for n in range(core.float_reg_file.ty.length)]
	# TODO(annnnna42): add float reg names (F0-F31) here

	# if main register file entries have aliases optionally use these for 'char* reg_name[]'
	if aliased_regnames:
		for child in core.main_reg_file.children:
			reg_names[child.range.lower] = child.name
	# TODO(annnnna42): add float reg aliases here

	txt = arch_cpp_template.render(
		start_time=start_time,
		core_name=core.name,
		instr_classes=sorted(core.instr_classes),
		reg_init_code="",
		reg_names=reg_names,
		ptr_regs=ptr_regs,
		actual_regs=actual_regs,
		alias_regs=alias_regs,
		initval_regs=initval_regs,
		procno_memory=core.procno_memory,
		type_info=type_info,
		arch=arch,
	)

	with open(output_path / f"{core.name}Arch.cpp", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_lib(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_lib_template = Template(filename=str(template_dir/'etiss_arch_lib.mako'))

	logger.info("writing architecture lib")

	txt = arch_lib_template.render(
		start_time=start_time,
		core_name=core.name
	)

	with open(output_path / f"{core.name}ArchLib.cpp", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_specific_header(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_specific_header_template = Template(filename=str(template_dir/'etiss_arch_specific_h.mako'))

	logger.info("writing architecture specific header")

	core.main_reg_file.ty.element_type.size = arch.get_const_or_val(core.main_reg_file.ty.element_type.size)
	core.main_reg_file.ty.length = arch.get_const_or_val(core.main_reg_file.ty.length)
	if core.float_reg_file is not None:
		core.float_reg_file.ty.element_type.size = arch.get_const_or_val(core.float_reg_file.ty.element_type.size)
		core.float_reg_file.ty.length = arch.get_const_or_val(core.float_reg_file.ty.length)
	if core.vector_reg_file is not None:
		core.vector_reg_file.ty.element_type.size = arch.get_const_or_val(core.vector_reg_file.ty.element_type.size)
		core.vector_reg_file.ty.length = arch.get_const_or_val(core.vector_reg_file.ty.length)
	if core.csr_reg_file is not None:
		core.csr_reg_file.ty.element_type.size = arch.get_const_or_val(core.csr_reg_file.ty.element_type.size)
		core.csr_reg_file.ty.length = arch.get_const_or_val(core.csr_reg_file.ty.length)

	txt = arch_specific_header_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file,
		float_reg=core.float_reg_file,
		vector_reg=core.vector_reg_file,
		csr_reg=core.csr_reg_file,
		arch=arch
	)

	with open(output_path / f"{core.name}ArchSpecificImp.h", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_specific_cpp(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, virtualstruct_regs: dict, fill_mode: str):
	fill_jit_extensions=None
	fill_length_updater=None
	fill_endianess_compensation=None
	assert isinstance(fill_mode, str)
	fill_mode = fill_mode.lower()
	if fill_mode == "auto":
		extra_headers = set()
		extra_libs = set()
		extra_header_paths = set()
		extra_lib_paths = set()
		has_softfloat = core.float_reg_file is not None
		has_softvector = core.vector_reg_file is not None
		extra_header_paths.add("etiss/jit")
		extra_lib_paths.add("etiss/jit")
		if has_softfloat:
			extra_headers.add("etiss/jit/libsoftfloat.h")
			extra_libs.add("softfloat")
		if has_softvector:
			extra_headers.add("etiss/jit/libsoftvector.h")
			extra_headers.add("etiss/jit/softvector.h")
			extra_libs.add("softvector")
			extra_libs.add("etiss_softvector")
		fill_jit_extensions = Template(filename=str(template_dir/'etiss_jit_extensions.mako')).render(
				extra_headers=";".join(sorted(list(extra_headers))),
				extra_libs=";".join(sorted(list(extra_libs))),
				extra_header_paths=";".join(sorted(list(extra_header_paths))),
				extra_lib_paths=";".join(sorted(list(extra_lib_paths))),
		)
		fill_length_updater = Template(filename=str(template_dir/'etiss_length_updater.mako')).render(core_name=core.name)
	else:
	    assert fill_mode == "empty", f"Unsupported fill_mode: {fill_mode}"
	arch_source_template = Template(filename=str(template_dir/'etiss_arch_specific_cpp.mako'))

	error_fn = None

	for fn in core.functions.values():
		if attribute_info.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn.attributes:
			error_fn = fn
			break

	for fn in core.functions.values():
		if attribute_info.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN in fn.attributes:
			error_fn = fn
			break

	error_callbacks: "dict[int, str]" = {}

	if error_fn is not None:
		for bitsize in core.instr_classes:
			error_bitfield = arch.BitField("error_code", arch.RangeSpec(31, 0), type_info.TypeKind.UINT)
			error_instr = arch.Instruction(f"trap_entry {bitsize}", {attribute_info.InstrAttribute.NO_CONT: None}, [error_bitfield], "", "", None, None)
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
		attr = core.global_irq_en_memory.attributes[attribute_info.MemoryAttribute.ETISS_IS_GLOBAL_IRQ_EN][0]
		if not isinstance(attr, behav.Literal):
			raise M2TypeError(f"IRQ enable mask of {core.global_irq_en_memory.name} is not compile static")
		global_irq_en_mask = attr.value

	txt = arch_source_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file,
		float_reg=core.float_reg_file,
		irq_en_reg=core.irq_en_memory,
		irq_pending_reg=core.irq_pending_memory,
		global_irq_en_reg=core.global_irq_en_memory,
		global_irq_en_mask=global_irq_en_mask,
		error_callbacks=error_callbacks,
		error_fn=error_fn,
		virtualstruct_regs=virtualstruct_regs,
		fill_jit_extensions=fill_jit_extensions,
		fill_length_updater=fill_length_updater,
		fill_endianess_compensation=fill_endianess_compensation,
	)

	with open(output_path / f"{core.name}ArchSpecificImp.cpp", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_gdbcore(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, gdb_mapping: dict):
	arch_gdbcore_template = Template(filename=str(template_dir/'etiss_arch_gdbcore.mako'))

	logger.info("writing gdbcore")

	txt = arch_gdbcore_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file,
		float_reg=core.float_reg_file,
		mapping=gdb_mapping,
	)

	with open(output_path / f"{core.name}GDBCore.h", "w", encoding="utf-8") as f:
		f.write(txt)

def write_arch_cmake(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, separate: bool):
	arch_cmake_template = Template(filename=str(template_dir/'etiss_arch_cmake.mako'))

	logger.info("writing CMakeLists")

	arch_files = [f'{core.name}Instr.cpp']

	# if generation of one instr.cpp per extension is desired, only generate extensions which actually
	# contain instructions
	if separate:
		arch_files += [f'{core.name}_{ext_name}Instr.cpp' for ext_name in core.contributing_types if len(core.instructions_by_ext[ext_name]) > 0]

	txt = arch_cmake_template.render(
		start_time=start_time,
		core_name=core.name,
		arch_files=arch_files
	)

	with open(output_path / "CMakeLists.txt", "w", encoding="utf-8") as f:
		f.write(txt)
