# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026
# Chair of Electrical Design Automation
# Technical University of Munich

"""Utility stuff for M2-ISA-R DOT (Graphviz) backend."""

from anytree import Node

class TreeGenContext:
	"""Data keeping class for recursive TreeView generation"""

	def __init__(self, parent=None) -> None:
		if parent:
			self.nodes = [parent]
		else:
			self.nodes = [Node("Tree")]
		self.parent_stack = [parent]

	@property
	def parent(self):
		print("parent", self.parent_stack)
		return self.parent_stack[-1]

	def push(self, new_id):
		print("push", new_id)
		self.parent_stack.append(new_id)

	def pop(self):
		print("pop")
		return self.parent_stack.pop()

	def insert(self, text, values=None):
		print("insert", text, values)
		self.push(self.insert2(text, values=values))

	def insert2(self, text, values=None):
		raise NotImplementedError

class TextTreeGenContext(TreeGenContext):
	def __init__(self, parent=None) -> None:
		super().__init__(parent=parent)

	def insert2(self, text, values=None):
		print("insert2", text, values)
		if isinstance(values, (list, set, tuple)):
			if len(values) == 1:
				values = values[0]
		return Node(text, parent=self.parent, values=values)
