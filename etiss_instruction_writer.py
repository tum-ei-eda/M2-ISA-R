import pathlib
from contextlib import ExitStack

from mako.template import Template

import model_classes
from etiss_instruction_generator import (generate_functions,
                                         generate_instructions)
import logging

logger = logging.getLogger("instruction_writer")

def write_functions(core: model_classes.CoreDef, start_time: str, output_path: pathlib.Path):
    fn_set_header_template = Template(filename='templates/etiss_function_set_header.mako')
    fn_set_footer_template = Template(filename='templates/etiss_function_set_footer.mako')

    core_name = core.name

    with open(output_path / f'{core_name}Funcs.h', 'w') as funcs_f:
        fn_set_str = fn_set_header_template.render(
            start_time=start_time,
            core_name=core_name
        )

        funcs_f.write(fn_set_str)

        for fn_name, templ_str in generate_functions(core):
            logger.info("processing function %s", fn_name)
            funcs_f.write(templ_str)

        fn_set_str = fn_set_footer_template.render()

        funcs_f.write(fn_set_str)

def write_instructions(core: model_classes.CoreDef, start_time: str, output_path: pathlib.Path, separate: bool):
    instr_set_template = Template(filename='templates/etiss_instruction_set.mako')

    outfiles = {}
    core_name = core.name

    with ExitStack() as stack:
        if separate:
            outfiles = {ext_name: stack.enter_context(open(output_path / f'{core_name}_{ext_name}Instr.cpp', 'w')) for ext_name in core.contributing_types}

        outfiles['default'] = stack.enter_context(open(output_path / f'{core_name}Instr.cpp', 'w'))

        for extension_name, out_f in outfiles.items():
            instr_set_str = instr_set_template.render(
                start_time=start_time,
                extension_name=extension_name,
                core_name=core_name
            )

            out_f.write(instr_set_str)

        for instr_name, (code, mask), ext_name, templ_str in generate_instructions(core):
            logger.info("processing instruction %s", instr_name)
            # save instruction code to file
            outfiles.get(ext_name, outfiles['default']).write(templ_str)
