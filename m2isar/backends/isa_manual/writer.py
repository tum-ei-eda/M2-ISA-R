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
    model_fname = abs_top_level
    output_file = pathlib.Path(args.output)

    if args.separate:
        raise NotImplementedEroor

    if abs_top_level.suffix == ".core_desc":
        logger.warning(".core_desc file passed as input. This is deprecated behavior, please change your scripts!")
        model_path = search_path.joinpath('gen_model')

        if not model_path.exists():
            raise FileNotFoundError('Models not generated!')
        model_fname = model_path / (abs_top_level.stem + '.m2isarmodel')

    logger.info("loading models")

    # load models
    with open(model_fname, 'rb') as f:
        model_obj: "M2Model" = pickle.load(f)

    if model_obj.model_version != M2_METAMODEL_VERSION:
        logger.warning("Loaded model version mismatch")

    models = model_obj.cores

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

        # group instructions by size
        instrs_by_size = defaultdict(dict)

        for k, v in core_def.instructions.items():
            instrs_by_size[v.size][k] = v

        # generate instruction size groups
        for size, instrs in sorted(instrs_by_size.items()):

            # generate instructions
            out_text += f"=== {size}-bit Instructions\n"
            for (code, mask), instr_def in instrs.items():
                opcode_str = "{code:0{width}x}:{mask:0{width}x}".format(code=code, mask=mask, width=int(instr_def.size/4))
                logger.info("processing instruction %s", instr_def.name)

                # generate encoding
                enc_str = []
                for enc in instr_def.encoding:
                    if isinstance(enc, arch.BitVal):
                        enc_str.append(f"{enc.value:0{enc.length}b}")
                    elif isinstance(enc, arch.BitField):
                        enc_str.append(f"{enc.name}[{enc.range.upper}:{enc.range.lower}]")

                writer = CoreDSL2Writer()
                patch_model(visitor)
                writer.write_behavior2(instr_def.operation, drop_first=True)
                behavior_text = writer.text
                asm_str = None
                if instr_def.assembly:
                    asm_str = instr_def.assembly.replace("\"", "")
                    asm_str = re.sub(r"{([a-zA-Z0-9]+)}", r"\g<1>", re.sub(r"{([a-zA-Z0-9]+):[#0-9a-zA-Z\.]+}", r"{\g<1>}", re.sub(r"name\(([a-zA-Z0-9]+)\)", r"\g<1>", asm_str)))
                content_template = Template(MAKO_TEMPLATE_INSTR)
                encoding_text = generate_encoding(instr_def.encoding)
                content_text = content_template.render(name=instr_def.name, mnemonic=instr_def.mnemonic, assembly=asm_str if asm_str else "N/A", encoding=encoding_text, attributes=instr_def.attributes, throws=arch.FunctionThrows(instr_def.throws), behavior=behavior_text)
                out_text += content_text
    with open(output_file, "w") as f:
        f.write(out_text)


if __name__ == "__main__":
    main()
