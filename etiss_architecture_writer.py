import logging
import pathlib
from typing import List

from mako.template import Template

import model_classes

logger = logging.getLogger("arch_writer")

def write_child_reg(reg: model_classes.Memory, regs: List[str]):
    logger.debug("processing register %s", reg)
    if model_classes.RegAttribute.IS_PC in reg.attributes or model_classes.SpaceAttribute.IS_MAIN_MEM in reg.attributes:
        logger.debug("this register is either the PC or main memory, skipping")
        return

    array_txt = f"[{reg.data_range.length}]" if reg.data_range.length > 1 else ""

    if len(reg.children) > 0:
        logger.debug("processing children")
        for child in reg.children:
            write_child_reg(child, regs)

        regs.append(f"etiss_uint{reg.actual_size} *{reg.name}{array_txt}")
        regs.append(f"etiss_uint{reg.actual_size} ins_{reg.name}{array_txt}")
    else:
        regs.append(f"etiss_uint{reg.actual_size} {reg.name}{array_txt}")

def write_arch_struct(core: model_classes.CoreDef, start_time: str, output_path: pathlib.Path):
    logger.info("generating architecture struct")

    arch_struct_template = Template(filename='templates/etiss_arch_struct.mako')
    regs = []

    for mem_name, mem_desc in core.memories.items():
        write_child_reg(mem_desc, regs)

    txt = arch_struct_template.render(
        start_time=start_time,
        core_name=core.name,
        regs=regs
    )

    logger.info("writing architecture struct")
    with open(output_path / f"{core.name}.h", "w") as f:
        f.write(txt)
