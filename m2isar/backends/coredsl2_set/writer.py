# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Convert M2-ISA-R SET metamodel to .core_desc file."""

import argparse
import logging
import pathlib
import pickle
from typing import Union

from . import visitor
from m2isar.metamodel import arch, patch_model, behav
from m2isar.metamodel import M2_METAMODEL_VERSION, M2Model

logger = logging.getLogger("coredsl2_writer")


class DropUnusedContext:
    def __init__(self, names: "list[str]"):
        self.names = names
        self.to_keep = set()

    @property
    def to_drop(self):
        return set(name for name in self.names if name not in self.to_keep)

    def track(self, name: str):
        if name in self.names:
            # logger.debug("Tracked use of %s", name)
            self.to_keep.add(name)


class CoreDSL2Writer:
    def __init__(self, legacy: bool = False):
        self.text = ""
        self.indent_str = "    "
        self.level = 0
        self.legacy = legacy
        self.arch = True

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

    def write_attribute(self, attr, val=None):
        if self.needsspace:
            self.write(" ")
        self.write("[[")
        self.write(attr.name.lower())
        if val:
            self.write("=")
            self.write(val)  # TODO: operation
        self.write("]]")
        # print("key", key)
        # print("value", value)

    def write_attributes(self, attributes):
        for attr, val in attributes.items():
            self.write_attribute(attr, val)
        # input("inp")

    def write_function(self, function):
        if function.static:
            self.write("static ")
        if function.extern:
            self.write("extern ")
        self.write_type(function.data_type, None)
        if function.size is not None:
            self.write("<")
            self.write(f"{function.size}")
            self.write(">")
        self.write(" ")
        self.write(function.name)
        self.write("(")
        for i, param in enumerate(function.args.values()):
            self.write_type(param.data_type, param.size)
            if param.name is not None:
                self.write(" ")
                self.write(param.name)
            if i < len(function.args) - 1:
                self.write(", ")
        self.write(")")
        self.write_attributes(function.attributes)
        # self.enter_block()
        # self.write_behavior(instruction)
        if function.extern:
            self.write_line(";")
        else:
            function.operation.generate(self)
        # self.leave_block()

    def write_functions(self, functions):
        self.write("functions")
        # TODO: attributes
        self.enter_block()
        for function in functions.values():
            self.write_function(function)
        self.leave_block()

    def write_encoding_val(self, bitval):
        value = bitval.value
        width = bitval.length
        self.write(width)
        self.write("'b")
        bitstr = bin(value)[2:].zfill(width)
        self.write(bitstr)

    def write_encoding_field(self, bitfield):
        name = bitfield.name
        rng = bitfield.range
        # print("rng", rng)
        # input("aaaa")
        self.write(name)
        self.write(f"[{rng.upper}:{rng.lower}]")

    def write_encoding(self, encoding):
        self.write("encoding: ")
        # print("encoding", encoding, dir(encoding))
        for i, elem in enumerate(encoding):
            if isinstance(elem, arch.BitVal):
                self.write_encoding_val(elem)
            elif isinstance(elem, arch.BitField):
                self.write_encoding_field(elem)
            else:
                assert False
            if i < len(encoding) - 1:
                self.write(" :: ")
        self.write(";", nl=True)

    def write_assembly(self, instruction):
        self.write("assembly: ")
        mnemonic = instruction.mnemonic
        assembly = instruction.assembly
        if mnemonic and not self.legacy:
            self.write("{")
            self.write(f'"{mnemonic}"')
            self.write(", ")
        if assembly is None:
            assembly = ""
        self.write(f'"{assembly}"')
        if mnemonic and not self.legacy:
            self.write("}")
        self.write(";", nl=True)

    def write_behavior(self, instruction):
        self.write("behavior: ")
        op = instruction.operation
        op.generate(self)
        # self.write(";", nl=True)

    def write_instruction(self, instruction):
        self.write(instruction.name)
        self.write_attributes(instruction.attributes)
        self.enter_block()
        self.write_encoding(instruction.encoding)
        self.write_assembly(instruction)
        self.write_behavior(instruction)
        self.leave_block()

    def write_instructions(self, instructions):
        self.write("instructions")
        # TODO: attributes?
        self.enter_block()
        for instruction in instructions.values():
            self.write_instruction(instruction)
        self.leave_block()

    def write_architectural_state(self, set_def):
        if len(set_def.memories) == 0 and len(set_def.constants) == 0:
            return
        self.write("architectural_state")
        self.enter_block()
        # TODO: scalars, memories,...
        for mem_name, mem_def in set_def.memories.items():
            # TODO: move to write_memorie(s)
            self.write("register ")
            self.write_type(arch.DataType.U, mem_def.size)
            self.write(f" {mem_name}")
            if mem_def.range.length is not None:
                self.write("[")
                self.write(mem_def.range.length)
                self.write("]")
            self.write_attributes(mem_def.attributes)
            self.write_line(";")
        if len(set_def.constants) > 0:
            raise NotImplementedError("constants")
        self.leave_block()

    def write_set(self, set_def: arch.InstructionSet):
        self.write("InstructionSet ")
        self.write(set_def.name)
        # TODO: attributes
        # TODO: extends
        if set_def.extension:
            self.write(" extends ")
            self.write(", ".join(set_def.extension))
        self.enter_block()
        if set_def.functions:
            self.write_functions(set_def.functions)
        if self.arch:
            self.write_architectural_state(set_def)
        self.write_instructions(set_def.instructions)
        self.leave_block()
        self.write("\n")

    #     for instr_name, instr_def in set_def.instructions.items():
    #         logger.debug("writing instr %s", instr_def.name)
    #         # instr_def.operation.generate(context)
    #     # input("CONT1")

    def write_core(self, core_def: arch.CoreDef):
        self.write(f"Core {core_def.name} provides {', '.join(core_def.contributing_types)}")
        self.enter_block()
        self.write("architectural_state")
        self.enter_block()
        self.write(
            "CSR[0x000] = 0x0000000B; // ustatus\n"
            "CSR[RV_CSR_SSTATUS] = 0x0000000B; // sstatus\n"
            "CSR[RV_CSR_MSTATUS] = 0x0000000B; // mstatus\n"
            "\n"
            f"CSR[RV_CSR_MISA] = {'0x800000000014112D' if core_def.constants['XLEN'].value == 64 else '0x4014112D'}; // misa\n"
            "\n"
            "CSR[0xC10] = 0x00000003;\n"
            "\n"
            "CSR[RV_CSR_MIE] = 0xFFFFFBBB; // mie\n"
            "CSR[RV_CSR_SIE] = CSR[0x304] & (~(0x888)); // sie\n"
            "CSR[0x004] = CSR[0x304] & (~(0xAAA)); // uie",
            True,
        )
        self.leave_block()
        self.leave_block()


