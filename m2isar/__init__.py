# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""This is the top-level M2-ISA-R package. The project is divided into three major parts:

* :mod:`m2isar.metamodel`, the metamodel classes and helpers.
* :mod:`m2isar.backends`, consumers of M2-ISA-R models. Provided are an architecture plugin
  generator for ETISS and a graphical tool to inspect M2-ISA-R models.
* :mod:`m2isar.frontends`, producers of M2-ISA-R models. Currently provided is a parser for
  CoreDSL 2 ISA models.
"""

from collections.abc import Iterable

class M2Error(Exception):
	pass

class M2ValueError(ValueError, M2Error):
	pass

class M2NameError(NameError, M2Error):
	pass

class M2DuplicateError(M2NameError):
	pass

class M2TypeError(TypeError, M2Error):
	pass

class M2SyntaxError(SyntaxError, M2Error):
	pass

def flatten(xs):
	for x in xs:
		if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
			yield from flatten(x)
		else:
			yield x
