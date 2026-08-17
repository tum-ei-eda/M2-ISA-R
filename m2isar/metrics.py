# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""M2-ISA-R metrics utils."""

import logging

logger = logging.getLogger("metrics")


def write_metrics(metrics, dest=None):
    import pandas as pd
    assert dest is not None
    metrics_df = pd.DataFrame({key: [val] for key, val in metrics.items()})
    metrics_df.to_csv(dest, index=False)


def init_metrics(add_sets: bool = True, add_cores: bool = True, add_instructions: bool = True):
    metrics = {}
    if add_sets:
        metrics.update({
            "n_sets": 0,
            "skipped_sets": [],
            "failed_sets": [],
            "success_sets": [],
        })
    if add_cores:
        metrics.update({
            "n_cores": 0,
            "skipped_cores": [],
            "failed_cores": [],
            "success_cores": [],
        })
    if add_instructions:
        metrics.update({
            "n_instructions": 0,
            "skipped_instructions": [],
            "failed_instructions": [],
            "success_instructions": [],
        })
    return metrics


def handle_metrics(metrics, dest=None, ignore_failing: bool = False):
    if not ignore_failing:
        failed = {"instructions": metrics["failed_instructions"], "sets": metrics["failed_sets"], "cores": metrics["failed_cores"]}
        for kind, failed_ in failed.items():
            n_failed = len(failed_)
            if n_failed > 0:
                failing_str = ", ".join(failed)
                logger.error("%d %s failed: %s", n_failed, kind, failing_str)
                raise RuntimeError("Abort due to errors")
    if dest:
        write_metrics(metrics, dest=dest)


def add_metrics_args(parser):
    parser.add_argument("--metrics", default=None, help="Output metrics to file")
    parser.add_argument("--ignore-failing", action="store_true", help="Do not crash in case of errors.")
