from lark import Tree
from lark.visitors import Visitor_Recursive


class InstructionSetStorage(Visitor_Recursive):
	def __init__(self):
		self.instruction_sets = {}
		self.core_defs = {}

	def visit(self, tree):
		for child in tree.children:
			if isinstance(child, Tree):
				self._call_userfunc(child)

	def instruction_set(self, tree):
		name = tree.children[0]

		assert name not in self.instruction_sets
		self.instruction_sets[name] = tree
		pass

	def extend_ins_set(self, ins_set_name):
		extensions = self.instruction_sets[ins_set_name].children[1]
		if extensions:
			ret = [ins_set_name]
			for extension in extensions.children:
				ret = self.extend_ins_set(extension) + ret
			return ret
		else:
			return [ins_set_name]

	def core_def(self, tree):
		name, contributing_types = tree.children[0:2]
		ins_set_queue = []
		known_sets = set()
		for ct in contributing_types.children:
			new_sets = self.extend_ins_set(ct)
			for new_set in new_sets:
				if new_set not in known_sets:
					known_sets.add(new_set)
					ins_set_queue.append(self.instruction_sets[new_set])

		ins_set_queue.append(tree)
		self.core_defs[name] = ins_set_queue
