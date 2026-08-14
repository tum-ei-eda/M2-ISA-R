# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Clean M2-ISA-R/Seal5 metamodel to .core_desc file."""

import copy
import argparse
import logging
import pathlib


from ...metamodel import load_model
from .utils import CoreDSL2Writer
from .visitor import CDSLWriterVisitor

logger = logging.getLogger("coredsl2_writer")



def main():
    """Main app entrypoint."""

    # read command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel or .seal5model file.")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--reduced", action="store_true", help="Generate pattern-gen compatible syntax")
    parser.add_argument("--splitted", action="store_true", help="Split per set and instruction")
    parser.add_argument("--ext", type=str, default="core_desc", help="Default file extension (if using --splitted)")
    # parser.add_argument("--metrics", default=None, help="Output metrics to file")
    # parser.add_argument("--ignore-failing", action="store_true", help="Do not crash in case of errors.")
    args = parser.parse_args()

    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))

    # resolve model paths
    top_level = pathlib.Path(args.top_level)
    if args.output is None:
        out_path = f"{top_level}.{args.ext}"
    else:
        out_path = pathlib.Path(args.output)

    logger.info("loading models")

    # load models
    model_obj = load_model(top_level)

    # TODO: handle cores as well

    # metrics = {
    #     "n_sets": 0,
    #     "n_instructions": 0,
    #     "n_skipped": 0,
    #     "n_failed": 0,
    #     "n_success": 0,
    #     "skipped_instructions": [],
    #     "failed_instructions": [],
    #     "success_instructions": [],
    #     "skipped_sets": [],
    #     "failed_sets": [],
    #     "success_sets": [],
    # }

    if args.splitted:
        assert out_path.is_dir(), "Expecting output directory when using --splitted"
        for set_name, set_def in model_obj.sets.items():
            # metrics["n_sets"] += 1
            for instr_def in set_def.instructions.values():
                visitor = CDSLWriterVisitor()
                writer = CoreDSL2Writer(visitor, reduced=args.reduced)
                logger.debug("writing instr %s/%s", set_def.name, instr_def.name)
                set_def_ = copy.deepcopy(set_def)
                set_def_.instructions = {
                    key: instr_def
                    for key, instr_def_ in set_def.instructions.items()
                    if instr_def.name == instr_def_.name
                }
                try:
                    writer.write_set(set_def_)
                    content = writer.text
                    out_path_ = out_path / set_name / f"{instr_def.name}.{args.ext}"
                    out_path_.parent.mkdir(exist_ok=True)
                    with open(out_path_, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception as ex:
                    logger.exception(ex)
    else:
        visitor = CDSLWriterVisitor()
        writer = CoreDSL2Writer(visitor, reduced=args.reduced)
        num_cores = len(model_obj.cores)
        num_sets = len(model_obj.sets)
        if num_sets > 0:
            assert num_cores == 0
            for set_name, set_def in model_obj.sets.items():
                logger.debug("writing set %s", set_def.name)
                try:
                    writer.write_set(set_def)
                except Exception as ex:
                    logger.exception(ex)
        if num_cores > 0:
            assert num_sets == 0
            for core_name, core_def in model_obj.cores.items():
                logger.debug("writing core %s", core_def.name)
                try:
                    writer.write_core(core_def)
                except Exception as ex:
                    logger.exception(ex)
        content = writer.text
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)


if __name__ == "__main__":
    main()
