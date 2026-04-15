# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""validate behavior in M2-ISA-R metamodel."""

import sys
import argparse
import logging
import pathlib

from m2isar.metamodel import patch_model, load_model, dump_model
from m2isar.backends.etiss.warnings import WarningsManager, WarningsInfo, add_warnings_flags, KNOWN_WARNINGS

from . import visitor

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
    add_warnings_flags(parser, KNOWN_WARNINGS, KNOWN_WARNINGS)
    return parser


def run(args):
    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))
    logger = logging.getLogger("validate_behav")
    logger.setLevel(getattr(logging, args.log.upper()))

    # resolve model paths
    top_level = pathlib.Path(args.top_level)

    out_path = (top_level.parent / top_level.stem) if args.output is None else args.output
    print("out_path", out_path)

    model_obj = load_model(top_level)
    warnings_info = args.warnings

    for _, core_def in model_obj.cores.items():
        logger.debug("validating behavior for core %s", core_def.name)
        context = ValidatorContext(warnings_info)
        patch_model(visitor)
        for _, instr_def in core_def.instructions.items():
            logger.debug("validating behavior for instr %s", instr_def.name)
            instr_def.operation.generate(context)
    for _, set_def in model_obj.sets.items():
        logger.debug("validating behavior for set %s", set_def.name)
        context = ValidatorContext(warnings_info)
        patch_model(visitor)
        for _, instr_def in set_def.instructions.items():
            logger.debug("validating behavior for instr %s", instr_def.name)
            instr_def.operation.generate(context)

    dump_model(model_obj, out_path)


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main(sys.argv[1:])
