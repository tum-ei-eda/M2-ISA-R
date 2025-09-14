# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Main entrypoint for the spike_writer program."""

import argparse
import logging
import pathlib
import pickle
import shutil
import time

from ...metamodel import M2_METAMODEL_VERSION, M2Model
from ...metamodel.utils.expr_preprocessor import process_attributes, process_functions, process_instructions
from .instruction_writer import write_instructions


def setup():
    """Setup a M2-ISA-R metamodel consumer. Create an argument parser, unpickle the model
    and generate output file structure.
    """

    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("top_level", help="A .m2isarmodel file containing the models to generate.")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    args = parser.parse_args()

    # configure logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))
    logger = logging.getLogger("spike_writer")

    # resolve model paths
    top_level = pathlib.Path(args.top_level)
    abs_top_level = top_level.resolve()
    search_path = abs_top_level.parent.parent
    model_fname = abs_top_level

    if abs_top_level.suffix == ".core_desc":
        logger.warning(".core_desc file passed as input. This is deprecated behavior, please change your scripts!")
        search_path = abs_top_level.parent
        model_path = search_path.joinpath("gen_model")

        if not model_path.exists():
            raise FileNotFoundError("Models not generated!")
        model_fname = model_path / (abs_top_level.stem + ".m2isarmodel")

    # create top level output directory
    spec_name = abs_top_level.stem
    output_base_path = search_path.joinpath("gen_output")
    output_base_path.mkdir(exist_ok=True)

    logger.info("loading models")

    with open(model_fname, "rb") as f:
        model_obj: M2Model = pickle.load(f)

    if model_obj.model_version != M2_METAMODEL_VERSION:
        logger.warning("Loaded model version mismatch")

    start_time = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.localtime())

    return (model_obj.sets, logger, output_base_path, spec_name, start_time, args)


def main():
    """spike_writer main entrypoint function."""

    # setup spike writer
    sets, logger, output_base_path, spec_name, start_time, args = setup()

    # preprocess all sets
    for set_name, set_def in sets.items():
        logger.info("preprocessing set %s", set_name)
        process_functions(set_def)
        process_instructions(set_def)
        process_attributes(set_def)

    # generate each core in the model
    for set_name, set_def in sets.items():
        logger.info("processing set %s", set_name)

        # create output files path
        output_path = output_base_path / spec_name / set_name
        try:
            output_path.mkdir(parents=True)
        except FileExistsError:
            shutil.rmtree(output_path)
            output_path.mkdir(parents=True)

        # generate and write files
        # TODO: support functions
        # write_functions(set_def, start_time, output_path, args.static_scalars, args.coverage)
        write_instructions(set_def, start_time, output_path)


if __name__ == "__main__":
    main()
