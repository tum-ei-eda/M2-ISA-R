# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Clean M2-ISA-R/Seal5 metamodel to .core_desc file."""

import logging

# from ...metrics import init_metrics

logger = logging.getLogger("iter_utils")


def process_sets(model_obj, handler, description: str = None, metrics=None):
    prefix = description if description is not None else "Processing"
    for set_name, set_def in model_obj.sets.items():
        logger.debug("%s set %s/%s", prefix, set_def.name)
        if metrics:
            metrics["n_sets"] += 1
        try:
            handler(set_def)
            if metrics:
                metrics["success_sets"].append(set_name)
        except Exception as ex:
            logger.exception(ex)
            if metrics:
                metrics["failed_sets"].append(set_name)
    return metrics


def process_cores(model_obj, handler, description: str = None, metrics=None):
    prefix = description if description is not None else "Processing"
    for core_name, core_def in model_obj.cores.items():
        logger.debug("%s core %s/%s", prefix, core_def.name)
        if metrics:
            metrics["n_cores"] += 1
        try:
            handler(core_def)
            if metrics:
                metrics["success_cores"].append(core_name)
        except Exception as ex:
            logger.exception(ex)
            if metrics:
                metrics["failed_cores"].append(core_name)
    return metrics


def process_sets_instructions(model_obj, handler, description: str = None, metrics=None):
    prefix = description if description is not None else "Processing"
    for set_name, set_def in model_obj.sets.items():
        logger.debug("%s set %s/%s", prefix, set_def.name)
        if metrics:
            metrics["n_sets"] += 1
        for instr_def in set_def.instructions.values():
            if metrics:
                metrics["n_instructions"] += 1
            logger.debug("%s instr %s/%s", prefix, set_def.name, instr_def.name)
            try:
                handler(set_def, instr_def)
                if metrics:
                    metrics["success_instructions"].append(instr_def.name)
            except Exception as ex:
                logger.exception(ex)
                if metrics:
                    metrics["failed_instructions"].append(instr_def.name)
    return metrics


def process_cores_instructions(model_obj, handler, description: str = None, metrics=None):
    prefix = description if description is not None else "Processing"
    for core_name, core_def in model_obj.cores.items():
        logger.debug("%s core %s/%s", prefix, core_def.name)
        if metrics:
            metrics["n_cores"] += 1
        for instr_def in core_def.instructions.values():
            if metrics:
                metrics["n_instructions"] += 1
            prefix = description if description is not None else "Processing"
            logger.debug("%s instr %s/%s", prefix, core_def.name, instr_def.name)
            try:
                handler(core_def, instr_def)
                if metrics:
                    metrics["success_instructions"].append(instr_def.name)
            except Exception as ex:
                logger.exception(ex)
                if metrics:
                    metrics["failed_instructions"].append(instr_def.name)
    return metrics
