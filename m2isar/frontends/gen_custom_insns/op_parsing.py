"""
Templates for Operations modeled with the M2-ISA-R metamodel.
New instructions are added by updating the dict 'OP_TEMPLATES'
In this dict instructions keywords are mapped to a function,
	that has an argument 'operands' of type Dict[str, behav.IndexedReference]'
They need to return any subclass of behav.Basenode, but not behav.assignment
	as they get put into an assignmenat after key lookup (load/store inst is not possible right now)
The reasoning behind it, is that this way they can be chained to create new instructions
"""

from typing import Callable, Dict, List, Union

from .op_models import alu_ops, simd
from ...metamodel import behav
from .operands import Operand


def parse_op(operands: Dict[str, Operand], name: str) -> behav.Operation:
	"""Looks up the op name and puts it into an assignment"""
	try:
		expr = OPS[name](operands)
	except KeyError as exc:
		raise KeyError(f"Instruction '{name}' not implemented!") from exc

	if isinstance(expr, behav.Operation):
		return expr
	if isinstance(expr, behav.Assignment):
		return behav.Operation([expr])
	if isinstance(expr, list) and isinstance(expr[0], behav.BaseNode):
		# assuming simd instr
		return behav.Operation(expr)
	if isinstance(expr, behav.BaseNode):
		# if its not an operation, list of basenodes, or assignment
		# i just assume for now that we need to put it in an assignment
		# this would need to be changed to allow for e.g. load/store
		return behav.Operation([mm_assignment(operands, expr)])

	raise TypeError(f"The entry for Key '{name}' produces an unsupported type!")


def mm_assignment(
	operands: Dict[str, Operand], expr: behav.BaseNode
) -> behav.Assignment:
	"""rd = expr"""
	rd_ref = operands["rd"].to_metemodel_ref("rd")
	return behav.Assignment(rd_ref, expr)


# operations without assignment or behav.Operations()
OPS: Dict[
	str, Callable[[Dict[str, Operand]], Union[behav.BaseNode, List[behav.BaseNode]]]
] = {}

# TODO This could maybe be done automaticly for all the files in the instructions folder
OPS.update(alu_ops.OPS)
OPS.update(simd.OPS)
