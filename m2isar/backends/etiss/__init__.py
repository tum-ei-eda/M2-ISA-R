# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""This is the ETISS architecture generation backend of M2-ISA-R. It is used
for automatic generation of architecture plugins for the ETISS instruction
set simulator.
"""

from enum import Enum, auto

class BlockEndType(Enum):
	"""Denotes the conditions on which to enforce a translation block end in ETISS."""

	NONE = auto()
	UNCOND = auto()
	ALL = auto()