def write_includes(writer, used_extensions, includes_prefix: str = "rv_base/", tum_includes_prefix: str = ""):
    if "RV32I" in used_extensions:
        writer.write(f'import "{includes_prefix}RV32I.core_desc"', nl=True)
    if "RV64I" in used_extensions:
        writer.write(f'import "{includes_prefix}RV64I.core_desc"', nl=True)
    if "RV32M" in used_extensions or "RV64M" in used_extensions:
        writer.write(f'import "{includes_prefix}RVM.core_desc"', nl=True)
    if "RV32IC" in used_extensions or "RV64IC" in used_extensions:
        writer.write(f'import "{includes_prefix}RVC.core_desc"', nl=True)
    if "RV32F" in used_extensions or "RV64F" in used_extensions:
        writer.write(f'import "{includes_prefix}RVF.core_desc"', nl=True)
    if "RV32D" in used_extensions or "RV64D" in used_extensions:
        writer.write(f'import "{includes_prefix}RVD.core_desc"', nl=True)

    # add tum extensions at the end
    if "tum_csr" in used_extensions:
        writer.write(f'import "{tum_includes_prefix}tum_mod.core_desc"', nl=True)
        writer.write(f'import "{tum_includes_prefix}tum_rva.core_desc"', nl=True)
        writer.write(f'import "{tum_includes_prefix}tum_rvm.core_desc"', nl=True)
    writer.write("\n")


def gen_cdsl_code(
    model_obj,
    with_includes: bool = True,
    includes_prefix: str = "rv_base/",
    tum_includes_prefix: str = "",
    legacy: bool = False,
):
    # preprocess model
    # print("model", model["sets"]["XCoreVMac"].keys())
    writer = CoreDSL2Writer(legacy=legacy)

    # write imports
    core_defs = [core for core in model_obj.cores.values()]
    if core_defs:  # TODO add imports if an instruction set extends another set
        if with_includes:
            used_extensions = set()
            # gather needed imports
            for core_def in core_defs:
                used_extensions.update(core_def.contributing_types)

            write_includes(writer, used_extensions)

    for set_name, set_def in model_obj.sets.items():
        logger.debug("writing set %s", set_def.name)
        if with_includes:
            write_includes(writer, set_def.extension)
        patch_model(visitor)
        writer.write_set(set_def)
        # context = DropUnusedContext(list(set_def.constants.keys()))

    if core_defs:
        for core_def in core_defs:
            logger.info("Writing Core: %s", core_def.name)
            writer.write_core(core_def)
    return writer.text


def main():
    """Main app entrypoint."""

    # read command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel or .m2isarmodel (SET only) file.")
    parser.add_argument(
        "--log",
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
    )
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--legacy", action="store_true")
    args = parser.parse_args()

    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))

    # resolve model paths
    top_level = pathlib.Path(args.top_level)
    # abs_top_level = top_level.resolve()

    if args.output is None:
        assert top_level.suffix == ".m2isarmodel"

        out_path = top_level.parent / (top_level.stem + ".core_desc")
    else:
        out_path = pathlib.Path(args.output)

    logger.info("loading models")

    # load models
    # with open(top_level, "rb") as f:
    #     # models: "dict[str, arch.CoreDef]" = pickle.load(f)
    #     model: dict = pickle.load(f)
    #     assert "sets" in model

    with open(top_level, "rb") as f:
        model_obj: M2Model = pickle.load(f)

    if model_obj.model_version != M2_METAMODEL_VERSION:
        logger.warning("Loaded model version mismatch")

    cdsl_code = gen_cdsl_code(model_obj, legacy=args.legacy)

    with open(out_path, "w") as f:
        f.write(cdsl_code)


if __name__ == "__main__":
    main()
