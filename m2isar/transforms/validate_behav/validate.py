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

from ...metamodel import load_model, dump_model
from ...warnings import WarningsManager, WarningsInfo, add_warnings_flags, KNOWN_WARNINGS, DEFAULT_ERRORS
from .visitor import ValidateBehavVisitor


class ValidatorContext(WarningsManager):
    """Track miscellaneous information throughout the validation process."""
    def __init__(self, warnings_info: WarningsInfo = None):
        super().__init__(warnings_info)


def get_parser():
    # read command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel file.")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    add_warnings_flags(parser, KNOWN_WARNINGS, KNOWN_WARNINGS, DEFAULT_ERRORS)
    return parser


def validate_behav(model_obj, warnings_info):
    logger = logging.getLogger("validate_behav")
    for _, core_def in model_obj.cores.items():
        logger.debug("validating behavior for core %s", core_def.name)
        context = ValidatorContext(warnings_info)
        visitor = ValidateBehavVisitor()
        for _, instr_def in core_def.instructions.items():
            logger.debug("validating behavior for instr %s", instr_def.name)
            visitor.generate(instr_def.operation, context)
    for _, set_def in model_obj.sets.items():
        logger.debug("validating behavior for set %s", set_def.name)
        context = ValidatorContext(warnings_info)
        visitor = ValidateBehavVisitor()
        for _, instr_def in set_def.instructions.items():
            logger.debug("validating behavior for instr %s", instr_def.name)
            visitor.generate(instr_def.operation, context)
    # return model_obj


def run(args):
    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))

    # resolve model paths
    top_level = pathlib.Path(args.top_level)

    model_obj = load_model(top_level)
    warnings_info = args.warnings
    alidate_behav(model_obj, warnings_info)


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main(sys.argv[1:])
