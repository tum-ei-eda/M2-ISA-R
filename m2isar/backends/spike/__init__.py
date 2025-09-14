# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""This is the Spike patch generation backend of M2-ISA-R.

The main entry point for the patch writer is contained within
:mod:`m2isar.backends.spike.writer`.
"""

from collections import defaultdict
from enum import Enum, auto
