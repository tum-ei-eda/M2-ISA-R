import logging
import pathlib
from typing import Dict, List

from mako.template import Template

from ...metamodel import arch
from .templates import template_dir


logger = logging.getLogger("arch_writer")

def write_child_reg_def(reg: arch.Memory, regs: List[str]):
	logger.debug("processing register %s", reg)
	if arch.MemoryAttribute.IS_PC in reg.attributes or arch.MemoryAttribute.IS_MAIN_MEM in reg.attributes:
		logger.debug("this register is either the PC or main memory, skipping")
		return

	array_txt = f"[{reg.data_range.length}]" if reg.data_range.length > 1 else ""

	if len(reg.children) > 0:
		logger.debug("processing children")
		for child in reg.children:
			write_child_reg_def(child, regs)

		regs.append(f"etiss_uint{reg.actual_size} *{reg.name}{array_txt}")
		regs.append(f"etiss_uint{reg.actual_size} ins_{reg.name}{array_txt}")
	else:
		regs.append(f"etiss_uint{reg.actual_size} {reg.name}{array_txt}")

def write_arch_struct(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_struct_template = Template(filename=str(template_dir/'etiss_arch_struct.mako'))
	regs = []

	for mem_name, mem_desc in core.memories.items():
		write_child_reg_def(mem_desc, regs)

	txt = arch_struct_template.render(
		start_time=start_time,
		core_name=core.name,
		regs=regs
	)

	logger.info("writing architecture struct")
	with open(output_path / f"{core.name}.h", "w") as f:
		f.write(txt)

def write_arch_header(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_h.mako'))

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		instr_classes=sorted(core.instr_classes)
	)

	logger.info("writing architecture class header")
	with open(output_path / f"{core.name}Arch.h", "w") as f:
		f.write(txt)

def build_reg_hierarchy(reg: arch.Memory, ptr_regs: List[arch.Memory], actual_regs: List[arch.Memory], alias_regs: Dict[arch.Memory, arch.Memory], initval_regs: List[arch.Memory]):
	"""Populate the passed lists with memory objects of their category.

	ptr_regs: Registers that need to be a pointer within ETISS
	actual_regs: Registers that are not a pointer
	alias_regs: Registers which are an alias to some other register
	initval_regs: Registers which have initial value(s) defined in the model
	"""

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
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_cpp.mako'))

	ptr_regs = []
	actual_regs = []
	alias_regs = {}
	initval_regs = []

	for mem_name, mem_desc in core.memories.items():
		if mem_desc.is_main_mem:
			continue
		build_reg_hierarchy(mem_desc, ptr_regs, actual_regs, alias_regs, initval_regs)

	reg_names = [f"{core.main_reg_file.name}{n}" for n in range(core.main_reg_file.data_range.length)]

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
		initval_regs=initval_regs
	)

	logger.info("writing architecture class file")
	with open(output_path / f"{core.name}Arch.cpp", "w") as f:
		f.write(txt)

def write_arch_lib(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_lib.mako'))

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name
	)

	logger.info("writing architecture lib")
	with open(output_path / f"{core.name}ArchLib.cpp", "w") as f:
		f.write(txt)

def write_arch_specific_header(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_specific_h.mako'))

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file
	)

	logger.info("writing architecture specific header")
	with open(output_path / f"{core.name}ArchSpecificImp.h", "w") as f:
		f.write(txt)

def write_arch_specific_cpp(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_specific_cpp.mako'))

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file
	)

	logger.info("writing architecture specific file")
	with open(output_path / f"{core.name}ArchSpecificImp.cpp", "w") as f:
		f.write(txt)

def write_arch_gdbcore(core: arch.CoreDef, start_time: str, output_path: pathlib.Path):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_gdbcore.mako'))

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		main_reg=core.main_reg_file
	)

	logger.info("writing gdbcore")
	with open(output_path / f"{core.name}GDBCore.h", "w") as f:
		f.write(txt)

def write_arch_cmake(core: arch.CoreDef, start_time: str, output_path: pathlib.Path, separate: bool):
	arch_header_template = Template(filename=str(template_dir/'etiss_arch_cmake.mako'))

	arch_files = [f'{core.name}Instr.cpp']
	if separate:
		arch_files += [f'{core.name}_{ext_name}Instr.cpp' for ext_name in core.contributing_types]

	txt = arch_header_template.render(
		start_time=start_time,
		core_name=core.name,
		arch_files=arch_files
	)

	logger.info("writing CMakeLists")
	with open(output_path / "CMakeLists.txt", "w") as f:
		f.write(txt)
