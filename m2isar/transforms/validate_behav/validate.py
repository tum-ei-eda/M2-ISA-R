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

from ... import M2Error
from ...diagnostics import M2ValidationError
from ...metamodel import load_model, dump_model
from ...warnings import WarningsManager, WarningsInfo, add_warnings_flags, KNOWN_WARNINGS, DEFAULT_WARNINGS
from .visitor import ValidateBehavVisitor


class ValidatorContext(WarningsManager):
    """Track miscellaneous information throughout the validation process."""
    def __init__(self, warnings_info: WarningsInfo = None, partial=False, function=None, *, source_validated=False):
        super().__init__(warnings_info)
        self.partial = partial
        self.function = function
        self.source_validated = source_validated


def get_parser():
    # read command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel file.")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    add_warnings_flags(parser, KNOWN_WARNINGS, DEFAULT_WARNINGS)
    return parser


def validate_behav(model_obj, warnings_info, *, source_validated=False):
    logger = logging.getLogger("validate_behav")
    errors = []

    def validate_body(visitor, operation, context, function=None):
        try:
            visitor.generate(operation, context)
        except M2ValidationError as error:
            errors.append(error)
        if function is not None:
            terminated = getattr(function, '_coredsl_return_terminated', None)
            if terminated is None:
                terminated = visitor.is_return_terminated(operation)
            if not function.ty.kind.is_void and not terminated:
                errors.append(M2ValidationError('Not all execution paths return a value', 'MissingReturnStatement',
                                                operation.line_info))

    for _, core_def in model_obj.cores.items():
        logger.debug("validating behavior for core %s", core_def.name)
        context = ValidatorContext(warnings_info, source_validated=source_validated)
        visitor = ValidateBehavVisitor()
        for always_block in core_def.always_blocks.values():
            logger.debug("validating behavior for always block %s", always_block.name)
            validate_body(visitor, always_block.operation, context)
        for _, instr_def in core_def.instructions.items():
            logger.debug("validating behavior for instr %s", instr_def.name)
            validate_body(visitor, instr_def.operation, context)
    for _, set_def in model_obj.sets.items():
        logger.debug("validating behavior for set %s", set_def.name)
        context = ValidatorContext(warnings_info, partial=True, source_validated=source_validated)
        visitor = ValidateBehavVisitor()
        for always_block in set_def.always_blocks.values():
            logger.debug("validating behavior for always block %s", always_block.name)
            validate_body(visitor, always_block.operation, context)
        for _, instr_def in set_def.instructions.items():
            logger.debug("validating behavior for instr %s", instr_def.name)
            validate_body(visitor, instr_def.operation, context)
    # Functions participate in the same validation policy as instruction bodies.
    for definitions in (model_obj.cores, model_obj.sets):
        for definition in definitions.values():
            for function in definition.functions.values():
                if function.extern:
                    continue
                logger.debug("validating behavior for function %s", function.name)
                visitor = ValidateBehavVisitor()
                validate_body(visitor, function.operation,
                              ValidatorContext(warnings_info, partial=definitions is model_obj.sets, function=function,
                                               source_validated=source_validated),
                              function)
    if errors:
        errors[0].related_diagnostics.extend(errors[1:])
        raise errors[0]


def run(args):
    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))

    # resolve model paths
    top_level = pathlib.Path(args.top_level)

    model_obj = load_model(top_level)
    warnings_info = args.warnings
    validate_behav(model_obj, warnings_info)


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    try:
        run(args)
    except M2Error as exc:
        logging.getLogger("validate_behav").error("Validation failed: %s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
