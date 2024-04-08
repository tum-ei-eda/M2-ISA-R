# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Viewer tool to visualize an M2-ISA-R model hierarchy."""

import re
import argparse
import logging
import pathlib
import pickle
from copy import deepcopy
from collections import defaultdict
from mako.template import Template

from .utils import generate_encoding
from . import visitor

from ...metamodel import M2_METAMODEL_VERSION, M2Model, arch, patch_model
from ...metamodel.utils.expr_preprocessor import (process_attributes,
                                                  process_functions,
                                                  process_instructions)

HEADER_CONTENT = """
= M2-ISA-R Metamodel
:doctype: article
:encoding: utf-8
:lang: en
:toc: left
:toclevels: 3
:numbered:
:stem: latexmath
:le: &#8804;
:ge: &#8805;
:ne: &#8800;
:approx: &#8776;
:inf: &#8734;

:sectnums!:
"""

MAKO_TEMPLATE_INSTR = """
==== ${name}

===== Assembly

```asm
${mnemonic} ${assembly}
```

===== Behavior

```c
${behavior}
```


===== Encoding

```wavedrom
${encoding}
```

===== Exceptions

% if throws:

Throws: ${throws.name}

% else:

N/A

% endif

===== Attributes

% if attributes:
    % for key, value in attributes.items():
        % if value:
* ${key.name} (${value})
        % else:
* ${key.name}
        % endif
    % endfor
% else:
N/A
% endif

"""

logger = logging.getLogger("isa_manual")


class CoreDSL2Writer:
    def __init__(self):
        self.text = ""
        self.indent_str = "    "
        self.level = 0

    @property
    def indent(self):
        return self.indent_str * self.level

    @property
    def isstartofline(self):
        return len(self.text) == 0 or self.text[-1] == "\n"

    @property
    def needsspace(self):
        return len(self.text) != 0 and self.text[-1] not in ["\n", " "]

    def write(self, text, nl=False):
        if isinstance(text, int):
            text = str(text)
        assert isinstance(text, str)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if self.isstartofline:
                self.text += self.indent
            self.text += line
            if (i < len(lines) - 1) or nl:
                self.text += "\n"

    def write_line(self, text):
        self.write(text, nl=True)

    def enter_block(self, br=True, nl=True):
        if br:
            if self.needsspace:
                self.write(" ")
            self.write("{", nl=nl)
        self.level += 1

    def leave_block(self, br=True, nl=True):
        assert self.level > 0
        self.level -= 1
        if br:
            self.write("}", nl=nl)

    def write_type(self, data_type, size):
        # print("write_type")
        # print("data_type", data_type)
        # print("size", size)
        if data_type == arch.DataType.U:
            self.write("unsigned")
        elif data_type == arch.DataType.S:
            self.write("signed")
        elif data_type == arch.DataType.NONE:
            self.write("void")
        else:
            raise NotImplementedError(f"Unsupported type: {data_type}")
        if size:
            self.write("<")
            self.write(size)
            self.write(">")

    def write_behavior2(self, operation, drop_first=False):
        # Eliminate PC increment
        if drop_first:
            operation.statements = operation.statements[1:]
        operation.generate(self)

    def write_behavior(self, instruction):
        self.write("behavior: ")
        operation = instruction.operation
        self.write_operation(operation)
        # self.write(";", nl=True)


def sort_instruction(entry: "tuple[tuple[int, int], arch.Instruction]"):
    """Instruction sort key function. Sorts most restrictive encoding first."""
    (code, mask), _ = entry
    return bin(mask).count("1"), code
    #return code, bin(mask).count("1")
  # TODO: sort by name

