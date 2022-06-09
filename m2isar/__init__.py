# SPDX-License-Identifier: Apache-2.0

# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (c) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

class M2Error(Exception):
	pass

class M2ValueError(ValueError, M2Error):
	pass

class M2NameError(NameError, M2Error):
	pass

class M2DuplicateError(M2NameError):
	pass

class M2TypeError(TypeError, M2Error):
	pass

class M2SyntaxError(SyntaxError, M2Error):
	pass