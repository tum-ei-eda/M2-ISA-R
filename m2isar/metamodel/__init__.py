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

Any model traversal should use a :subclass`` of the ExprVisitor MetaClass including the needed
transformations/ recursive calls. For examples on how the recursive generate functions look like,
see the ExprVisitor MetaClass with its default generate function in :mod:`m2isar.metamodel.utils.ExprVisitor`
Multiple examples of such visitors can be found in the :mod:`m2isar.backends` submodules,
e.g. :mod:`m2isar.backends.etiss.instruction_transform` or :mod:`m2isar.backends.isa_manual.visitor`.
But also the metamodel builders in :mod:`m2isar.frontends.coredsl2` use this approach to build
the model from the parse tree. As well as the Frontend.

Usually a M2-ISA-R behavioral model is traversed from top to bottom. Necessary contextual
information is either stored globally within the self object of the ExprVisitor or passed to lower levels
by a user-defined `context` object for local stack-based information. Each object should then
generate a piece of output (e.g. c-code for ETISS) and return it to its parent. Value passing between
generation functions is completely user-defined, :mod:`m2isar.backends.etiss.instruction_transform`
uses complex objects in lower levels of translation and switches to strings for the two highest levels of
the hierarchy.
"""

import pickle
import inspect
import logging
from typing import Union
from pathlib import Path
from dataclasses import dataclass

from m2isar.metamodel import type_info

from . import arch, behav, code_info

M2_METAMODEL_VERSION = 3


def patch_model(module):
	"""Monkey patch transformation functions inside `module`
	into :mod:`m2isar.metamodel.behav` classes

	Transformation functions must have a specific signature for this to work:

	`def transform(self: <behav Class>, context: Any)`

	where `<behav Class>` is the class in :mod:`m2isar.metamodel.behav` which this
	transformation is associated with. Context can be any user-defined object to keep track
	of additional contextual information, if needed.
	"""

	logger = logging.getLogger("patch_model")
	# import warnings
	# warnings.warn(
	logger.warning(
		"The monkey-patching based patch_model function is deprecated."
		"Please move to the new class-based visitors/mutators",
	# 	DeprecationWarning
	)

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

intrinsic_defs = [
	arch.Intrinsic("__encoding_size", 16, type_info.TypeKind.UINT),
]

intrinsics = {x.name: x for x in intrinsic_defs}

#@property
#def intrinsics():
#	return {x.name: x for x in intrinsic_defs}

@dataclass
class M2Model:
	model_version: int
	cores: "dict[str, arch.CoreDef]"
	sets: "dict[str, arch.InstructionSet]"
	code_infos: "dict[int, code_info.CodeInfoBase]"

	def __post_init__(self):
		self.line_infos: dict[int, code_info.LineInfo] = {}
		self.function_infos: dict[int, code_info.FunctionInfo] = {}

		for idx, c in self.code_infos.items():
			if isinstance(c, code_info.LineInfo):
				self.line_infos[idx] = c
			elif isinstance(c, code_info.FunctionInfo):
				self.function_infos[idx] = c


def load_model(
    model_path: Union[str, Path], allow_missmatch: bool = False
) -> M2Model:
    logger = logging.getLogger("load_model")
    logger.debug("loading model: %s", str(model_path))
    with open(model_path, "rb") as f:
        model_obj: M2Model = pickle.load(f)
    assert isinstance(model_obj, M2Model), "Expected M2Model"
    required_version = M2_METAMODEL_VERSION
    if model_obj.model_version != required_version:
        err_handler = logger.warning if allow_missmatch else RuntimeError
        err_handler("Loaded model version mismatch")
    return model_obj


def dump_model(
    model_obj: M2Model, out_path: Union[str, Path], ignore_suffix: bool = False
):
    logger = logging.getLogger("dump_model")
    if not ignore_suffix:
        out_path = Path(out_path)
        suffix = out_path.suffix
        required_suffix = ".m2isarmodel"
        if suffix not in [required_suffix]:
            assert len(suffix) == 0, f"Invalid suffix: {suffix}"
            out_path = out_path.parent / f"{out_path.stem}{required_suffix}"
        else:
            assert suffix == required_suffix, f"Invalid suffix: {suffix}, Expected: {required_suffix}"
    logger.debug("dumping model: %s", out_path)
    with open(out_path, "wb") as f:
        pickle.dump(model_obj, f)
