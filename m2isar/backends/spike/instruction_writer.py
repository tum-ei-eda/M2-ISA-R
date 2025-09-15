# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2025
# Chair of Electrical Design Automation
# Technical University of Munich

"""Actual text output functions for functions and instructions."""

import os
import logging
import pathlib
from contextlib import ExitStack

from mako.template import Template

from ...metamodel import arch
from .instruction_generator import generate_instructions
from .templates import template_dir

logger = logging.getLogger("instruction_writer")


def write_instructions(set_def: arch.InstructionSet, start_time: str, output_path: pathlib.Path):
    """Generate and write the Spike patches for one instruction."""

    outfiles = {}
    # set_name = set_def.name

    logger.info("writing instructions")

    def safe_open(path, *args, **kwargs):
        """
        Open a file like the built-in open(), but ensure parent directories exist.
        """
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Open the file
        return open(path, *args, **kwargs)

    with ExitStack() as stack:
        # open a default file
        outfiles["encoding.h"] = stack.enter_context(safe_open(output_path / "riscv/encoding.h", "w", encoding="utf-8"))
        outfiles["riscv.mk"] = stack.enter_context(safe_open(output_path / "riscv/riscv.mk", "w", encoding="utf-8"))

        # generate instruction behavior models
        for instr_name, _, ext_name, enc_str, mk_str, behav_str in generate_instructions(set_def):
            logger.debug("writing instruction %s", instr_name)
            outfiles[f"{instr_name}.h"] = stack.enter_context(
                safe_open(output_path / f"riscv/insns/{instr_name}.h", "w", encoding="utf-8")
            )
            outfiles[f"{instr_name}.h"].write(behav_str)
            outfiles["encoding.h"].write(enc_str)
            outfiles["riscv.mk"].write(mk_str)
    print("outfiles", outfiles)
