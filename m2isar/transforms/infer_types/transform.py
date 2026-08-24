# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Type inference for M2-ISA-R metamodel."""

import sys
import argparse
import logging
import pathlib

from m2isar.metamodel import load_model, dump_model
from m2isar.metamodel.utils.expr_simplifier import ExprSimplifierVisitor
from ...warnings import WarningsManager, WarningsInfo, add_warnings_flags, KNOWN_WARNINGS, DEFAULT_ERRORS
from .visitor import InferTypesMutator


class ValidatorContext(WarningsManager):
    """Track miscellaneous information throughout the validation process."""
    def __init__(self, warnings_info: WarningsInfo = None):
        super().__init__(warnings_info)


def get_parser():
    # read command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel file.")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    parser.add_argument("--output", "-o", type=str, default=None)
    add_warnings_flags(parser, KNOWN_WARNINGS, KNOWN_WARNINGS, DEFAULT_ERRORS)
    return parser


def infer_types(model_obj, warnings_info=None, skip_simplify: bool = False):
    logger = logging.getLogger("infer_types")
    for _, core_def in model_obj.cores.items():
        logger.debug("inferring types for core %s", core_def.name)
        context = ValidatorContext(warnings_info)
        simplifier = ExprSimplifierVisitor()
        mutator = InferTypesMutator()
        for always_block in core_def.always_blocks.values():
            logger.debug("inferring types for always block %s", always_block.name)
            mutator.generate(always_block.operation, context)
            if not skip_simplify:
                simplifier.generate(always_block.operation, context)
                mutator.generate(always_block.operation, context)
        for _, instr_def in core_def.instructions.items():
            logger.debug("inferring types for instr %s", instr_def.name)
            mutator.generate(instr_def.operation, context)
            if not skip_simplify:
                simplifier.generate(instr_def.operation, context)
                mutator.generate(instr_def.operation, context)

        for _, func_def in core_def.functions.items():
            logger.debug("inferring types for functions %s", func_def.name)
            mutator.generate(func_def.operation, context)
            if not skip_simplify:
                simplifier.generate(instr_def.operation, context)
                mutator.generate(instr_def.operation, context)

    for _, set_def in model_obj.sets.items():
        logger.debug("inferring types for set %s", set_def.name)
        context = ValidatorContext(warnings_info)
        simplifier = ExprSimplifierVisitor()
        mutator = InferTypesMutator()
        for always_block in set_def.always_blocks.values():
            logger.debug("inferring types for always block %s", always_block.name)
            mutator.generate(always_block.operation, context)
            if not skip_simplify:
                simplifier.generate(always_block.operation, context)
                mutator.generate(always_block.operation, context)
        for _, instr_def in set_def.instructions.items():
            logger.debug("inferring types for instr %s", instr_def.name)
            mutator.generate(instr_def.operation, context)
            if not skip_simplify:
                simplifier.generate(instr_def.operation, context)
                mutator.generate(instr_def.operation, context)
    return model_obj


def run(args):
    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))

    # resolve model paths
    top_level = pathlib.Path(args.top_level)

    out_path = (top_level.parent / top_level.stem) if args.output is None else args.output
    print("out_path", out_path)

    model_obj = load_model(top_level)
    warnings_info = args.warnings
    model_obj = infer_types(model_obj, warnings_info=warnings_info)

    dump_model(model_obj, out_path)


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main(sys.argv[1:])
