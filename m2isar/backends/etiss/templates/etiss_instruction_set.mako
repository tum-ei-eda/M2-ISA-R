## SPDX-License-Identifier: Apache-2.0
##
## This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
##
## Copyright (C) 2022
## Chair of Electrical Design Automation
## Technical University of Munich
\
/**
 * Generated on ${start_time}.
 *
 * This file contains the instruction behavior models of the ${extension_name}
 * instruction set for the ${core_name} core architecture.
 */

#include "${core_name}Arch.h"

#define ETISS_ARCH_STATIC_FN_ONLY
#include "${core_name}Funcs.h"

using namespace etiss;
using namespace etiss::instr;

