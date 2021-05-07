import pathlib
from typing import List

from mako.template import Template

import model_classes


def write_child_reg(reg: model_classes.Memory):
    if len(reg.children) > 0:
        for child in reg.children:
            write_child_reg(child)
        print(f"{reg.actual_size} *{reg.name}")
        print(f"{reg.actual_size} ins_{reg.name}")
    else:
        print(f"{reg.actual_size} {reg.name}")

def write_arch_struct(core: model_classes.CoreDef, start_time: str, output_path: pathlib.Path):
    arch_struct_template = Template(filename='templates/etiss_arch_struct.mako')

    core_name = core.name

    for mem_name, mem_desc in core.memories.items():
        write_child_reg(mem_desc)
