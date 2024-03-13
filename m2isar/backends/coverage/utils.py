# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2024
# Chair of Electrical Design Automation
# Technical University of Munich

from collections import defaultdict

class IdMatcherContext:
	def __init__(self):
		self.arch_name = None
		self.id_to_obj_map = defaultdict(dict)
