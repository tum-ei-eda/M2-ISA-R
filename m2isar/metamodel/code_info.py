# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2024
# Chair of Electrical Design Automation
# Technical University of Munich

from dataclasses import dataclass, field
from enum import Enum, auto


class LineInfoPlacement(Enum):
	AFTER = auto()
	BEFORE = auto()

@dataclass
class CodeInfoBase:
	"""Base class for tracking code info."""

	id: int = field(init=False)
	"""Automatically calculated unique ID for tracking purposes in consumer programs."""

	file_path: str
	start_chr: int
	stop_chr: int
	start_line_no: int
	stop_line_no: int

	__id_counter = 0
	database = {}
	"""A global database of all created CodeInfo objects."""

	def __post_init__(self):
		self.id = CodeInfoBase.__id_counter
		CodeInfoBase.__id_counter += 1
		CodeInfoBase.database[self.id] = self

	def line_eq(self, other):
		if isinstance(other, self.__class__):
			return self.file_path == other.file_path and \
				self.start_line_no == other.start_line_no #and \
				#self.stop_line_no == other.stop_line_no
		return NotImplemented

	def __hash__(self) -> int:
		return hash(self.id)

	def line_hash(self):
		return hash((self.file_path, self.start_line_no, self.stop_line_no))

@dataclass(eq=False)
class LineInfo(CodeInfoBase):
	placement: LineInfoPlacement = LineInfoPlacement.AFTER

@dataclass(eq=False)
class FunctionInfo(CodeInfoBase):
	fn_name: str

class LineInfoFactory:
	"""Factory class to create non-overlapping LineInfo objects."""

	tracker = {}

	@classmethod
	def make(cls, file_path, start_chr, stop_chr, start_line_no, stop_line_no, placement=LineInfoPlacement.AFTER):
		ret = cls.tracker.get((file_path, start_chr, stop_chr))
		if ret is None:
			ret = LineInfo(file_path, start_chr, stop_chr, start_line_no, stop_line_no, placement)
			cls.tracker[(file_path, start_chr, stop_chr)] = ret

		return ret

class FunctionInfoFactory:
	"""Factory class to create non-overlapping FunctionInfo objects."""

	tracker = {}

	@classmethod
	def make(cls, file_path, start_chr, stop_chr, start_line_no, stop_line_no, fn_name):
		ret = cls.tracker.get((file_path, start_chr, stop_chr))
		if ret is None:
			ret = FunctionInfo(file_path, start_chr, stop_chr, start_line_no, stop_line_no, fn_name)
			cls.tracker[(file_path, start_chr, stop_chr)] = ret

		return ret
