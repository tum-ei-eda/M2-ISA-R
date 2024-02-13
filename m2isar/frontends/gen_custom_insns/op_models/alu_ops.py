"""ALU instructions of the core v extension"""

from functools import partial
from typing import Callable, Dict

from ....metamodel import behav
from ..operands import Operand, to_metamodel_operands


def binary_op(operands: Dict[str, Operand], operator: str) -> behav.BinaryOperation:
	"""rs1 {operator} rs2"""
	mm_operands = to_metamodel_operands(operands)
	return behav.BinaryOperation(
		mm_operands["rs1"],
		behav.Operator(operator),
		mm_operands["rs2"],
	)


def alu_imm(operands: Dict[str, Operand], operator: str):
	"""rs1 {operator} immediate"""
	mm_operands = to_metamodel_operands(operands)
	immediate = next(
		imm for imm in mm_operands.values() if isinstance(imm, behav.NamedReference)
	)

	return behav.BinaryOperation(
		mm_operands["rs1"],
		behav.Operator(operator),
		immediate,
	)


def alu_n(operands: Dict[str, Operand], operator: str) -> behav.BinaryOperation:
	"""(rs1 {operator} rs2) >> Is3"""
	mm_operands = to_metamodel_operands(operands)
	return behav.BinaryOperation(
		binary_op(operands, operator),
		behav.Operator(">>"),
		mm_operands["Is3"],
	)


def alu_rn(operands: Dict[str, Operand], operator: str) -> behav.BinaryOperation:
	# It seems like m2isar does not differentiate between logical an arithmetic shift
	"""(rs1 {operator} rs2 + 2^(Is3-1)) >> Is3"""
	mm_operands = to_metamodel_operands(operands)
	pow2_part = behav.BinaryOperation(
		behav.IntLiteral(2),
		behav.Operator("^"),
		behav.BinaryOperation(
			mm_operands["Is3"],
			behav.Operator("-"),
			behav.IntLiteral(1),
		),
	)
	return behav.BinaryOperation(
		behav.BinaryOperation(
			binary_op(operands, operator), behav.Operator("+"), pow2_part
		),
		behav.Operator(">>"),
		mm_operands["Is3"],
	)


def slet(operands: Dict[str, Operand]) -> behav.Conditional:
	"""rs1 <= rs2 ? 1:0"""
	mm_operands = to_metamodel_operands(operands)
	return behav.Conditional(
		[
			behav.BinaryOperation(
				mm_operands["rs1"],
				behav.Operator("<="),
				mm_operands["rs2"],
			)
		],
		[behav.IntLiteral(1), behav.IntLiteral(0)],
	)


def min_max(operands: Dict[str, Operand], operator: str = "<") -> behav.Conditional:
	"""min/max(rs1, rs2)"""  # TODO this is not yet sign dependant
	mm_operands = to_metamodel_operands(operands)
	return behav.Conditional(
		[binary_op(operands, operator)],
		[
			mm_operands["rs1"],
			mm_operands["rs2"],
		],
	)


def mm_abs(operands: Dict[str, Operand]) -> behav.Ternary:
	"""rs1 < 0 ? -rs1 : rs1"""
	mm_operands = to_metamodel_operands(operands)
	return behav.Ternary(
		behav.BinaryOperation(
			mm_operands["rs1"],
			behav.Operator("<"),
			behav.IntLiteral(0),
		),
		behav.UnaryOperation(behav.Operator("-"), mm_operands["rs1"]),
		mm_operands["rs1"],
	)


OPS: Dict[str, Callable[[Dict[str, Operand]], behav.BaseNode]] = {
	"abs": partial(mm_abs),
	"addN": partial(alu_n, operator="+"),
	"subN": partial(alu_n, operator="-"),
	"min": partial(min_max, operator="<"),
	"max": partial(min_max, operator=">"),
	"addRN": partial(alu_rn, operator="+"),
	"subRN": partial(alu_rn, operator="-"),
	"add": partial(binary_op, operator="+"),
	"addI": partial(alu_imm, operator="+"),
}
