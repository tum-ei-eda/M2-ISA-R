import inspect
import logging

def patch_model(module):
	"""Monkey patch transformation functions inside `m2isar.backends.etiss.instruction_transform module`
	into `m2isar.metamodel.behav` classes

	Transformation functions must have a specific signature for this to work:

	`def transform(self: <behav Class>, context: Any)`

	where `<behav Class>` is the class in `m2isar.metamodel.behav` which this transformation is associated with.
	"""

	logger = logging.getLogger("patch_model")

	for name, fn in inspect.getmembers(module, inspect.isfunction):
		sig = inspect.signature(fn)
		param = sig.parameters.get("self")
		if not param:
			logger.warning("no self parameter found in %s", fn)
			continue
		if not param.annotation:
			logger.warning("self parameter not annotated correctly for %s", fn)
			continue

		logger.debug("patching %s with fn %s", param.annotation, fn)
		param.annotation.generate = fn