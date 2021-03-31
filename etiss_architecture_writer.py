import pathlib
from typing import List

from mako.template import Template

import model_classes
import model_classes.arch


def write_child_reg(reg: model_classes.arch.Memory):
    if len(reg.children) > 0:
        for reg in reg.children:
            write_child_reg(reg)
    pass

def write_arch_struct(core: model_classes.arch.CoreDef, start_time: str, output_path: pathlib.Path):
    arch_struct_template = Template(filename='templates/etiss_arch_struct.mako')

    core_name = core.name

    for mem_name, mem_desc in core.memories.items():
        if len(mem_desc.children) > 0:
            for reg in mem_desc.children:
                write_child_reg(reg)
