# SPDX-License-Identifier: Apache-2.0
"""Export instruction sets with the future-paper API and upstream typed visitor."""
import argparse
import copy
import json
import logging
from pathlib import Path

from ...metamodel import load_model, type_info
from ..coredsl2.utils import CoreDSL2Writer as TypedCoreDSL2Writer
from ..coredsl2.visitor import CDSLWriterVisitor


class CoreDSL2Writer(TypedCoreDSL2Writer):
    def __init__(self, legacy=False):
        super().__init__(CDSLWriterVisitor(), reduced=False)
        self.legacy = legacy

    def write_assembly(self, instruction):
        if self.legacy:
            self.write_line("assembly: " + json.dumps(instruction.assembly or "") + ";")
        else:
            super().write_assembly(instruction)

    def write_encoding(self, encoding):
        if any(field is None for field in encoding):
            self.write_line("encoding: auto;")
        else:
            super().write_encoding(encoding)

    def write_behavior(self, instruction, drop_first=False):
        self.write("behavior:")
        self.enter_block()
        self.visitor.generate(instruction.operation, self)
        self.leave_block()

    def write_instruction(self, instruction):
        self.write(instruction.name)
        self.write_attributes(instruction.attributes)
        self.enter_block()
        if not instruction.has_encoding and instruction.operands:
            self.write("operands:")
            self.enter_block()
            for operand in instruction.operands.values():
                self.write_type(type_info.PrimitiveType(
                    type_info.TypeKind.INT if operand.signed else type_info.TypeKind.UINT, operand.size))
                self.write(" " + operand.name)
                self.write_attributes(operand.attributes)
                self.write_line(";")
            self.leave_block()
        self.write_encoding(instruction.encoding)
        self.write_assembly(instruction)
        self.write_behavior(instruction)
        self.leave_block()

    def write_set(self, set_def):
        # The upstream writer emits the encoded collection. Include unencoded
        # instructions as well so an export cannot silently drop custom ISAXes.
        set_def = copy.copy(set_def)
        set_def.instructions = dict(set_def.instructions)
        set_def.instructions.update(set_def.unencoded_instructions)
        super().write_set(set_def)
        self.write("\n")


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


def gen_cdsl_code(model_obj, with_includes=True, includes_prefix="rv_base/", tum_includes_prefix="", legacy=False):
    """Generate CoreDSL without modifying the caller's model or behavior."""
    model_obj = copy.deepcopy(model_obj)
    writer = CoreDSL2Writer(legacy=legacy)
    if with_includes:
        extensions = set()
        for core in model_obj.cores.values():
            extensions.update(core.contributing_types)
        for instruction_set in model_obj.sets.values():
            extensions.update(instruction_set.extension)
        write_includes(writer, extensions, includes_prefix, tum_includes_prefix)
    for instruction_set in model_obj.sets.values():
        writer.write_set(instruction_set)
    for core in model_obj.cores.values():
        writer.write_core(core)
    return writer.text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("top_level", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log.upper()))
    model = load_model(args.top_level)
    output = args.output or args.top_level.with_suffix(".core_desc")
    output.write_text(gen_cdsl_code(model, legacy=args.legacy), encoding="utf-8")


if __name__ == "__main__":
    main()
