# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026
# Chair of Electrical Design Automation
# Technical University of Munich
# Modifed by JK TUW ECS

"""Viewer tool to generate a DOT representation for an M2-ISA-R hierarchy."""
import abc
import argparse
import logging
import pathlib
import pickle
from collections import defaultdict
from anytree import Node, RenderTree

from .utils import TextTreeGenContext

from ...metamodel import M2_METAMODEL_VERSION, M2Model, arch
from ...metamodel.utils.expr_preprocessor import (process_attributes,
                                                  process_functions,
                                                  process_instructions)
from .treegen import TreeGenVisitor

logger = logging.getLogger("viewer")


class TreeBuilder:

    def __init__(self):
        pass

    @abc.abstractmethod
    def _add_node(self, name: str, parent=None, values=None, **kwargs):
        raise NotImplementedError

    def add_node(self, name: str, parent=None, values=None, **kwargs):
        return self._add_node(name, parent=parent, values=values, **kwargs)


# class TkTreeBuilder(TreeBuilder):
# 
#     def __init__(self, name: str):
#         super().__init__(name)
#         self.root = tk.Tk()
#         self.root.title(self.name)
#         self.treeview = ttk.Treeview(root, columns=(1,))
#         self.treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
#         scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=self.treeview.yview)
#         self.treeview.configure(yscroll=scrollbar.set)
#         scrollbar.pack(side=tk.LEFT, fill=tk.Y)
#         self.treeview.heading("#0", text="Item")
#         self.treeview.heading(1, text="Value")
# 
#     def _add_node(self, name: str, parent=None, **kwargs):
#         return tree.insert(parent, tk.END, text=name)


class AnyTreeBuilder(TreeBuilder):

    def __init__(self, name: str):
        super().__init__()
        self.root = Node("Tree")

    def _add_node(self, name: str, parent="", **kwargs):
        return Node(name, parent=parent, **kwargs)



def sort_instruction(entry: "tuple[tuple[int, int], arch.Instruction]"):
	"""Instruction sort key function. Sorts most restrictive encoding first."""
	(code, mask), _ = entry
	return bin(mask).count("1"), code
	#return code, bin(mask).count("1")

