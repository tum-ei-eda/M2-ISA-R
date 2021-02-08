/**
 * Generated on ${start_time}.
 *
 * This file contains the function macros of the ${extension_name}
 * instruction set for the ${core_name} core architecture.
 */

#ifndef __${core_name.upper()}_${extension_name.upper()}_FUNCS_H
#define __${core_name.upper()}_${extension_name.upper()}_FUNCS_H

#ifndef ETISS_ARCH_STATIC_FN_ONLY
#include "Arch/${core_name}/${core_name}.h"
#include "etiss/jit/CPU.h"
#include "etiss/jit/System.h"
#include "etiss/jit/ReturnCode.h"
#endif

${functions_code}
#endif