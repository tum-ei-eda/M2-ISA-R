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

/**
	@brief VirtualStruct for ${core_name} architecture to faciliate register acess

	@details VirtualStruct enables user to access certain register via their name without knowning ETISS hierarchy of a core.
				Further fiels might be needed to enable gdbserver etc.

*/
class RegField_${core_name} : public etiss::VirtualStruct::Field{
private:
	const unsigned gprid_;
public:
	RegField_${core_name}(etiss::VirtualStruct & parent,unsigned gprid)
		: Field(parent,
			std::string("${main_reg.name}")+etiss::toString(gprid),
			std::string("${main_reg.name}")+etiss::toString(gprid),
			R|W,
			${int(main_reg.size / 8)}
		),
		gprid_(gprid)
	{}

	RegField_${core_name}(etiss::VirtualStruct & parent, std::string name, unsigned gprid)
		: Field(parent,
			name,
			name,
			R|W,
			${int(main_reg.size / 8)}
		),
		gprid_(gprid)
	{}

	virtual ~RegField_${core_name}(){}

protected:
	virtual uint64_t _read() const {
		% if len(main_reg.children) > 0:
		return (uint64_t) *((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_];
		% else:
		return (uint64_t) ((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_];
		% endif
	}

	virtual void _write(uint64_t val) {
		etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
		% if len(main_reg.children) > 0:
		*((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_] = (etiss_uint${main_reg.size}) val;
		% else:
		((${core_name}*)parent_.structure_)->${main_reg.name}[gprid_] = (etiss_uint${main_reg.size}) val;
		% endif
	}
};

% if float_reg:
class FloatRegField_${core_name} : public etiss::VirtualStruct::Field{
private:
	const unsigned gprid_;
public:
	FloatRegField_${core_name}(etiss::VirtualStruct & parent,unsigned gprid)
		: Field(parent,
			std::string("${float_reg.name}")+etiss::toString(gprid),
			std::string("${float_reg.name}")+etiss::toString(gprid),
			R|W,
			${int(float_reg.size / 8)}
		),
		gprid_(gprid)
	{}

	FloatRegField_${core_name}(etiss::VirtualStruct & parent, std::string name, unsigned gprid)
		: Field(parent,
			name,
			name,
			R|W,
			${int(float_reg.size / 8)}
		),
		gprid_(gprid)
	{}

	virtual ~FloatRegField_${core_name}(){}

protected:
	virtual uint64_t _read() const {
		% if len(main_reg.children) > 0:
		return (uint64_t) *((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_];
		% else:
		return (uint64_t) ((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_];
		% endif
	}

	virtual void _write(uint64_t val) {
		etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
		% if len(main_reg.children) > 0:
		*((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_] = (etiss_uint${float_reg.size}) val;
		% else:
		((${core_name}*)parent_.structure_)->${float_reg.name}[gprid_] = (etiss_uint${float_reg.size}) val;
		% endif
	}
};
% endif

class pcField_${core_name} : public etiss::VirtualStruct::Field{
public:
	pcField_${core_name}(etiss::VirtualStruct & parent)
		: Field(parent,
			"instructionPointer",
			"instructionPointer",
			R|W,
			${int(main_reg.size / 8)}
		)
	{}

	virtual ~pcField_${core_name}(){}

protected:
	virtual uint64_t _read() const {
		return (uint64_t) ((ETISS_CPU *)parent_.structure_)->instructionPointer;
	}

	virtual void _write(uint64_t val) {
		etiss::log(etiss::VERBOSE, "write to ETISS cpu state", name_, val);
		((ETISS_CPU *)parent_.structure_)->instructionPointer = (etiss_uint${main_reg.size}) val;
	}
};

#endif