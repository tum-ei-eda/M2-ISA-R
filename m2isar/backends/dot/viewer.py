# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich
#
# Copyright (C) 2026
# Modifed by JK TUW ECS

"""Viewer tool to generate a DOT representation for an M2-ISA-R hierarchy."""

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
	root = Node("Tree")
	sets_node = Node("Sets", parent=root)
	cores_node = Node("Cores", parent=root)

	# add each core to the treeview
	for core_name, core_def in sorted(cores.items()):
		core_node = Node("Core", parent=cores_node, value=core_name)

		# add constants to tree
		consts_node = Node("Constants", parent=core_node)
		for const_name, const_def in sorted(core_def.constants.items()):
			break  # TODO: drop
			_ = Node(f"{const_name}", parent=consts_node, value=const_def.value)

		# add memories to tree
		mems_node = Node("Memories", parent=core_node, value="{}")
		for mem_name, mem_def in sorted(core_def.memories.items()):
			break  # TODO
			_ = Node(
				f"{mem_name}",
				parent=mems_node,
				value=f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",
			)

		# add memory aliases to tree
		aliases_node = Node("Memory Aliases", parent=core_node, value="{}")
		for mem_name, mem_def in sorted(core_def.memory_aliases.items()):
			break  # TODO
			_ = Node(
				f"{mem_name} ({mem_def.parent.name})",
				parent=aliases_node,
				value=f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",
			)

		# add auxillary attributes (TODO)
		# tree.insert(core_id, tk.END, text="Main Memory Object", values=(core_def.main_memory,))
		# tree.insert(core_id, tk.END, text="Main Register File Object", values=(core_def.main_reg_file,))
		# TODO: float_reg_file?
		# tree.insert(core_id, tk.END, text="PC Memory Object", values=(core_def.pc_memory,))

		# add functions to tree
		fns_node = Node("Functions", parent=core_node, value="{}")
		for fn_name, fn_def in core_def.functions.items():
			break  # TODO
			fn_node = Node(fn_name, parent=fns_node, value="extern" if fn_def.extern else "")

			# add returns and throws information
			return_str = "None" if fn_def.size is None else f"{fn_def.data_type} {fn_def.size}"
			_ = Node("Return", parent=fn_node, value=return_str)
			_ = Node("Throws", parent=fn_node, value=fn_def.throws)

			# generate and add attributes
			attrs_node = Node("Attributes", parent=fn_node)

			for attr, ops in fn_def.attributes.items():
				attr_node = Node(attr, parent=attrs_node)
				for op in ops:
					context = TextTreeGenContext(parent=attr_node)
					visitor.generate(op, context)

			# generate and add parameters
			params_node = Node("Parameters", parent=fn_node)

			for param_name, param_def in fn_def.args.items():
				_ = Node(param_name, parent=params_node, value=f"{param_def.data_type} {param_def.size}")

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

		instrs_top_node = Node("Instructions", parent=core_node)

		# generate instruction size groups
		for size, instrs in sorted(instrs_by_size.items()):
			instrs_node = Node(f"Width {size}", parent=instrs_top_node)

			# generate instructions
			for (code, mask), instr_def in instrs.items():
				opcode_str = "{code:0{width}x}:{mask:0{width}x}".format(code=code, mask=mask, width=int(instr_def.size/4))

				instr_node = Node(f"{instr_def.ext_name} : {instr_def.name}", parent=instrs_node, value=opcode_str)

				# generate encoding
				enc_str = []
				for enc in instr_def.encoding:
					if isinstance(enc, arch.BitVal):
						enc_str.append(f"{enc.value:0{enc.length}b}")
					elif isinstance(enc, arch.BitField):
						enc_str.append(f"{enc.name}[{enc.range.upper}:{enc.range.lower}]")

				_ = Node("Encoding", parent=instr_node, value=" ".join(enc_str))
				_ = Node("Assembly", parent=instr_node, value=instr_def.assembly)
				_ = Node("Throws", parent=instr_node, value=instr_def.throws)
				attrs_node = Node("Attributes", parent=instr_node, value="{}")

				# generate attributes
				for attr, ops in instr_def.attributes.items():
					attr_node = Node(attr.name, parent=attrs_node)
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
	for pre, fill, node in RenderTree(root):
	    suffix = ""
	    if hasattr(node, "value"):
	        if node.value is not None:
	            suffix = f" [{node.value}]"
	    print("%s%s%s" % (pre, node.name, suffix))
	print("============================")
	# from anytree.dotexport import RenderTreeGraph
	from anytree.exporter import UniqueDotExporter
	def edgeattrfunc(node, child):
	    return 'label="%s:%s"' % (node.name, child.name)
	def edgefunc(node, child):
		return f"--{child.edge}-->"
	
	def nodeattrfunc(node):
		if hasattr(node, "value"):
			if node.value is not None:
				if isinstance(node.value, arch.Instruction):
					label = node.name
					xlabel = node.value
				else:
					label = node.value
					xlabel = node.name
			else:
				label = node.name
				xlabel = ""
			return f'shape=box,label="{label}",xlabel="{xlabel}"'
		return f'shape=box,label="{node.name}"'
	
	# TODO: update nodenamefunc for memories to point upwards
	# return
	
	exporter = UniqueDotExporter(
		root,
		# options=["rankdir=LR;"],
		# nodefunc=nodefunc,
		# nodenamefunc=nodenamefunc,
		nodeattrfunc=nodeattrfunc,
		# edgeattrfunc=edgeattrfunc,
		maxlevel=100,
	)
	# .to_picture("tree2.png")
	for line in exporter:
		print(line)

if __name__ == "__main__":
	main()
