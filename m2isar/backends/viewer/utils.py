# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Utility stuff for M2-ISA-R viewer"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	import tkinter as tk
	from tkinter import ttk

class TreeGenContext:
	"""Data keeping class for recursive TreeView generation"""

	def __init__(self, tree: "ttk.Treeview", parent) -> None:
		self.tree = tree
		self.parent_stack = [parent]

	@property
	def parent(self):
		return self.parent_stack[-1]

	def push(self, new_id):
		self.parent_stack.append(new_id)

	def pop(self):
		return self.parent_stack.pop()
