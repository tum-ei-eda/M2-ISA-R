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
 * This file contains the library interface for the ${core_name} core architecture.
 */

// define a name for this library. this will be used to avoid name clashes with other libraries. in this example the library is named "X".
// IMPORTANT this name MUST match the library name: e.g. X -> libX.so

#define ETISS_LIBNAME ${core_name}
#include "etiss/helper/CPUArchLibrary.h" // defines the following functions
#include "${core_name}Arch.h"
extern "C" {

	ETISS_LIBRARYIF_VERSION_FUNC_IMPL

	ETISS_PLUGIN_EXPORT unsigned ${core_name}_countCPUArch()
	{
//TODO
		return 1; // number of cpu architectures provided
	}
	ETISS_PLUGIN_EXPORT const char * ${core_name}_nameCPUArch(unsigned index)
	{
//TODO
		switch (index)
		{
		case 0:
			return "${core_name}";
		default:
			return "";
		}
	}
	ETISS_PLUGIN_EXPORT etiss::CPUArch* ${core_name}_createCPUArch(unsigned index,std::map<std::string,std::string> options)
	{
//TODO
		switch (index)
		{
		case 0:
			return new ${core_name}Arch();
		default:
			return 0;
		}
	}
	ETISS_PLUGIN_EXPORT void ${core_name}_deleteCPUArch(etiss::CPUArch* arch)
	{
		delete arch;
	}
}
