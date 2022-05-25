import logging

from ...metamodel import arch, patch_model
from . import scalar_staticness, function_staticness

logger = logging.getLogger("preprocessor")

def process_functions(core: arch.CoreDef):
	for fn_name, fn_def in core.functions.items():
		patch_model(scalar_staticness)
		logger.debug("examining scalar staticness for fn %s", fn_name)
		fn_def.operation.generate(None)

		patch_model(function_staticness)
		logger.debug("examining function staticness for fn %s", fn_name)

		if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn_def.attributes and arch.FunctionAttribute.ETISS_STATICFN in fn_def.attributes:
			raise M2ValueError("etiss_needs_arch and etiss_staticfn not allowed together, in function %s", fn_name)

		if not fn_def.extern and (arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn_def.attributes or arch.FunctionAttribute.ETISS_STATICFN in fn_def.attributes):
			raise M2ValueError("etiss_needs_arch and etiss_staticfn only allowed for extern functions, in function %s", fn_name)

		if fn_def.extern:
			if arch.FunctionAttribute.ETISS_STATICFN in fn_def.attributes:
				fn_def.static = True

		else:
			ret = fn_def.operation.generate(None)
			fn_def.static = ret

def process_instructions(core: arch.CoreDef):
	patch_model(scalar_staticness)

	for (code, mask), instr_def in core.instructions.items():
		logger.debug("examining staticness for instr %s", instr_def.name)
		instr_def.operation.generate(None)
