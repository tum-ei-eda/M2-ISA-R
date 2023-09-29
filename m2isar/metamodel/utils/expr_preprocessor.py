# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""A helper module for applying all preprocessing functions in this package to
functions and instructions.
"""

import logging
from itertools import chain

from ... import M2ValueError
from .. import arch, patch_model
from . import (ScalarStaticnessContext, expr_simplifier, function_staticness,
               function_throws, scalar_staticness)

logger = logging.getLogger("preprocessor")

def process_attributes(core: arch.CoreDef):
	"""Apply all preprocessing to memory, function and instruction attributes in `core`."""

	patch_model(expr_simplifier)

	for _, obj_def in chain(core.functions.items(), core.instructions.items(), core.memories.items(), core.memory_aliases.items()):
		for attr_name, attr_defs in obj_def.attributes.items():
			logger.debug("simplifying expressions for attr %s of %s", attr_name, obj_def.name)
			for attr_def in attr_defs:
				attr_def.generate(None)

def process_functions(core: arch.CoreDef):
	"""Apply all preprocessing to all functions in `core`."""

	for fn_name, fn_def in core.functions.items():
		patch_model(expr_simplifier)
		logger.debug("simplifying expressions for fn %s", fn_name)
		fn_def.operation.generate(None)

		patch_model(function_throws)
		logger.debug("checking throws for fn %s", fn_name)
		throws = fn_def.operation.generate(None)
		fn_def.throws = throws or arch.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn_def.attributes

		context = ScalarStaticnessContext()
		patch_model(scalar_staticness)
		logger.debug("examining scalar staticness for fn %s", fn_name)
		fn_def.operation.generate(context)

		patch_model(function_staticness)
		logger.debug("examining function staticness for fn %s", fn_name)

		if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn_def.attributes and arch.FunctionAttribute.ETISS_STATICFN in fn_def.attributes:
			raise M2ValueError("etiss_needs_arch and etiss_staticfn not allowed together, in function %s", fn_name)

		#if not fn_def.extern and (arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn_def.attributes or arch.FunctionAttribute.ETISS_STATICFN in fn_def.attributes):
		#	raise M2ValueError("etiss_needs_arch and etiss_staticfn only allowed for extern functions, in function %s", fn_name)

		if fn_def.extern or arch.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn_def.attributes:
			if arch.FunctionAttribute.ETISS_STATICFN in fn_def.attributes:
				fn_def.static = True

		else:
			ret = fn_def.operation.generate(None)
			fn_def.static = ret

def process_instructions(core: arch.CoreDef):
	"""Apply all preprocessing to all instructions in `core`."""

	for _, instr_def in core.instructions.items():
		patch_model(expr_simplifier)
		logger.debug("simplifying expressions for instr %s", instr_def.name)
		instr_def.operation.generate(None)

		patch_model(function_throws)
		logger.debug("checking throws for instr %s", instr_def.name)
		throws = instr_def.operation.generate(None)
		instr_def.throws = throws

		context = ScalarStaticnessContext()
		patch_model(scalar_staticness)
		logger.debug("examining staticness for instr %s", instr_def.name)
		instr_def.operation.generate(context)