def main():
    """Main app entrypoint."""

    # read command line args
    parser = argparse.ArgumentParser()
    parser.add_argument('top_level', help="A .m2isarmodel file containing the models to generate.")
    parser.add_argument('-s', '--separate', action='store_true', help="Generate separate .adoc files for each core.")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    parser.add_argument('--output', '-o', default="out.adoc", help="TODO")
    args = parser.parse_args()

    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))

    # resolve model paths
    top_level = pathlib.Path(args.top_level)
    abs_top_level = top_level.resolve()
    # search_path = abs_top_level.parent.parent
    model_fname = abs_top_level
    output_file = pathlib.Path(args.output)

    if args.separate:
        raise NotImplementedEroor

    if abs_top_level.suffix == ".core_desc":
        logger.warning(".core_desc file passed as input. This is deprecated behavior, please change your scripts!")
        # search_path = abs_top_level.parent
        model_path = search_path.joinpath('gen_model')

        if not model_path.exists():
            raise FileNotFoundError('Models not generated!')
        model_fname = model_path / (abs_top_level.stem + '.m2isarmodel')

    # output_base_path = search_path.joinpath('gen_output')
    # output_base_path.mkdir(exist_ok=True)

    logger.info("loading models")

    # load models
    with open(model_fname, 'rb') as f:
        model_obj: "M2Model" = pickle.load(f)

    if model_obj.model_version != M2_METAMODEL_VERSION:
        logger.warning("Loaded model version mismatch")

    models = model_obj.models

    out_text = ""

    out_text += HEADER_CONTENT

    # preprocess model
    for core_name, core in models.items():
        logger.info("preprocessing model %s", core_name)
        process_functions(core)
        process_instructions(core)
        process_attributes(core)

    # add each core to the treeview
    for core_name, core_def in sorted(models.items()):
        logger.info("processing core %s", core_name)
        out_text += f"== {core_name}\n"
        # consts_id = tree.insert(core_id, tk.END, text="Constants")
        # for const_name, const_def in sorted(core_def.constants.items()):
        #     tree.insert(consts_id, tk.END, text=const_name, values=(const_def.value,))

        # add memories to tree
        # mems_id = tree.insert(core_id, tk.END, text="Memories")
        # for mem_name, mem_def in sorted(core_def.memories.items()):
        #     tree.insert(mems_id, tk.END, text=mem_name, values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",))

        # add memory aliases to tree
        # alias_id = tree.insert(core_id, tk.END, text="Memory Aliases")
        # for mem_name, mem_def in sorted(core_def.memory_aliases.items()):
        #     tree.insert(alias_id, tk.END, text=f"{mem_name} ({mem_def.parent.name})", values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",))

        # add auxillary attributes
        # tree.insert(core_id, tk.END, text="Main Memory Object", values=(core_def.main_memory,))
        # tree.insert(core_id, tk.END, text="Main Register File Object", values=(core_def.main_reg_file,))
        # tree.insert(core_id, tk.END, text="PC Memory Object", values=(core_def.pc_memory,))

        # add functions to tree
        # fns_id = tree.insert(core_id, tk.END, text="Functions")
        # for fn_name, fn_def in core_def.functions.items():
        #     fn_id = tree.insert(fns_id, tk.END, text=fn_name, values=("extern" if fn_def.extern else ""))

        #     # add returns and throws information
        #     return_str = "None" if fn_def.size is None else f"{fn_def.data_type} {fn_def.size}"
        #     tree.insert(fn_id, tk.END, text="Return", values=(return_str,))
        #     tree.insert(fn_id, tk.END, text="Throws", values=(fn_def.throws))

        #     # generate and add attributes
        #     attrs_id = tree.insert(fn_id, tk.END, text="Attributes")

        #     for attr, ops in fn_def.attributes.items():
        #         attr_id = tree.insert(attrs_id, tk.END, text=attr)
        #         for op in ops:
        #             context = TreeGenContext(tree, attr_id)
        #             op.generate(context)

        #     # generate and add parameters
        #     params_id = tree.insert(fn_id, tk.END, text="Parameters")

        #     for param_name, param_def in fn_def.args.items():
        #         tree.insert(params_id, tk.END, text=param_name, values=(f"{param_def.data_type} {param_def.size}",))

        #     # generate and add function behavior
        #     context = TreeGenContext(tree, fn_id)
        #     fn_def.operation.generate(context)

        # group instructions by size
        instrs_by_size = defaultdict(dict)

        for k, v in core_def.instructions.items():
            instrs_by_size[v.size][k] = v

        # sort instructions by encoding
        # for k, v in instrs_by_size.items():
        #     instrs_by_size[k] = dict(sorted(v.items(), key=sort_instruction, reverse=True))

        # instrs_top_id = tree.insert(core_id, tk.END, text="Instructions")

        # generate instruction size groups
        for size, instrs in sorted(instrs_by_size.items()):
            # instrs_id = tree.insert(instrs_top_id, tk.END, text=f"Width {size}")

            # generate instructions
            out_text += f"=== {size}-bit Instructions\n"
            for (code, mask), instr_def in instrs.items():
                opcode_str = "{code:0{width}x}:{mask:0{width}x}".format(code=code, mask=mask, width=int(instr_def.size/4))
                logger.info("processing instruction %s", instr_def.name)

                # instr_id = tree.insert(instrs_id, tk.END, text=f"{instr_def.ext_name} : {instr_def.name}", values=(opcode_str,), tags=("mono",))

                # generate encoding
                enc_str = []
                for enc in instr_def.encoding:
                    if isinstance(enc, arch.BitVal):
                        enc_str.append(f"{enc.value:0{enc.length}b}")
                    elif isinstance(enc, arch.BitField):
                        enc_str.append(f"{enc.name}[{enc.range.upper}:{enc.range.lower}]")

                # tree.insert(instr_id, tk.END, text="Encoding", values=(" ".join(enc_str),))
                # tree.insert(instr_id, tk.END, text="Assembly", values=(instr_def.disass,))
                # attrs_id = tree.insert(instr_id, tk.END, text="Attributes")

                # generate attributes
                # for attr, ops in instr_def.attributes.items():
                #     attr_id = tree.insert(attrs_id, tk.END, text=attr.name)
                #     for op in ops:
                #         context = TreeGenContext(tree, attr_id)
                #         op.generate(context)

                # generate behavior
                # context = TreeGenContext(tree, instr_id)
                # instr_def.operation.generate(context)
                writer = CoreDSL2Writer()
                patch_model(visitor)
                writer.write_behavior2(instr_def.operation, drop_first=True)
                behavior_text = writer.text
                asm_str = None
                if instr_def.disass:
                    asm_str = instr_def.disass.replace("\"", "")
                    asm_str = re.sub(r"{([a-zA-Z0-9]+)}", r"\g<1>", re.sub(r"{([a-zA-Z0-9]+):[#0-9a-zA-Z\.]+}", r"{\g<1>}", re.sub(r"name\(([a-zA-Z0-9]+)\)", r"\g<1>", asm_str)))
                content_template = Template(MAKO_TEMPLATE_INSTR)
                encoding_text = generate_encoding(instr_def.encoding)
                content_text = content_template.render(name=instr_def.name, assembly=asm_str if asm_str else "N/A", mnemonic=instr_def.name.lower().replace("_", "."), encoding=encoding_text, attributes=instr_def.attributes, throws=arch.FunctionThrows(instr_def.throws), behavior=behavior_text)
                out_text += content_text
    with open(output_file, "w") as f:
        f.write(out_text)

    #tree.tag_configure("mono", font=font.nametofont("TkFixedFont"))


if __name__ == "__main__":
    main()
