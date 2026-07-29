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
         calculated during process (if possible), otherwise it is assumed to be the register size. Problems may occur
         when var_1 encounters bit manipulation such as "~" due to bit expansion. To change the nml model with explicit
         slicing e.g var_1 = val_2<3..0> or avoid bit manipulation for dynamic sliced variable. Otherwise, you have to
         manually correct it.

     7. Implementation dependent functionalities such as exception handling should be manully added. Corresponding
         interfaces are provided in ${core_name}ArchSpecificImp.h

     8. ${core_name}GDBCore.h provides the GDBCore class to support gdb flavor debugging feature, modify iy if in need.

 *********************************************************************************************************************************/

#include "${core_name}Arch.h"
#include "${core_name}Funcs.h"

#define ${core_name}_DEBUG_CALL 0
using namespace etiss;
using namespace etiss::instr;

${core_name}Arch::${core_name}Arch(unsigned int coreno) : CPUArch("${core_name}"), coreno_(coreno)
{
    headers_.insert("Arch/${core_name}/${core_name}.h");
}

const std::set<std::string> &${core_name}Arch::getListenerSupportedRegisters()
{
    return listenerSupportedRegisters_;
}

ETISS_CPU *${core_name}Arch::newCPU()
{
    ETISS_CPU *ret = (ETISS_CPU *)new ${core_name}();
    resetCPU(ret, 0);
    return ret;
}

void ${core_name}Arch::resetCPU(ETISS_CPU *cpu, etiss::uint64 *startpointer)
{
    memset(cpu, 0, sizeof(${core_name}));
    ${core_name} *${core_name.lower()}cpu = (${core_name} *)cpu;

    if (startpointer)
        cpu->instructionPointer = *startpointer & ~((etiss::uint64)0x1);
    else
        cpu->instructionPointer = 0x0; //  reference to manual
    cpu->nextPc = cpu->instructionPointer;
    cpu->mode = 1;
    cpu->cpuTime_ps = 0;
    cpu->cpuCycleTime_ps = 31250;

    % for reg in ptr_regs:
    % if isinstance(reg.ty, type_info.ArrayType):
    for (int i = 0; i < ${arch.get_const_or_val(reg.ty.length)}; ++i)
    {
        ${core_name.lower()}cpu->ins_${reg.name}[i] = 0;
        ${core_name.lower()}cpu->${reg.name}[i] = &${core_name.lower()}cpu->ins_${reg.name}[i];
    }
    % else:
    ${core_name.lower()}cpu->ins_${reg.name} = 0;
    ${core_name.lower()}cpu->${reg.name} = &${core_name.lower()}cpu->ins_${reg.name};
    % endif
    % endfor

    % for reg in actual_regs:
    % if not isinstance(reg, (arch.Memory, arch.Alias)):
    % if isinstance(reg, arch.RegisterBank):
    <% assert isinstance(reg.ty, type_info.ArrayType) %>
    for (int i = 0; i < ${arch.get_const_or_val(reg.ty.length)}; ++i)
    {
        ${core_name.lower()}cpu->${reg.name}[i] = 0;
    }
    % else:
    <% assert isinstance(reg.ty, type_info.PrimitiveType) %>
    % if not reg.is_pc:
    ${core_name.lower()}cpu->${reg.name} = 0;
    % endif
    % endif
    % endif
    % endfor

    % for reg, parent in alias_regs.items():
<% ref = "&" %>\
        % if isinstance(reg.ty.ty, type_info.ArrayType): #Alias if of pointertype
    for (int i = 0; i < ${arch.get_const_or_val(reg.ty.length)}; ++i)
    {
        ${core_name.lower()}cpu->${parent.name}[${reg.range.lower} + i]  = ${ref}${core_name.lower()}cpu->${reg.name}[i];
    }
        % else:
            % if isinstance(parent.ty, type_info.ArrayType):
    ${core_name.lower()}cpu->${parent.name}[${reg.range.lower}] = ${ref}${core_name.lower()}cpu->${reg.name};
            % else:
    ${core_name.lower()}cpu->${parent.name} = ${ref}${core_name.lower()}cpu->${reg.name};
            % endif
        % endif
    % endfor

    % for reg in initval_regs:
<% ref = "*" if isinstance(reg.ty, type_info.ArrayType) else "" %>\
    % if isinstance(reg.ty, type_info.ArrayType):
    % for idx, val in reg._initval.items():
<% suffix = "ULL" if val > 0 else "LL" %>\
    ${ref}${core_name.lower()}cpu->${reg.name}[${idx}] = ${val}${suffix};
    % endfor
    % else:
<% val = reg._initval[None] %>\
<% suffix = "ULL" if val > 0 else "LL" %>\
    ${ref}${core_name.lower()}cpu->${reg.name} = ${val}${suffix};
    % endif
    % endfor
    % if procno_memory is not None:
<% ref = "*" if isinstance(reg.ty, type_info.ArrayType) else "" %>\
    ${ref}${core_name.lower()}cpu->${procno_memory.name} = coreno_;
    % endif
}

void ${core_name}Arch::deleteCPU(ETISS_CPU *cpu)
{
    delete (${core_name} *)cpu;
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
const std::set<std::string> &${core_name}Arch::getHeaders() const
{
    return headers_;
}

void ${core_name}Arch::initCodeBlock(etiss::CodeBlock &cb) const
{
    cb.fileglobalCode().insert("#include \"Arch/${core_name}/${core_name}.h\"\n");
    cb.fileglobalCode().insert("#include \"Arch/${core_name}/${core_name}Funcs.h\"\n");
    cb.functionglobalCode().insert("cpu->exception = 0;\n");
    cb.functionglobalCode().insert("cpu->return_pending = 0;\n");
    cb.functionglobalCode().insert("etiss_uint32 mem_ret_code = 0;\n");
}

etiss::plugin::gdb::GDBCore &${core_name}Arch::getGDBCore()
{
    return gdbcore_;
}

// clang-format off
const char * const reg_name[] =
{
    % for n in reg_names:
    "${n}",
    % endfor
};
// clang-format on

% for l in instr_classes:
etiss::instr::InstructionGroup ISA${l}_${core_name}("ISA${l}_${core_name}", ${l});
etiss::instr::InstructionClass ISA${l}_${core_name}Class(1, "ISA${l}_${core_name}", ${l}, ISA${l}_${core_name});
% endfor

etiss::instr::InstructionCollection ${core_name}ISA("${core_name}ISA", ${', '.join([f'ISA{l}_{core_name}Class' for l in instr_classes])});
