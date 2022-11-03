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
${callback_code},
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
