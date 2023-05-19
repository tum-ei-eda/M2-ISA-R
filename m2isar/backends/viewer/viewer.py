# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Viewer tool to visualize an M2-ISA-R model hierarchy."""

import argparse
import logging
import pathlib
import pickle
import tkinter as tk
from collections import defaultdict
from tkinter import ttk

from m2isar.backends.viewer.utils import TreeGenContext

from ...metamodel import arch, patch_model
from ...metamodel.utils.expr_preprocessor import (process_functions,
                                                  process_instructions)
from . import treegen

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
	parser.add_argument('-s', '--separate', action='store_true', help="Generate separate .cpp files for each instruction set.")
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
		models: "dict[str, arch.CoreDef]" = pickle.load(f)

	# preprocess model
	for core_name, core in models.items():
		logger.info("preprocessing model %s", core_name)
		process_functions(core)
		process_instructions(core)

	# load Ttk TreeView transformer functions
	patch_model(treegen)

	# create main Tk window
	root = tk.Tk()
	root.title("M2-ISA-R Viewer")

	tree = ttk.Treeview(root, columns=(1,))
	tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

	scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=tree.yview)
	tree.configure(yscroll=scrollbar.set)
	scrollbar.pack(side=tk.LEFT, fill=tk.Y)

	#tree.heading(0, text="Item")
	tree.heading("#0", text="Item")
	tree.heading(1, text="Value")

	# add each core to the treeview
	for core_name, core_def in sorted(models.items()):
		core_id = tree.insert("", tk.END, text=core_name)

		# add constants to tree
		consts_id = tree.insert(core_id, tk.END, text="Constants")
		for const_name, const_def in sorted(core_def.constants.items()):
			tree.insert(consts_id, tk.END, text=const_name, values=(const_def.value,))

		# add memories to tree
		mems_id = tree.insert(core_id, tk.END, text="Memories")
		for mem_name, mem_def in sorted(core_def.memories.items()):
			tree.insert(mems_id, tk.END, text=mem_name, values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",))

		# add memory aliases to tree
		alias_id = tree.insert(core_id, tk.END, text="Memory Aliases")
		for mem_name, mem_def in sorted(core_def.memory_aliases.items()):
			tree.insert(alias_id, tk.END, text=f"{mem_name} ({mem_def.parent.name})", values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",))

		# add auxillary attributes
		tree.insert(core_id, tk.END, text="Main Memory Object", values=(core_def.main_memory,))
		tree.insert(core_id, tk.END, text="Main Register File Object", values=(core_def.main_reg_file,))
		tree.insert(core_id, tk.END, text="PC Memory Object", values=(core_def.pc_memory,))

		# add functions to tree
		fns_id = tree.insert(core_id, tk.END, text="Functions")
		for fn_name, fn_def in core_def.functions.items():
			fn_id = tree.insert(fns_id, tk.END, text=fn_name, values=("extern" if fn_def.extern else ""))

			# add returns and throws information
			return_str = "None" if fn_def.size is None else f"{fn_def.data_type} {fn_def.size}"
			tree.insert(fn_id, tk.END, text="Return", values=(return_str,))
			tree.insert(fn_id, tk.END, text="Throws", values=(fn_def.throws))

			# generate and add attributes
			attrs_id = tree.insert(fn_id, tk.END, text="Attributes")

			for attr, ops in fn_def.attributes.items():
				attr_id = tree.insert(attrs_id, tk.END, text=attr)
				for op in ops:
					context = TreeGenContext(tree, attr_id)
					op.generate(context)

			# generate and add parameters
			params_id = tree.insert(fn_id, tk.END, text="Parameters")

			for param_name, param_def in fn_def.args.items():
				tree.insert(params_id, tk.END, text=param_name, values=(f"{param_def.data_type} {param_def.size}",))

			# generate and add function behavior
			context = TreeGenContext(tree, fn_id)
			fn_def.operation.generate(context)

		# group instructions by size
		instrs_by_size = defaultdict(dict)

		for k, v in core_def.instructions.items():
			instrs_by_size[v.size][k] = v

		# sort instructions by encoding
		for k, v in instrs_by_size.items():
			instrs_by_size[k] = dict(sorted(v.items(), key=sort_instruction, reverse=True))

		instrs_top_id = tree.insert(core_id, tk.END, text="Instructions")

		# generate instruction size groups
		for size, instrs in sorted(instrs_by_size.items()):
			instrs_id = tree.insert(instrs_top_id, tk.END, text=f"Width {size}")

			# generate instructions
			for (code, mask), instr_def in instrs.items():
				opcode_str = "{code:0{width}x}:{mask:0{width}x}".format(code=code, mask=mask, width=int(instr_def.size/4))

				instr_id = tree.insert(instrs_id, tk.END, text=f"{instr_def.ext_name} : {instr_def.name}", values=(opcode_str,), tags=("mono",))

				# generate encoding
				enc_str = []
				for enc in instr_def.encoding:
					if isinstance(enc, arch.BitVal):
						enc_str.append(f"{enc.value:0{enc.length}b}")
					elif isinstance(enc, arch.BitField):
						enc_str.append(f"{enc.name}[{enc.range.upper}:{enc.range.lower}]")

				tree.insert(instr_id, tk.END, text="Encoding", values=(" ".join(enc_str),))
				tree.insert(instr_id, tk.END, text="Assembly", values=(instr_def.assembly,))
				tree.insert(instr_id, tk.END, text="Throws", values=(instr_def.throws))
				attrs_id = tree.insert(instr_id, tk.END, text="Attributes")

				# generate attributes
				for attr, ops in instr_def.attributes.items():
					attr_id = tree.insert(attrs_id, tk.END, text=attr.name)
					for op in ops:
						context = TreeGenContext(tree, attr_id)
						op.generate(context)

				# generate behavior
				context = TreeGenContext(tree, instr_id)
				instr_def.operation.generate(context)

	#tree.tag_configure("mono", font=font.nametofont("TkFixedFont"))

	root.mainloop()

if __name__ == "__main__":
	main()
