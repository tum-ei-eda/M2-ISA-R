# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""M2-ISA-R Logging utils."""

import logging


def add_logging_args(parser):
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])


def handle_logging_args(args):
    # initialize logging
    logging.basicConfig(level=getattr(logging, args.log.upper()))
