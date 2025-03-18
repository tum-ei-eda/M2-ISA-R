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

	file_path: str
	start_chr: int
	stop_chr: int
	start_line_no: int
	stop_line_no: int

	id: int = field(default=None)
	"""Automatically calculated unique ID for tracking purposes in consumer programs."""

	__id_counter = 0
	database = {}
	"""A global database of all created CodeInfo objects."""

	def __post_init__(self):
		if self.id is None:
			self.id = CodeInfoBase.__id_counter
			CodeInfoBase.__id_counter += 1

		CodeInfoBase.database[self.id] = self

	def line_eq(self, other):
		if isinstance(other, self.__class__) or isinstance(self, other.__class__):
			return self.file_path == other.file_path and \
				self.start_line_no == other.start_line_no #and \
				#self.stop_line_no == other.stop_line_no

		raise NotImplementedError

	def __hash__(self) -> int:
		return hash(self.id)

	def line_hash(self):
		return hash((self.file_path, self.start_line_no, self.stop_line_no))

@dataclass(eq=False)
class LineInfo(CodeInfoBase):
	placement: LineInfoPlacement = field(default=LineInfoPlacement.AFTER)

@dataclass(eq=False)
class FunctionInfo(CodeInfoBase):
	fn_name: str = None

@dataclass(eq=False)
class BranchInfo(LineInfo):
	branch_id: int = field(default=None)

@dataclass(eq=False)
class BranchEntryInfo(BranchInfo):
	placement: LineInfoPlacement = field(default=LineInfoPlacement.BEFORE, init=False)
	def __post_init__(self):
		super().__post_init__()

		if self.branch_id is None:
			self.branch_id = self.id

class InfoFactory:
	def __init__(self, cls_to_use):
		self.cls_to_use = cls_to_use
		self.tracker: "dict[tuple[str, int, int], CodeInfoBase]" = {}

	def make(self, file_path, start_chr, stop_chr, start_line_no, stop_line_no, *args, **kwargs):
		ret = self.tracker.get((file_path, start_chr, stop_chr))
		if ret is None:
			ret = self.cls_to_use(file_path, start_chr, stop_chr, start_line_no, stop_line_no, *args, **kwargs)
			self.tracker[((file_path, start_chr, stop_chr))] = ret

		return ret

LineInfoFactory = InfoFactory(LineInfo)
FunctionInfoFactory = InfoFactory(FunctionInfo)
BranchEntryInfoFactory = InfoFactory(BranchEntryInfo)
