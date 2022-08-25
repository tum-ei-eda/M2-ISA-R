# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""This module contains utility functions for working with M2-ISA-R model hierarchies."""

from dataclasses import dataclass
from enum import IntFlag, auto


class StaticType(IntFlag):
	"""Describes the staticness of a Scalar or Function"""

	NONE = 0
	READ = auto()
	WRITE = auto()
	RW = READ | WRITE

@dataclass
class ScalarStaticnessContext:
	"""A datakeeping class for the scalar staticness transformations."""

	context_is_static: StaticType = StaticType.RW
