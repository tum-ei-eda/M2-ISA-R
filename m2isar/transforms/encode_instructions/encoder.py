# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import argparse
import logging
import pathlib
import pickle

from ...metamodel import M2_METAMODEL_VERSION, M2Model
from .operands import Operand
from .instr_encodings import _reset_enc_generators, get_mm_encoding

logger = logging.getLogger("set_parser")


def encode_instructions(instructions):
    # print("encode_instructions")
    ret = []
    for instr_def in instructions:
        print("instr_def", instr_def)
        assert not instr_def.has_encoding
        in_operands = {}
        out_operands = {}
        # print("instr_def.operands", instr_def.operands)
        for operand_def in instr_def.operands.values():
            # print("operand_def", operand_def)
            # print("operand_def.name", operand_def.name)
            # print("operand_def.size", operand_def.size)
            # print("operand_def.signed", operand_def.signed)
            # print("operand_def.attributes", operand_def.attributes)
            attrs = operand_def.attributes
            print("attrs", attrs)  # TODO: fix parsing of operand attrs
            name = operand_def.name
            width = operand_def.size
            immediate = "imm" in name
            direction = "in" if name[:2] == "rs" or immediate else "out"
            sign = "s" if operand_def.signed else "u"
            operand = Operand(width=width, sign=sign, immediate=immediate)
            if direction.lower() == "in":
                in_operands[operand_def.name] = operand
            else:
                out_operands[operand_def.name] = operand
        # print("in_operands", in_operands)
        # print("out_operands", out_operands)
        # assert len(out_operands) == 1
        enc = get_mm_encoding(in_operands, out_operands)
        # print("enc", enc)
        instr_def.encoding = enc
        instr_def.process_encoding()
        # print("instr_def", instr_def)
        ret.append(instr_def)
        # input("*")
    return ret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel file containing the models to generate.")
    parser.add_argument("-I", dest="includes", action="append", type=str, help="Extra include dirs.")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--inplace", "-i", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log.upper()))

    top_level = pathlib.Path(args.top_level)

    with open(top_level, "rb") as f:
        model_obj: M2Model = pickle.load(f)

    if model_obj.model_version != M2_METAMODEL_VERSION:
        logger.warning("Loaded model version mismatch")

    for core_name, core_def in model_obj.cores.items():
        _reset_enc_generators()
        unencoded_instructions = list(core_def.unencoded_instructions.values())
        if len(unencoded_instructions) == 0:
            continue
        encoded_instructions = encode_instructions(unencoded_instructions)
        encoded_instructions_dict = {(instr_def.code, instr_def.mask) for instr_def in encoded_instructions}
        core_def.instructions.update(encoded_instructions_dict)

    for set_name, set_def in model_obj.sets.items():
        _reset_enc_generators()
        unencoded_instructions = list(set_def.unencoded_instructions.values())
        if len(unencoded_instructions) == 0:
            continue
        encoded_instructions = encode_instructions(unencoded_instructions)
        encoded_instructions_dict = {(instr_def.code, instr_def.mask): instr_def for instr_def in encoded_instructions}
        set_def.instructions.update(encoded_instructions_dict)

    if args.output is None:
        assert args.inplace
        out_path = top_level
    else:
        assert not args.inplace
        out_path = pathlib.Path(args.output)

    logger.info("dumping model")
    with open(out_path, "wb") as f:
        pickle.dump(model_obj, f)


if __name__ == "__main__":
    main()
