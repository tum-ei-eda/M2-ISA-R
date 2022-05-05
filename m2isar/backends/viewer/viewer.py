import argparse
import logging
import pathlib
import pickle
import tkinter as tk
from tkinter import ttk

from m2isar.backends.viewer.utils import TreeGenContext

from ...metamodel import arch, patch_model
from . import treegen

logger = logging.getLogger("viewer")


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('top_level', help="A .m2isarmodel file containing the models to generate.")
	parser.add_argument('-s', '--separate', action='store_true', help="Generate separate .cpp files for each instruction set.")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
	args = parser.parse_args()

	logging.basicConfig(level=getattr(logging, args.log.upper()))
	logger = logging.getLogger("etiss_writer")

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

	spec_name = abs_top_level.stem
	output_base_path = search_path.joinpath('gen_output')
	output_base_path.mkdir(exist_ok=True)

	logger.info("loading models")

	with open(model_fname, 'rb') as f:
		models: "dict[str, arch.CoreDef]" = pickle.load(f)

	patch_model(treegen)

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

	tree.insert("", tk.END, "top", text=model_fname.stem)

	for core_name, core_def in sorted(models.items()):
		#print(f"core {core_name}")
		tree.insert("top", tk.END, core_name, text=core_name)

		tree.insert(core_name, tk.END, core_name+"consts", text="Constants")
		for const_name, const_def in sorted(core_def.constants.items()):
			#print(f"constant {const_name} = {const_def.value}")
			tree.insert(core_name+"consts", tk.END, core_name+const_name, text=const_name, values=(const_def.value,))

		tree.insert(core_name, tk.END, core_name+"mems", text="Memories")
		for mem_name, mem_def in sorted(core_def.memories.items()):
			#print(f"memory {mem_name}: {mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}")
			tree.insert(core_name+"mems", tk.END, core_name+mem_name, text=mem_name, values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",))

		tree.insert(core_name, tk.END, core_name+"mem_alias", text="Memory Aliases")
		for mem_name, mem_def in sorted(core_def.memory_aliases.items()):
			#print(f"memory alias {mem_name} ({mem_def.parent.name}): {mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}")
			tree.insert(core_name+"mem_alias", tk.END, core_name+mem_name, text=f"{mem_name} ({mem_def.parent.name})", values=(f"{mem_def.range.upper}:{mem_def.range.lower} ({mem_def.range.length}), {mem_def.size}",))

		tree.insert(core_name, tk.END, core_name+"main_mem", text="Main Memory Object", values=(core_def.main_memory,))
		tree.insert(core_name, tk.END, core_name+"main_reg", text="Main Register File Object", values=(core_def.main_reg_file,))
		tree.insert(core_name, tk.END, core_name+"pc_mem", text="PC Memory Object", values=(core_def.pc_memory,))

		tree.insert(core_name, tk.END, core_name+"instrs", text="Instructions")
		for (code, mask), instr_def in sorted(core_def.instructions.items()):
			opcode_str = f"{code:08x}:{mask:08x}"
			#print(f"instruction {opcode_str} ({instr_def.name})")
			tree.insert(core_name+"instrs", tk.END, core_name+opcode_str, text=opcode_str, values=(instr_def.name,))

			enc_str = []
			for enc in instr_def.encoding:
				if isinstance(enc, arch.BitVal):
					enc_str.append(f"{enc.value:0{enc.length}b}")
				elif isinstance(enc, arch.BitField):
					enc_str.append(f"{enc.name}[{enc.range.upper}:{enc.range.lower}]")
			#print(" ".join(enc_str))

			tree.insert(core_name+opcode_str, tk.END, core_name+opcode_str+"encoding", text="Encoding", values=(" ".join(enc_str),))
			tree.insert(core_name+opcode_str, tk.END, core_name+opcode_str+"assembly", text="Assembly", values=(instr_def.disass,))
			tree.insert(core_name+opcode_str, tk.END, core_name+opcode_str+"attrs", text="Attributes")

			for attr in instr_def.attributes:
				tree.insert(core_name+opcode_str+"attrs", tk.END, core_name+opcode_str+"attrs"+attr.name, text=attr.name)

			context = TreeGenContext(tree, core_name+opcode_str)
			instr_def.operation.generate(context)



	root.mainloop()
	pass

if __name__ == "__main__":
	main()
