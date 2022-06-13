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
 * This file contains the GDBCore adapter for the ${core_name} core architecture.
 *
 * WARNING: This file contains user-added code, be mindful when overwriting this with
 * generated code!
 */

#ifndef ETISS_${core_name}Arch_${core_name}GDBCORE_H_
#define ETISS_${core_name}Arch_${core_name}GDBCORE_H_

#include "etiss/IntegratedLibrary/gdb/GDBCore.h"
#include <sstream>

/**
	@brief This class is the brige between ${core_name} architecture and gdbserver

	@details Gdbserver integrated in ETISS calls GDBCore to read/write registers via virtualStrruct
				The index in mapRegister() should strictly follow the ${core_name} gdb tool defined register
				order. Because gdbserver will send raw register data sequentially in strict order over
				RSP ->TCP/IP ->RSP protocal

				Check the order with gdb command:
				$(gdb) info all-registers
				which lists all registers supported and its order.

				By default only general purpose register and instruction pointer are supported. Further
				Special Function Register/Control and Status Register could be added manually. Meanwhile
				virtualStruct in ${core_name}Arch.cpp should be modified as well as well

*/
class ${core_name}GDBCore : public etiss::plugin::gdb::GDBCore {
public:
	std::string mapRegister(unsigned index){
		if (index < ${main_reg.range.length}){
			std::stringstream ss;
			ss << "${main_reg.name}" << index;
			return ss.str();
		}
		switch (index){
		case ${main_reg.range.length}:
			return "instructionPointer";
		/**************************************************************************
		*   Further register should be added here to send data over gdbserver	  *
		***************************************************************************/
		}
		return "";
	}

	unsigned mapRegister(std::string name){
		return INVALIDMAPPING;
	}

	unsigned mappedRegisterCount(){
		// Modify according to sent register number
		return ${main_reg.range.length + 1};
	}

	etiss::uint64 getInstructionPointer(ETISS_CPU * cpu){
		return cpu->instructionPointer;
	}

	bool isLittleEndian(){
		// Modify according to ${core_name} manual
		return true;
	}
};

#endif
