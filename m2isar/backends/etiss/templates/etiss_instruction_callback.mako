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
	}