import logging
import pathlib
from collections import defaultdict
from typing import Dict, List

from mako.template import Template

import model_classes

logger = logging.getLogger("arch_writer")

def write_child_reg_def(reg: model_classes.Memory, regs: List[str]):
    logger.debug("processing register %s", reg)
    if model_classes.RegAttribute.IS_PC in reg.attributes or model_classes.SpaceAttribute.IS_MAIN_MEM in reg.attributes:
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

def write_arch_struct(core: model_classes.CoreDef, start_time: str, output_path: pathlib.Path):
    logger.info("generating architecture struct")

    arch_struct_template = Template(filename='templates/etiss_arch_struct.mako')
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

def write_arch_header(core: model_classes.CoreDef, start_time: str, output_path: pathlib.Path):
    logger.info("generating architecture class header")

    arch_header_template = Template(filename='templates/etiss_arch_h.mako')

    txt = arch_header_template.render(
        start_time=start_time,
        core_name=core.name,
        instr_classes=sorted(core.instr_classes)
    )

    logger.info("writing architecture class header")
    with open(output_path / f"{core.name}Arch.h", "w") as f:
        f.write(txt)

def build_reg_hierarchy(reg: model_classes.Memory, ptr_regs: List[model_classes.Memory], actual_regs: List[model_classes.Memory], alias_regs: Dict[model_classes.Memory, model_classes.Memory]):
    logger.debug("processing register %s", reg)

    if len(reg.children) > 0:
        for child in reg.children:
            if child.is_main_mem:
                logger.warning("main memory is a child memory of %s", reg)
                continue
            build_reg_hierarchy(child, ptr_regs, actual_regs, alias_regs)
            alias_regs[child] = reg
        ptr_regs.append(reg)
    else:
        actual_regs.append(reg)

def write_arch_cpp(core: model_classes.CoreDef, start_time: str, output_path: pathlib.Path, aliased_regnames: bool=True):
    logger.info("generating architecture class file")

    arch_header_template = Template(filename='templates/etiss_arch_cpp.mako')

    ptr_regs = []
    actual_regs = []
    alias_regs = {}

    for mem_name, mem_desc in core.memories.items():
        if mem_desc.is_main_mem:
            continue
        build_reg_hierarchy(mem_desc, ptr_regs, actual_regs, alias_regs)

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
        alias_regs=alias_regs
    )

    logger.info("writing architecture class file")
    with open(output_path / f"{core.name}Arch.cpp", "w") as f:
        f.write(txt)
