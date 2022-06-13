## SPDX-License-Identifier: Apache-2.0
##
## This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
##
## Copyright (C) 2022
## Chair of Electrical Design Automation
## Technical University of Munich
\

${f'{"// "+instr_name+" ":-<80}'}
static InstructionDefinition ${instr_name.lower().replace('.', '_')}_${'_'.join(seen_fields)} (
	ISA${enc_idx}_${core_name},
	"${instr_name.lower()}",
	(uint${enc_idx}_t) ${code_string},
	(uint${enc_idx}_t) ${mask_string},
	[] (BitArray & ba,etiss::CodeSet & cs,InstructionContext & ic)
	{

// -----------------------------------------------------------------------------
${'\n'.join(misc_code)}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
${fields_code}
// -----------------------------------------------------------------------------

		CodePart & partInit = cs.append(CodePart::INITIALREQUIRED);

		partInit.code() = std::string("//${instr_name}\n");

// -----------------------------------------------------------------------------
${operation}
// -----------------------------------------------------------------------------

		% for reg in sorted(reg_dependencies):
		partInit.getRegisterDependencies().add(reg_name[${reg}], ${core_default_width});
		% endfor
		% for reg in sorted(reg_affected):
		partInit.getAffectedRegisters().add(reg_name[${reg}], ${core_default_width});
		% endfor
		partInit.getAffectedRegisters().add("instructionPointer", 32);

		return true;
	},
	0,
	[] (BitArray & ba, Instruction & instr)
	{
// -----------------------------------------------------------------------------
${fields_code}
// -----------------------------------------------------------------------------

		std::stringstream ss;
// -----------------------------------------------------------------------------
${asm_printer_code}
// -----------------------------------------------------------------------------
		return ss.str();
	}
);
