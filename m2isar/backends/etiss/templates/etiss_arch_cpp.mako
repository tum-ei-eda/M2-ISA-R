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
 * This file contains the architecture class for the ${core_name} core architecture.
 */

/*********************************************************************************************************************************

* Modification guidelines:

	 1. The initial value of SP register should be initialized by ctr0.S/board.S. If not, it could be initialized
		 through utility class etiss::VirtualStruct::Field.

	 2. Debug mode print out all assignment results. GDB in 8 is prefered.

	 3. Manually copy the content in bracket ["return ETISS_RETURNCODE_CPUFINISHED; \n"] to terminating instruction,
		 otherwise the emulation can not be ended.

	 4. If subset of encoding error occurs, it means the format of the encoding in the input model was not appropriate

	 5. If the PC register points to wrong address, please notice that some assembly may cause branch operation
		 implicitly such as "MOV Rd Rn" in ARMv6-M

	 6. If a variable is the result of dynamic slicing such as, var_1 = var_2<Hshift-1..Lshift-2>, the size would be
		 calculated during process (if possible), otherwise it is assumed to be the register size. Problems may occur when
		 var_1 encounters bit manipulation such as "~" due to bit expansion. To change the nml model with explicit slicing
		 e.g var_1 = val_2<3..0> or avoid bit manipulation for dynamic sliced variable. Otherwise, you have to manually
		 correct it.

	 7. Implementation dependent functionalities such as exception handling should be manully added. Corresponding interfaces
		 are provided in ${core_name}ArchSpecificImp.h

	 8. ${core_name}GDBCore.h provides the GDBCore class to support gdb flavor debugging feature, modify iy if in need.

 *********************************************************************************************************************************/

#include "${core_name}Arch.h"

#define ETISS_ARCH_STATIC_FN_ONLY
#include "${core_name}Funcs.h"

#define ${core_name}_DEBUG_CALL 0
using namespace etiss ;
using namespace etiss::instr ;

${core_name}Arch::${core_name}Arch():CPUArch("${core_name}")
{
	headers_.insert("Arch/${core_name}/${core_name}.h");
}

const std::set<std::string> & ${core_name}Arch::getListenerSupportedRegisters()
{
	return listenerSupportedRegisters_;
}

ETISS_CPU * ${core_name}Arch::newCPU()
{
	ETISS_CPU * ret = (ETISS_CPU *) new ${core_name}() ;
	resetCPU (ret, 0);
	return ret;
}

void ${core_name}Arch::resetCPU(ETISS_CPU * cpu,etiss::uint64 * startpointer)
{
	memset (cpu, 0, sizeof(${core_name}));
	${core_name} * ${core_name.lower()}cpu = (${core_name} *) cpu;

	if (startpointer) cpu->instructionPointer = *startpointer & ~((etiss::uint64)0x1);
	else cpu->instructionPointer = 0x0;   //  reference to manual
	cpu->mode = 1;
	cpu->cpuTime_ps = 0;
	cpu->cpuCycleTime_ps = 31250;


	% for reg in ptr_regs:
	% if reg.range.length > 1:
	for (int i = 0; i < ${reg.data_range.length}; ++i) {
		${core_name.lower()}cpu->ins_${reg.name}[i] = 0;
		${core_name.lower()}cpu->${reg.name}[i] = &${core_name.lower()}cpu->ins_${reg.name}[i];
	}
	% else:
	${core_name.lower()}cpu->ins_${reg.name} = 0;
	${core_name.lower()}cpu->${reg.name} = &${core_name.lower()}cpu->ins_${reg.name};
	% endif
	% endfor

	% for reg in actual_regs:
	% if not reg.is_pc:
	% if reg.range.length > 1:
	for (int i = 0; i < ${reg.data_range.length}; ++i) {
		${core_name.lower()}cpu->${reg.name}[i] = 0;
	}
	% else:
	${core_name.lower()}cpu->${reg.name} = 0;
	% endif
	% endif
	% endfor

	% for reg, parent in alias_regs.items():
<% ref = "" if len(reg.children) > 0 else "&" %> \
	% if reg.range.length > 1:
	for (int i = 0; i < ${reg.range.length}; ++i) {
		${core_name.lower()}cpu->${parent.name}[${reg.range.lower} + i] = ${ref}${core_name.lower()}cpu->${reg.name}[i];
	}
	% else:
	% if reg.is_pc:
	${core_name.lower()}cpu->${parent.name}[${reg.range.lower}] = (etiss_uint${reg.size}*)&(cpu->instructionPointer);
	% else:
	% if parent.range.length > 1:
	${core_name.lower()}cpu->${parent.name}[${reg.range.lower}] = ${ref}${core_name.lower()}cpu->${reg.name};
	% else:
	${core_name.lower()}cpu->${parent.name} = ${ref}${core_name.lower()}cpu->${reg.name};
	% endif
	% endif
	% endif
	% endfor

	% for reg in initval_regs:
<% ref = "*" if len(reg.children) > 0 else "" %> \
	% if reg.range.length > 1:
	% for idx, val in reg._initval.items():
	${ref}${core_name.lower()}cpu->${reg.name}[${idx}] = ${val};
	% endfor
	% else:
	${ref}${core_name.lower()}cpu->${reg.name} = ${reg._initval[None]};
	% endif
	% endfor
}

void ${core_name}Arch::deleteCPU(ETISS_CPU *cpu)
{
	delete (${core_name} *) cpu ;
}

/**
	@return 8 (jump instruction + instruction of delay slot)
*/
unsigned ${core_name}Arch::getMaximumInstructionSizeInBytes()
{
	return 8;
}

/**
	@return 2
*/
unsigned ${core_name}Arch::getInstructionSizeInBytes()
{
	return 2;
}

/**
	@brief required headers (${core_name}.h)
*/
const std::set<std::string> & ${core_name}Arch::getHeaders() const
{
	return headers_ ;
}

void ${core_name}Arch::initCodeBlock(etiss::CodeBlock & cb) const
{
	cb.fileglobalCode().insert("#include \"Arch/${core_name}/${core_name}.h\"\n");
	cb.fileglobalCode().insert("#include \"Arch/${core_name}/${core_name}Funcs.h\"\n");
	cb.functionglobalCode().insert("((${core_name}*)cpu)->exception = 0;\n");
	cb.functionglobalCode().insert("((${core_name}*)cpu)->exception_pending = 0;\n");
}

etiss::plugin::gdb::GDBCore & ${core_name}Arch::getGDBCore()
{
	return gdbcore_;
}

const char * const reg_name[] =
{
	% for n in reg_names:
	"${n}",
	% endfor
};

% for l in instr_classes:
etiss::instr::InstructionGroup ISA${l}_${core_name}("ISA${l}_${core_name}", ${l});
etiss::instr::InstructionClass ISA${l}_${core_name}Class(1, "ISA${l}_${core_name}", ${l}, ISA${l}_${core_name});
% endfor

etiss::instr::InstructionCollection ${core_name}ISA("${core_name}ISA", ${', '.join([f'ISA{l}_{core_name}Class' for l in instr_classes])});