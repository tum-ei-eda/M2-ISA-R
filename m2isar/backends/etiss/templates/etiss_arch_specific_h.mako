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
 * This file contains the architecture specific header for the ${core_name}
 * core architecture.
 *
 * WARNING: This file contains user-added code, be mindful when overwriting this with
 * generated code!
 */

#ifndef ETISS_${core_name}Arch_${core_name}ARCHSPECIFICIMP_H_
#define ETISS_${core_name}Arch_${core_name}ARCHSPECIFICIMP_H_

#include <cstdint>
#include "etiss/Instruction.h"
#include "etiss/VirtualStruct.h"
#include "etiss/jit/CPU.h"
#include "${core_name}.h"
#include "${core_name}Funcs.h"

/**
    @brief VirtualStruct for ${core_name} architecture to faciliate register acess

    @details VirtualStruct enables user to access certain register via their name without knowning ETISS hierarchy of a
    core. Further fiels might be needed to enable gdbserver etc.

*/
class RegField_${core_name} : public etiss::VirtualStruct::Field
{
  private:
    const unsigned gprid_;

  public:
    RegField_${core_name}(etiss::VirtualStruct &parent, unsigned gprid)
        // clang-format off
        : Field(
            parent,
            std::string("${main_reg.name}") + etiss::toString(gprid),
            std::string("${main_reg.name}") + etiss::toString(gprid),
            R|W,
            ${int(main_reg.ty.element_type.size / 8)}
        ),
        // clang-format on
        gprid_(gprid)
    {
    }

    RegField_${core_name}(etiss::VirtualStruct &parent, std::string name, unsigned gprid)
        // clang-format off
        : Field(
            parent,
            name,
            name,
            R|W,
            ${int(main_reg.ty.element_type.size / 8)}
        ),
        // clang-format on
        gprid_(gprid)
    {
    }

    virtual ~RegField_${core_name}() {}

