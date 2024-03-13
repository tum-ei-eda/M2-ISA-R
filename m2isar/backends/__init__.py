# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2024
# Chair of Electrical Design Automation
# Technical University of Munich

"""This module contains various consumers of M2-ISA-R models. Currently provided are:

* A generator for ETISS architecture plugins. This backend generates C++ plugin code for the ETISS
  instruction set simulator, allowing easy and fast additions of ISAs to ETISS.
* A graphical inspection tool for M2-ISA-R models. The tool allows exploring the contents of an
  M2-ISA-R model in an easy-to-use tree browser.
"""
