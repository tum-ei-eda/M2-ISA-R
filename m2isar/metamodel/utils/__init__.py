# SPDX-License-Identifier: Apache-2.0

# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (c) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

from enum import IntFlag, auto

class StaticType(IntFlag):
	NONE = 0
	READ = auto()
	WRITE = auto()
	RW = READ | WRITE