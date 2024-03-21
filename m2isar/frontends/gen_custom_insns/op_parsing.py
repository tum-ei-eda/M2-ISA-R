"""
Templates for Operations modeled with the M2-ISA-R metamodel.
New instructions are added by updating the dict 'OP_TEMPLATES'
In this dict instructions keywords are mapped to a function,
	that has an argument 'operands' of type Dict[str, behav.IndexedReference]'
They need to return any subclass of behav.Basenode, but not behav.assignment
	as they get put into an assignmenat after key lookup (load/store inst is not possible right now)
The reasoning behind it, is that this way they can be chained to create new instructions
"""

from typing import Dict, Optional

from .op_models import alu_ops, simd, mac_ops
from ...metamodel import behav
from .operands import Operand
from .seal5_support import GMIRLegalization
from .op_models.template import OpcodeDict


def parse_op(operands: Dict[str, Operand], name: str, x0_guard: bool) -> tuple[behav.Operation, Optional[GMIRLegalization]]:
	"""Looks up the op name and puts it into an Operation"""
	try:
		operation_template = OPS[name]
	except KeyError as exc:
		raise KeyError(f"Instruction '{name}' not implemented!") from exc
	behavior, legalization = operation_template(operands)

	if isinstance(behavior, behav.Operation):
		raise ValueError("The item in the OPS dict should not be an operation!")
	if isinstance(behavior, behav.Assignment):
		if x0_guard:
			behavior = x0_guard_wraper(operands, behavior)
		return (behav.Operation([behavior]), legalization)
	if isinstance(behavior, list) and isinstance(behavior[0], behav.Assignment):
		# assuming simd instr
		if x0_guard:
			behavior = x0_guard_wraper(operands, behavior) # type: ignore
		return (behav.Operation([behavior]), legalization) # type: ignore
	if isinstance(behavior, behav.BaseNode):
		# if its not an operation, list of assignment, or assignment
		# i just assume for now that we need to put it in an assignment
		# this would need to be changed to allow for e.g. load/store
		behavior = mm_assignment(operands, behavior)
		if x0_guard:
			behavior = x0_guard_wraper(operands, behavior)
		return (behav.Operation([behavior]), legalization)

	raise TypeError(f"The entry for Key '{name}' returns an unsupported type!")


def x0_guard_wraper(operands, node: behav.BaseNode):
	"""Wrap the behavior in an Conditional check to prevent writes to X[0]"""
	rd = operands["rd"].to_metamodel_ref("rd", cast= False).index
	behavior = node if isinstance(node, list) else [node]
	return behav.Conditional([behav.BinaryOperation(rd, behav.Operator("!="), behav.IntLiteral(0))], behavior)


def mm_assignment(
	operands: Dict[str, Operand], expr: behav.BaseNode
) -> behav.Assignment:
	"""rd = expr"""
	rd_ref = operands["rd"].to_metamodel_ref("rd", cast=False)

	return behav.Assignment(rd_ref, expr)


# operations without assignment or behav.Operations()
OPS: OpcodeDict = {}

# TODO This could maybe be done automaticly for all the files in the instructions folder
OPS.update(alu_ops.OPS)
OPS.update(mac_ops.OPS)
OPS.update(simd.OPS)
