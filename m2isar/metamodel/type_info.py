# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026
# Chair of Embedded Computing Systems
# Technical University of Vienna

"""This module contains helper data_type classes for modeling Symbol and data types
for the architectural part of an M2-ISA-R model. The architectural part is
anything but the functional behavior of functions and instructions.
"""

from enum import Enum, auto


class PrimitiveKind(Enum):
    NONE = auto()
    U = auto()
    S = auto()
    F = auto()
    D = auto()
    Q = auto()
    BOOL = auto()
    STR = auto()

