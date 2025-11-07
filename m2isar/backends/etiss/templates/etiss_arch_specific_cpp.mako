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
 * This file contains the architecture specific implementation for the ${core_name}
 * core architecture.
 *
 * WARNING: This file contains user-added code, be mindful when overwriting this with
 * generated code!
 */

#include <vector>

#include "${core_name}Arch.h"
#include "${core_name}ArchSpecificImp.h"
#include "${core_name}Funcs.h"

/**
    @brief This function will be called automatically in order to handling exceptions such as interrupt, system call,
    illegal instructions

    @details Exception handling mechanism is implementation dependent for each cpu variant. Please add it to the
    following block if exception handling is demanded. Pseudo example:
    ```
    switch(cause){
            case etiss::RETURNCODE::INTERRUPT:
                .
                .
                .
            break;
    ```

*/
etiss::int32 ${core_name}Arch::handleException(etiss::int32 cause, ETISS_CPU *cpu)
{
    % if error_fn is not None:
    ${error_fn.name}(cpu, nullptr, nullptr, cause);
    cpu->instructionPointer = cpu->nextPc;
    % endif \

    return 0;
}

/**
    @brief This function is called during CPUArch initialization

    @details Function pointer length_updater_ has to be replaced if multiple length instruction execution is supported.
    This function enables dynamic instruction length update in order to guarantee correct binary translation.
    Pseudo example:
    ```
    vis->length_updater_ = [](VariableInstructionSet & ,InstructionContext &ic, BitArray &ba)
    {
        switch(ba.byteCount()){
            case 4:
                if ( INSTRUCTION_LENTH_NOT_EQUAL(4)){
                    updateInstrLength(ic, ba);
                    ic.is_not_default_width_ = true;
                        .
                        .
                        .
                }
                break;
        }
    };
    ```

*/
void ${core_name}Arch::initInstrSet(etiss::instr::ModedInstructionSet &mis) const
{
    if (false) {
        // Pre-compilation of instruction set to view instruction tree. Enable by setting 'true' above.

        etiss::instr::ModedInstructionSet iset("${core_name}ISA");
        bool ok = true;
        ${core_name}ISA.addTo(iset, ok);

        iset.compile();

        std::cout << iset.print() << std::endl;
    }

    bool ok = true;
    ${core_name}ISA.addTo(mis, ok);
    if (!ok)
        etiss::log(etiss::FATALERROR, "Failed to add instructions for ${core_name}ISA");

    etiss::instr::VariableInstructionSet *vis = mis.get(1);

    using namespace etiss;
    using namespace etiss::instr;

    % for bitsize, callback in error_callbacks.items():
    vis->get(${bitsize})->getInvalid().addCallback(
${callback},
    0
    );

    %endfor

    /**************************************************************************
     *             vis->length_updater_ should be replaced here               *
     **************************************************************************/
}

/**
    @brief This function is called whenever a data is read from memory

    @details Target architecture may have inconsistent endianess. Data read from memory is buffered, and this function
                is called to alter sequence of buffered data so that the inconsistent endianess is compensated.
                Example for ARMv6M:
                void *ptr = ba.internalBuffer();
                if (ba.byteCount() == 2)
                {
                    *((uint32_t*)ptr) = ((uint16_t)(*((uint8_t*)ptr))) | ((uint16_t)(*(((uint8_t*)ptr)+1)) << 8);
                }
                else if (ba.byteCount() == 4)
                {
                    *((uint32_t*)ptr) = ((((uint32_t)(*((uint8_t*)ptr))) | ((uint32_t)(*(((uint8_t*)ptr)+1)) << 8)) << 16) | ((uint32_t)(*(((uint8_t*)ptr)+2)) ) | ((uint32_t)(*(((uint8_t*)ptr)+3)) << 8);
                }
                else
                {
                    etiss::log(etiss::FATALERROR,"Endianess cannot be handled",ba.byteCount());
                }

    @attention Default endianess: little-endian

*/
void ${core_name}Arch::compensateEndianess(ETISS_CPU *cpu, etiss::instr::BitArray &ba) const
{
    /**************************************************************************
     *                       Endianess compensation                           *
     **************************************************************************/
}

std::shared_ptr<etiss::VirtualStruct> ${core_name}Arch::getVirtualStruct(ETISS_CPU *cpu)
{
    auto ret = etiss::VirtualStruct::allocate(cpu, [](etiss::VirtualStruct::Field *f) { delete f; });

    for (uint32_t i = 0; i < ${main_reg.range.length}; ++i)
    {
        ret->addField(new RegField_${core_name}(*ret, i));
    }

    ret->addField(new pcField_${core_name}(*ret));
    return ret;
}

/**
    @brief If interrupt handling is expected, vector table could be provided to support interrupt triggering

    @details Interrupt vector table is used to inform the core whenever an edge/level triggered interrupt
                incoming. The content of interrupt vector could be a special register or standalone interrupt
                lines.
*/
etiss::InterruptVector *${core_name}Arch::createInterruptVector(ETISS_CPU *cpu)
{
    if (cpu == 0)
        return 0;

    % if irq_en_reg is not None and irq_pending_reg is not None:
<% en_ref = "" if len(irq_en_reg.children) > 0 else "&" %>\
<% pending_ref = "" if len(irq_pending_reg.children) > 0 else "&" %>\
    std::vector<etiss::uint${irq_en_reg.size} *> vec;
    std::vector<etiss::uint${irq_en_reg.size} *> mask;

    vec.push_back(${en_ref}((${core_name} *)cpu)->${irq_pending_reg.name});
    mask.push_back(${pending_ref}((${core_name} *)cpu)->${irq_en_reg.name});

    return new etiss::MappedInterruptVector<etiss::uint${irq_en_reg.size}>(vec, mask);
    % else:
    std::vector<etiss::uint${main_reg.size} *> vec;
    std::vector<etiss::uint${main_reg.size} *> mask;

    return new etiss::MappedInterruptVector<etiss::uint${main_reg.size}>(vec, mask);
    % endif
}

void ${core_name}Arch::deleteInterruptVector(etiss::InterruptVector *vec, ETISS_CPU *cpu)
{
    delete vec;
}

% if global_irq_en_reg is not None:
etiss::InterruptEnable *${core_name}Arch::createInterruptEnable(ETISS_CPU *cpu)
{
<% ref = "" if len(global_irq_en_reg.children) > 0 else "&" %>\
    return new etiss::MappedInterruptEnable<etiss::uint${main_reg.size}>(${ref}((${core_name} *)cpu)->${global_irq_en_reg.name}, ${global_irq_en_mask});
}

void ${core_name}Arch::deleteInterruptEnable(etiss::InterruptEnable *en, ETISS_CPU *cpu)
{
    delete en;
}
% endif
