"""ALU instructions of the core v extension"""

from functools import partial
from typing import Callable, Dict
from ....metamodel import behav
from ..operands import Operand


def binary_op(
	operands: Dict[str, Operand], operator: str
) -> behav.BinaryOperation:
	"""rs1 {operator} rs2"""
	return behav.BinaryOperation(operands["rs1"].to_metemodel_ref("rs1"), behav.Operator(operator), operands["rs2"].to_metemodel_ref("rs2"))

def aluN(operands: Dict[str, Operand], operator: str) -> behav.BinaryOperation:
	# TODO does m2iar differentiate between logical an arithmetic shift?
	"""(rs1 {operator} rs2) >> ls3"""
	return behav.BinaryOperation(
		binary_op(operands, operator), behav.Operator(">>"), operands["ls3"].to_metemodel_ref("ls3")
	)


def aluRN(
	operands: Dict[str, Operand], operator: str
) -> behav.BinaryOperation:
	# TODO does m2iar differentiate between logical an arithmetic shift?
	# At least CDSL2 doesn't
	"""(rs1 {operator} rs2 + 2^(ls3-1)) >> ls3"""
	pow2_part = behav.BinaryOperation(
		behav.IntLiteral(2),
		behav.Operator("^"),
		behav.BinaryOperation(operands["ls3"].to_metemodel_ref("ls3"), behav.Operator("-"), behav.IntLiteral(1)),
	)
	return behav.BinaryOperation(
		behav.BinaryOperation(binary_op(operands, operator), behav.Operator("+"), pow2_part),
		behav.Operator(">>"),
		operands["ls3"].to_metemodel_ref("ls3"),
	)


def slet(operands: Dict[str, Operand]) -> behav.Conditional:
	"""rs1 <= rs2 ? 1:0"""
	return behav.Conditional(
		[behav.BinaryOperation(operands["rs1"].to_metemodel_ref("rs1"), behav.Operator("<="), operands["rs2"].to_metemodel_ref("rs2"))],
		[behav.IntLiteral(1), behav.IntLiteral(0)],
	)


def min_max(
	operands: Dict[str, Operand], _min: bool = True
) -> behav.Conditional:
	"""min/max(rs1, rs2)"""  # TODO this is not yet sign dependant
	return behav.Conditional(
		[binary_op(operands, "<" if _min else ">")], [operands["rs1"].to_metemodel_ref("rs1"), operands["rs2"].to_metemodel_ref("rs2")]
	)


def mm_abs(operands: Dict[str, Operand]) -> behav.Conditional:
	"""rs1 < 0 ? -rs1 : rs1"""
	return behav.Conditional(
		[behav.BinaryOperation(operands["rs1"].to_metemodel_ref("rs1"), behav.Operator("<"), behav.IntLiteral(0))],
		[behav.UnaryOperation(behav.Operator("-"), operands["rs1"].to_metemodel_ref("rs1")), operands["rs1"].to_metemodel_ref("rs1")],
	)



OPS: Dict[str, Callable[[Dict[str, Operand]], behav.BaseNode]] = {
	"abs": partial(mm_abs),
	"addN": partial(aluN, operator="+"),
	"subN": partial(aluN, operator="-"),
	"min": partial(min_max, _min=True),
	"max": partial(min_max, _min=False),
	"addRN": partial(aluRN, operator="+"),
	"subRN": partial(aluRN, operator="-"),
	"add": partial(binary_op, operator="+"),
}
