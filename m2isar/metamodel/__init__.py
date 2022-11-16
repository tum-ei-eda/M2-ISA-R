# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""This module contains the M2-ISA-R metamodel classes to build an ISA from. The M2-ISA-R
metamodel is split into two submodules, one for architectural description, one for the behavioral
description.

Also included are preprocessing functions, mostly to simplify a model and to extract information
about scalar and function staticness as well as exceptions.

Any model traversal should use the :func:`patch_model` function and a module including the needed
transformations. :func:`patch_model` monkey patches transformation functions into the classes of the
behavior model, therefore separating model code from transformation code. For examples on how
these transformation functions look like, see either the modules in :mod:`m2isar.metamodel.utils`
or the main code generation module :mod:`m2isar.backends.etiss.instruction_transform`.
"""

import inspect
import logging
from . import behav

def patch_model(module):
	"""Monkey patch transformation functions inside `module`
	into :mod:`m2isar.metamodel.behav` classes

	Transformation functions must have a specific signature for this to work:

	`def transform(self: <behav Class>, context: Any)`

	where `<behav Class>` is the class in :mod:`m2isar.metamodel.behav` which this
	transformation is associated with.
	"""

	logger = logging.getLogger("patch_model")

	for _, fn in inspect.getmembers(module, inspect.isfunction):
		sig = inspect.signature(fn)
		param = sig.parameters.get("self")
		if not param:
			continue
		if not param.annotation:
			raise ValueError(f"self parameter not annotated correctly for {fn}")
		if not issubclass(param.annotation, behav.BaseNode):
			raise TypeError(f"self parameter for {fn} has wrong subclass")

		logger.debug("patching %s with fn %s", param.annotation, fn)
		param.annotation.generate = fn
