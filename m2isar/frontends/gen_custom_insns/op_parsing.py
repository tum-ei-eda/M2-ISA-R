"""
Templates for Operations modeled with the M2-ISA-R metamodel.
New instructions are added by updating the dict 'OP_TEMPLATES'
In this dict instructions keywords are mapped to a function,
	that has an argument 'operands' of type Dict[str, behav.IndexedReference]'
They need to return any subclass of behav.Basenode, but not behav.assignment
	as they get put into an assignmenat after key lookup (load/store inst is not possible right now)
The reasoning behind it, is that this way they can be chained to create new instructions
"""

from typing import Callable, Dict

from .op_models import alu_ops
from ...metamodel import behav, arch
from .operands import Operand

def _reg_indexed_ref(operands: Dict[str, Operand], reg_name: str) -> behav.IndexedReference:
	# TODO get memories of the dummy core from main.py
	registers = arch.Memory(
		"X", arch.RangeSpec(32), 32, {arch.MemoryAttribute.IS_MAIN_MEM: []}
	)
	return behav.IndexedReference(
		reference=registers,
		index=behav.NamedReference(
			arch.BitFieldDescr(
				reg_name,
				5,
				arch.DataType.S
				if operands[reg_name].sign == "s"
				else arch.DataType.U,
			)
		),
	)

def parse_op(operands: Dict[str, Operand], name: str) -> behav.Operation:
	"""Looksup the op name and puts it into an assignment"""
	try:
		expr = OPS[name](operands)
	except KeyError as exc:
		raise KeyError(f"Instruction '{name}' not implemented!") from exc
	return behav.Operation([mm_assignment(operands, expr)])


def mm_assignment(
	operands: Dict[str, Operand], expr: behav.BaseNode
) -> behav.Assignment:
	"""rd = expr"""
	rd_ref = _reg_indexed_ref(operands, "rd")
	return behav.Assignment(rd_ref, expr)


# operations without assignment or behav.Operations()
OPS: Dict[str, Callable[[Dict[str, Operand]], behav.BaseNode]] = {}

# TODO This could maybe be done automaticly for all the files in the instructions folder
OPS.update(alu_ops.OPS)
