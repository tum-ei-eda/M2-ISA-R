# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

default_prefix = '((${ARCH_NAME}*)cpu)->'
prefixes = {
	'PC': 'cpu->',
	#'X': '*((${ARCH_NAME}*)cpu)->',
	#'R': '*((${ARCH_NAME}*)cpu)->'
}

rename_static = {
	'PC': 'ic.current_address_'
}

rename_dynamic = {
	'PC': 'cpu->instructionPointer'
}

exception_mapping = {
	(0, 0): 'ETISS_RETURNCODE_IBUS_READ_ERROR',
	(0, 2): 'ETISS_RETURNCODE_ILLEGALINSTRUCTION',
	(0, 11): 'ETISS_RETURNCODE_SYSCALL',
	(0, 3): 'ETISS_RETURNCODE_CPUFINISHED'
}