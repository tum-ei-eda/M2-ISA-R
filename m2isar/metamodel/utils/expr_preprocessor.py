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
from .. import arch, attribute_info
from .expr_simplifier import ExprSimplifierVisitor
from .function_staticness import FunctionStaticnessVisitor
from .function_throws import FunctionThrowsVisitor
from .scalar_staticness import ScalarStaticnessVisitor

logger = logging.getLogger("preprocessor")

def process_attributes(core: arch.CoreDef):
	"""Apply all preprocessing to memory, function and instruction attributes in `core`."""

	simplifier = ExprSimplifierVisitor()

	for _, obj_def in chain(core.functions.items(), core.instructions.items(), core.memories.items(), core.memory_aliases.items()):
		for attr_name, attr_defs in obj_def.attributes.items():
			logger.debug("simplifying expressions for attr %s of %s", attr_name, obj_def.name)
			for attr_def in attr_defs:
				simplifier.generate(attr_def, None)

def process_functions(core: arch.CoreDef):
	"""Apply all preprocessing to all functions in `core`."""

	simplifier = ExprSimplifierVisitor()
	function_throws_visitor = FunctionThrowsVisitor()
	scalar_staticness_visitor = ScalarStaticnessVisitor()
	function_staticness_visitor = FunctionStaticnessVisitor()

	for fn_name, fn_def in core.functions.items():
		logger.debug("simplifying expressions for fn %s", fn_name)
		simplifier.generate(fn_def.operation, None)

		logger.debug("checking throws for fn %s", fn_name)
		throws = function_throws_visitor.generate(fn_def.operation, None)
		fn_def.throws = throws or attribute_info.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn_def.attributes

		context = attribute_info.ScalarStaticnessContext()
		logger.debug("examining scalar staticness for fn %s", fn_name)
		scalar_staticness_visitor.generate(fn_def.operation, context)

		logger.debug("examining function staticness for fn %s", fn_name)

		if attribute_info.FunctionAttribute.ETISS_NEEDS_ARCH in fn_def.attributes and attribute_info.FunctionAttribute.ETISS_STATICFN in fn_def.attributes:
			raise M2ValueError("etiss_needs_arch and etiss_staticfn not allowed together, in function %s", fn_name)

		#if not fn_def.extern and (attribute_info.FunctionAttribute.ETISS_NEEDS_ARCH in fn_def.attributes or attribute_info.FunctionAttribute.ETISS_STATICFN in fn_def.attributes):
		#	raise M2ValueError("etiss_needs_arch and etiss_staticfn only allowed for extern functions, in function %s", fn_name)

		if fn_def.extern or attribute_info.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn_def.attributes:
			if attribute_info.FunctionAttribute.ETISS_STATICFN in fn_def.attributes:
				fn_def.static = True

		else:
			ret = function_staticness_visitor.generate(fn_def.operation, None)
			fn_def.static = ret

def process_instructions(core: arch.CoreDef):
	"""Apply all preprocessing to all instructions in `core`."""

	simplifier = ExprSimplifierVisitor()
	function_throws_visitor = FunctionThrowsVisitor()
	scalar_staticness_visitor = ScalarStaticnessVisitor()

	for _, instr_def in core.instructions.items():
		logger.debug("simplifying expressions for instr %s", instr_def.name)
		simplifier.generate(instr_def.operation, None)

		logger.debug("checking throws for instr %s", instr_def.name)
		throws = function_throws_visitor.generate(instr_def.operation, None)
		instr_def.throws = throws

		context = attribute_info.ScalarStaticnessContext()
		logger.debug("examining staticness for instr %s", instr_def.name)
		scalar_staticness_visitor.generate(instr_def.operation, context)
