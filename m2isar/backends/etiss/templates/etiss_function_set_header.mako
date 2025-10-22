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
 * This file contains the function prototypes for the ${core_name} core architecture.
 */

#ifndef __${core_name.upper()}_FUNCS_H
#define __${core_name.upper()}_FUNCS_H

#ifdef __cplusplus
extern "C"
{
#endif

#include "${core_name}.h"
#include "etiss/jit/CPU.h"
#include "etiss/jit/System.h"
#include "etiss/jit/ReturnCode.h"
% if enable_coverage:
#include "etiss/jit/Coverage.h"
% endif