def main():
	"""Main app entrypoint."""

	# read command line args
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .m2isarmodel file containing the models to generate.")
	# parser.add_argument("--text", "-t", action="store_true", help="TODO")
	parser.add_argument("--operation", "-o", action="store_true", help="TODO")
	parser.add_argument("--constants", action="store_true", help="TODO")
	parser.add_argument("--functions", action="store_true", help="TODO")
	parser.add_argument("--attributes", action="store_true", help="TODO")
	parser.add_argument("--memories", action="store_true", help="TODO")
	# TODO: out file/dir
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	args = parser.parse_args()

	# initialize logging
	logging.basicConfig(level=getattr(logging, args.log.upper()))

	# resolve model paths
	top_level = pathlib.Path(args.top_level)
	abs_top_level = top_level.resolve()
	search_path = abs_top_level.parent.parent
	model_fname = abs_top_level

	if abs_top_level.suffix == ".core_desc":
		logger.warning(".core_desc file passed as input. This is deprecated behavior, please change your scripts!")
		search_path = abs_top_level.parent
		model_path = search_path.joinpath('gen_model')

		if not model_path.exists():
			raise FileNotFoundError('Models not generated!')
		model_fname = model_path / (abs_top_level.stem + '.m2isarmodel')

	output_base_path = search_path.joinpath('gen_output')
	output_base_path.mkdir(exist_ok=True)

	logger.info("loading models")

	# load models
	with open(model_fname, 'rb') as f:
		model_obj: "M2Model" = pickle.load(f)

	if model_obj.model_version != M2_METAMODEL_VERSION:
		logger.warning("Loaded model version mismatch")

	cores = model_obj.cores
	sets = model_obj.sets
	if len(sets) > 0:
		raise NotImplementedError

	# preprocess model
	# for core_name, core in cores.items():
	# 	logger.info("preprocessing model %s", core_name)
	# 	process_functions(core)
	# 	process_instructions(core)
	# 	process_attributes(core)

	# load Ttk TreeView transformer functions
	visitor = TreeGenVisitor()
	tree = AnyTreeBuilder("Tree")
	sets_node = tree.add_node("Sets", parent=tree.root)
	cores_node = tree.add_node("Cores", parent=tree.root)

	# add each core to the treeview
	for core_name, core_def in sorted(cores.items()):
		core_node = tree.add_node("Core", parent=cores_node, values=core_name)

		# add constants to tree
		if args.constants:
			consts_node = tree.add_node("Constants", parent=core_node)
			for const_name, const_def in sorted(core_def.constants.items()):
				# break  # TODO: drop
				_ = tree.add_node(f"{const_name}", parent=consts_node, values=const_def.value)

		# add memories to tree
		if args.memories:
			mems_node = tree.add_node("Memories", parent=core_node, values="{}")
			for mem_name, mem_def in sorted(core_def.memories.items()):
				# break  # TODO
				_ = tree.add_node(
					f"{mem_name}",
					parent=mems_node,
					values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",),
				)

			# add memory aliases to tree
			aliases_node = tree.add_node("Memory Aliases", parent=core_node, values=("{}",))
			for mem_name, mem_def in sorted(core_def.memory_aliases.items()):
				# break  # TODO
				_ = tree.add_node(
					f"{mem_name} ({mem_def.parent.name})",
					parent=aliases_node,
					values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",),
				)

		# add auxillary attributes (TODO)
		# tree.insert(core_id, tk.END, text="Main Memory Object", values=(core_def.main_memory,))
		# tree.insert(core_id, tk.END, text="Main Register File Object", values=(core_def.main_reg_file,))
		# TODO: float_reg_file?
		# tree.insert(core_id, tk.END, text="PC Memory Object", values=(core_def.pc_memory,))

		# add functions to tree
		if args.functions:
			fns_node = tree.add_node("Functions", parent=core_node, values=("{}",))
			for fn_name, fn_def in core_def.functions.items():
				# break  # TODO
				fn_node = tree.add_node(fn_name, parent=fns_node, values=(("extern" if fn_def.extern else ""),))

				# add returns and throws information
				return_str = "None" if fn_def.size is None else f"{fn_def.data_type} {fn_def.size}"
				_ = tree.add_node("Return", parent=fn_node, values=(return_str,))
				_ = tree.add_node("Throws", parent=fn_node, values=(fn_def.throws,))

				if args.attributes:
					# generate and add attributes
					attrs_node = tree.add_node("Attributes", parent=fn_node)

					for attr, ops in fn_def.attributes.items():
						attr_node = tree.add_node(attr, parent=attrs_node)
						for op in ops:
							context = TextTreeGenContext(parent=attr_node)
							visitor.generate(op, context)

				# generate and add parameters
				params_node = tree.add_node("Parameters", parent=fn_node)

				for param_name, param_def in fn_def.args.items():
					_ = tree.add_node(param_name, parent=params_node, values=(f"{param_def.data_type} {param_def.size}",))

				# generate and add function behavior
				if args.operation:
					context = TextTreeGenContext(parent=fn_node)
					visitor.generate(fn_def.operation, context)

		# group instructions by size
		instrs_by_size = defaultdict(dict)

		for k, v in core_def.instructions.items():
			instrs_by_size[v.size][k] = v

		# sort instructions by encoding
		for k, v in instrs_by_size.items():
			instrs_by_size[k] = dict(sorted(v.items(), key=sort_instruction, reverse=True))

		instrs_top_node = tree.add_node("Instructions", parent=core_node)

		# generate instruction size groups
		for size, instrs in sorted(instrs_by_size.items()):
			if size == 16:
				continue
			instrs_node = tree.add_node(f"Width {size}", parent=instrs_top_node)

			# generate instructions
			for (code, mask), instr_def in instrs.items():
				opcode_str = "{code:0{width}x}:{mask:0{width}x}".format(code=code, mask=mask, width=int(instr_def.size/4))

				instr_node = tree.add_node(f"{instr_def.ext_name} : {instr_def.name}", parent=instrs_node, values=(opcode_str,))

				# generate encoding
				enc_str = []
				for enc in instr_def.encoding:
					if isinstance(enc, arch.BitVal):
						enc_str.append(f"{enc.value:0{enc.length}b}")
					elif isinstance(enc, arch.BitField):
						enc_str.append(f"{enc.name}[{enc.range.upper}:{enc.range.lower}]")

				_ = tree.add_node("Encoding", parent=instr_node, values=(" ".join(enc_str),))
				_ = tree.add_node("Assembly", parent=instr_node, values=(instr_def.assembly,))
				_ = tree.add_node("Throws", parent=instr_node, values=(instr_def.throws,))
				if args.attributes:
					attrs_node = tree.add_node("Attributes", parent=instr_node, values="{}")

					# generate attributes
					for attr, ops in instr_def.attributes.items():
						attr_node = tree.add_node(attr.name, parent=attrs_node)
						for op in ops:
							context = TextTreeGenContext(parent=attr_node)
							visitor.generate(op, context)

				# generate behavior
				if args.operation:
					context = TextTreeGenContext(parent=instr_node)
					visitor.generate(instr_def.operation, context)
				break # TODO
	print("============================")
	# text = ""
	for pre, fill, node in RenderTree(tree.root):
	    suffix = ""
	    if hasattr(node, "values"):
	        if node.values is not None:
	            suffix = f" [{node.values}]"
	    print("%s%s%s" % (pre, node.name, suffix))
	print("============================")
	# from anytree.dotexport import RenderTreeGraph
	from anytree.exporter import UniqueDotExporter
	from anytree.exporter import MermaidExporter
	def edgeattrfunc(node, child):
	    return 'label="%s:%s"' % (node.name, child.name)
	def edgefunc(node, child):
		return f"--{child.edge}-->"

	def nodeattrfunc(node):
		if hasattr(node, "values"):
			if node.values is not None:
				if isinstance(node.values, arch.Instruction):
					label = node.name
					xlabel = node.values
				else:
					label = node.values
					xlabel = node.name
			else:
				label = node.name
				xlabel = ""
			return f'shape=box,label="{label}",xlabel="{xlabel}"'
		return f'shape=box,label="{node.name}"'

	# TODO: update nodenamefunc for memories to point upwards
	# return

	exporter = UniqueDotExporter(
		tree.root,
		# options=["rankdir=LR;"],
		# nodefunc=nodefunc,
		# nodenamefunc=nodenamefunc,
		nodeattrfunc=nodeattrfunc,
		# edgeattrfunc=edgeattrfunc,
		maxlevel=100,
	)
	# .to_picture("tree2.png")
	dot_file = "tree3.dot"
	with open(dot_file, "w") as f:
		for line in exporter:
			print(line)
			f.write(line + "\n")
	for line in MermaidExporter(tree.root):
		print(line)

if __name__ == "__main__":
	main()
