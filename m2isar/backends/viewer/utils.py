from typing import TYPE_CHECKING

if TYPE_CHECKING:
	import tkinter as tk
	from tkinter import ttk

class TreeGenContext:
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