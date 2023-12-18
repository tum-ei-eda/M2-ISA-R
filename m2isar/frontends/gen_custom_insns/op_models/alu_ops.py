"""ALU instructions of the core v extension"""

from functools import partial
from typing import Callable, Dict
from ....metamodel import arch, behav as mm


def aluN(operands: Dict[str, mm.IndexedReference], operator: str) -> mm.BinaryOperation:
	# TODO does m2iar differentiate between logical an arithmetic shift?
	"""(rs1 {operator} rs2) >> ls3"""
	return mm.BinaryOperation(
		binary_op(operands, operator), mm.Operator(">>"), operands["ls3"]
	)


def aluRN(
	operands: Dict[str, mm.IndexedReference], operator: str
) -> mm.BinaryOperation:
	# TODO does m2iar differentiate between logical an arithmetic shift?
	# At least CDSL2 doesn't
	"""(rs1 {operator} rs2 + 2^(ls3-1)) >> ls3"""
	pow2_part = mm.BinaryOperation(
		mm.IntLiteral(2),
		mm.Operator("^"),
		mm.BinaryOperation(operands["ls3"], mm.Operator("-"), mm.IntLiteral(1)),
	)
	return mm.BinaryOperation(
		mm.BinaryOperation(binary_op(operands, operator), mm.Operator("+"), pow2_part),
		mm.Operator(">>"),
		operands["ls3"],
	)


def slet(operands: Dict[str, mm.IndexedReference]) -> mm.Conditional:
	"""rs1 <= rs2 ? 1:0"""
	return mm.Conditional(
		[mm.BinaryOperation(operands["rs1"], mm.Operator("<="), operands["rs2"])],
		[mm.IntLiteral(1), mm.IntLiteral(0)],
	)


def min_max(
	operands: Dict[str, mm.IndexedReference], _min: bool = True
) -> mm.Conditional:
	"""min/max(rs1, rs2)"""  # TODO this is not yet sign dependant
	return mm.Conditional(
		[binary_op(operands, "<" if _min else ">")], [operands["rs1"], operands["rs2"]]
	)


def mm_abs(operands: Dict[str, mm.IndexedReference]) -> mm.Conditional:
	"""rs1 < 0 ? -rs1 : rs1"""
	return mm.Conditional(
		[mm.BinaryOperation(operands["rs1"], mm.Operator("<"), mm.IntLiteral(0))],
		[mm.UnaryOperation(mm.Operator("-"), operands["rs1"]), operands["rs1"]],
	)


def binary_op(
	operands: Dict[str, mm.IndexedReference], operator: str
) -> mm.BinaryOperation:
	"""rs1 {operator} rs2"""
	return mm.BinaryOperation(operands["rs1"], mm.Operator(operator), operands["rs2"])


OPS: Dict[str, Callable[[Dict[str, mm.IndexedReference]], mm.BaseNode]] = {
	"abs": partial(mm_abs),
	"addN": partial(aluN, operator="+"),
	"subN": partial(aluN, operator="-"),
	"min": partial(min_max, _min=True),
	"max": partial(min_max, _min=False),
	"addRN": partial(aluRN, operator="+"),
	"subRN": partial(aluRN, operator="-"),
	"add": partial(binary_op, operator="+"),
}
