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
 * This file contains the registers for the ${core_name} core architecture.
 */

#ifndef ETISS_${core_name}Arch_${core_name}_H_
#define ETISS_${core_name}Arch_${core_name}_H_
#include <stdio.h>
#include "etiss/jit/CPU.h"

#ifdef __cplusplus
extern "C" {
#endif
#pragma pack(push, 1)
struct ${core_name} {
	ETISS_CPU cpu; // original cpu struct must be defined as the first field of the new structure. this allows to cast X * to ETISS_CPU * and vice vers
	etiss_uint32 exception;
	etiss_uint32 exception_pending;
	% for reg in regs:
	${reg};
	% endfor
};

#pragma pack(pop) // undo changes
typedef struct ${core_name} ${core_name}; // convenient use of X instead of struct X in generated C code
#ifdef __cplusplus
} // extern "C"
#endif
#endif
