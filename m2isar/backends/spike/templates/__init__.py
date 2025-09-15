# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""This module only contains mako templates for generating ETISS plugin C++
code, and a variable :data:`template_dir` to keep track of the directory
where the templates are stored.
"""

import pathlib

template_dir = pathlib.Path(__file__).parent.resolve()