  protected:
    virtual uint64_t _read(size_t offset) const
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        % if len(main_reg.children) > 0:
        return (uint64_t) *((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_];
        % else:
        return (uint64_t) ((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_];
        % endif
        // clang-format on
    }

    virtual void _write(uint64_t val, size_t offset)
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
        % if len(main_reg.children) > 0:
        *((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_] = (etiss_uint${main_reg.ty.element_type.size}) val;
        % else:
        ((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_] = (etiss_uint${main_reg.ty.element_type.size}) val;
        % endif
        // clang-format on
    }
};

% if float_reg:
class FloatRegField_${core_name} : public etiss::VirtualStruct::Field
{
  private:
    const unsigned gprid_;

  public:
    FloatRegField_${core_name}(etiss::VirtualStruct &parent, unsigned gprid)
        // clang-format off
            : Field(parent,
              std::string("${float_reg.name}")+etiss::toString(gprid),
              std::string("${float_reg.name}")+etiss::toString(gprid),
              R|W,
              ${int(float_reg.ty.element_type.size / 8)}
            ),
            gprid_(gprid)
    // clang-format on
    {
    }

    FloatRegField_${core_name}(etiss::VirtualStruct &parent, std::string name, unsigned gprid)
        // clang-format off
        : Field(parent,
              name,
              name,
              R|W,
              ${int(float_reg.ty.element_type.size / 8)}
            ),
            gprid_(gprid)
    // clang-format on
    {
    }

    virtual ~FloatRegField_${core_name}() {}

  protected:
    virtual uint64_t _read(size_t offset) const
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        % if len(float_reg.children) > 0:
        return (uint64_t) *((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_];
        % else:
        return (uint64_t) ((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_];
        % endif
        // clang-format on
    }

    virtual void _write(uint64_t val, size_t offset)
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
        % if len(main_reg.children) > 0:
        *((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_] = (etiss_uint${float_reg.ty.element_type.size}) val;
        % else:
        ((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_] = (etiss_uint${float_reg.ty.element_type.size}) val;
        % endif
        // clang-format on
    }
};
% endif

% if vector_reg:
class VectorRegField_${core_name} : public etiss::VirtualStruct::Field
{
  private:
    const unsigned gprid_;

  public:
    VectorRegField_${core_name}(etiss::VirtualStruct &parent,unsigned gprid)
        // clang-format off
        : Field(parent,
                std::string("${vector_reg.name}")+etiss::toString(gprid),
                std::string("${vector_reg.name}")+etiss::toString(gprid),
                R|W,
                ${int((vector_reg.ty.length // 32) // (vector_reg.ty.element_type.size // 8))}
        ),
        gprid_(gprid)
    // clang-format on
    {
    }

    VectorRegField_${core_name}(etiss::VirtualStruct &parent, std::string name, unsigned gprid)
        // clang-format off
        : Field(parent,
                name,
                name,
                R|W,
                ${int((vector_reg.ty.length // 32) // (vector_reg.ty.element_type.size // 8))}
        ),
        gprid_(gprid)
    // clang-format on
    {
    }

     virtual ~VectorRegField_${core_name}() {}

  protected:
    virtual uint64_t _read(size_t offset) const
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        return (uint64_t) *((uint64_t*)&((${core_name}*)parent_.structure_)->${vector_reg.name}[gprid_ * width_ + sizeof(uint64_t) * offset]);
        // clang-format on
    }

    virtual void _write(uint64_t val, size_t offset)
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
        *((uint64_t*)&((${core_name}*)parent_.structure_)->${vector_reg.name}[gprid_ * width_ + sizeof(uint64_t)]) = (etiss_uint64) val;  // TODO: write V[gprid_] instead
        // clang-format on
    }
};
% endif

% if csr_reg:
class CSRField_${core_name} : public etiss::VirtualStruct::Field
{
  private:
    const unsigned gprid_;

  public:
    CSRField_${core_name}(etiss::VirtualStruct &parent, unsigned gprid)
        // clang-format off
        : Field(parent,
            std::string("${csr_reg.name}")+etiss::toString(gprid),
            std::string("${csr_reg.name}")+etiss::toString(gprid),
            R|W,
            ${int(csr_reg.ty.element_type.size / 8)}
        ),
        gprid_(gprid)
    // clang-format on
    {
    }

    CSRField_${core_name}(etiss::VirtualStruct &parent, std::string name, unsigned gprid)
        // clang-format off
      : Field(parent,
        name,
        name,
        R|W,
        ${int(csr_reg.ty.element_type.size / 8)}
      ),
      gprid_(gprid)
    // clang-format on
    {
    }

    virtual ~CSRField_${core_name}() {}

  protected:
    virtual uint64_t _read(size_t offset) const
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        return (uint64_t) ${core_name}_csr_read((ETISS_CPU*)parent_.structure_, nullptr, nullptr, (etiss_uint${csr_reg.ty.element_type.size}) gprid_);
        // clang-format on
    }

    virtual void _write(uint64_t val, size_t offset)
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
        ${core_name}_csr_write((ETISS_CPU*)parent_.structure_, nullptr, nullptr, gprid_, (etiss_uint${csr_reg.ty.element_type.size}) val);
        // clang-format on
    }
};
% endif


class pcField_${core_name} : public etiss::VirtualStruct::Field
{
  public:
    pcField_${core_name}(etiss::VirtualStruct &parent)
        // clang-format off
        : Field(
            parent,
            "instructionPointer",
            "instructionPointer",
            R|W,
            ${int(main_reg.ty.element_type.size / 8)}
        )
    // clang-format on
    {
    }

    virtual ~pcField_${core_name}() {}

  protected:
    virtual uint64_t _read(size_t offset) const
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        return (uint64_t) ((ETISS_CPU *)parent_.structure_)->instructionPointer;
        // clang-format on
    }

    virtual void _write(uint64_t val, size_t offset)
    {
        // clang-format off
        assert((offset == 0 || (offset < (bitwidth_ / sizeof(uint64_t)))) && "Virtualstruct field offset out of range");
        etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
        ((ETISS_CPU *)parent_.structure_)->instructionPointer = (etiss_uint${main_reg.ty.element_type.size}) val;
        // clang-format on
    }
};

#endif
