"""ALU instructions of the core v extension"""

from functools import partial
from typing import Dict

from ....metamodel import behav
from ..operands import Operand, to_metamodel_operands
from ..seal5_support import GMIRLegalization, operand_types
from .template import OpcodeDict


def binary_op_helper(operands: Dict[str, Operand], operator: str):
	"""rs1 {operator} rs2\n
	Only use this as a helper functions to reduce boilerplate code"""
	mm_operands = to_metamodel_operands(operands)
	return behav.BinaryOperation(
		mm_operands["rs1"],
		behav.Operator(operator),
		mm_operands["rs2"],
	)


def binary_op(operands: Dict[str, Operand], operator: str):
	"""rs1 {operator} rs2, with legalizations\n
	Use this function if you need legalizations"""
	types = operand_types(operands)
	for ty in types:
		if "32" in ty:  # Would need to be addapted for XLEN 64 support
			types.remove(ty)
	op_dict = {
		"+": ["G_ADD"],
		"-": ["G_SUB"],
		"&": ["G_AND"],  # TODO make sure G_AND means bitwise and
		"|": ["G_OR"],
		"^": ["G_XOR"],
	}
	if types:
		legalization = GMIRLegalization(op_dict[operator], types)
	else:
		legalization = None

	mm_operands = to_metamodel_operands(operands)
	return (
		behav.BinaryOperation(
			mm_operands["rs1"],
			behav.Operator(operator),
			mm_operands["rs2"],
		),
		legalization,
	)


def alu_imm(operands: Dict[str, Operand], operator: str):
	"""rs1 {operator} immediate"""
	mm_operands = to_metamodel_operands(operands)
	immediate = [
		imm for imm in mm_operands.values() if isinstance(imm, behav.NamedReference)
	]
	if len(immediate) > 1:
		raise RuntimeError("More than 1 immediate found!")
	immediate = immediate[0]

	types = operand_types(operands)
	for ty in types:
		if "32" in ty:  # Would need to be addapted for XLEN 64 support
			types.remove(ty)
	op_dict = {
		"+": ["G_ADD"],
		"-": ["G_SUB"],
		"&": ["G_AND"],  # TODO make sure G_AND means bitwise and
		"|": ["G_OR"],
		"^": ["G_XOR"],
	}
	if types:
		legalization = GMIRLegalization(op_dict[operator], types)
	else:
		legalization = None

	return (
		behav.BinaryOperation(
			mm_operands["rs1"],
			behav.Operator(operator),
			immediate,
		),
		legalization,
	)


def alu_n(operands: Dict[str, Operand], operator: str):
	"""(rs1 {operator} rs2) >> Is3"""
	mm_operands = to_metamodel_operands(operands)
	return (
		behav.BinaryOperation(
			binary_op_helper(operands, operator),
			behav.Operator(">>"),
			mm_operands["Is3"],
		),
		None,
	)


def alu_rn(operands: Dict[str, Operand], operator: str):
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
	return (
		behav.BinaryOperation(
			behav.BinaryOperation(
				binary_op_helper(operands, operator), behav.Operator("+"), pow2_part
			),
			behav.Operator(">>"),
			mm_operands["Is3"],
		),
		None,
	)


def slet(operands: Dict[str, Operand]):
	"""rs1 <= rs2 ? 1:0"""
	mm_operands = to_metamodel_operands(operands)
	return (
		behav.Conditional(
			[
				behav.BinaryOperation(
					mm_operands["rs1"],
					behav.Operator("<="),
					mm_operands["rs2"],
				)
			],
			[behav.IntLiteral(1), behav.IntLiteral(0)],
		),
		None,
	)


def min_max(operands: Dict[str, Operand], operator: str = "<"):
	"""min/max(rs1, rs2)"""
	# From https://github.com/Minres/CoreDSL/wiki/Expressions#comparisons:
	# "They perform a comparison based on the value represented by the operands,
	# 	and do not take the operand types into account."
	if operator not in ("<", ">"):
		raise ValueError("Operator must be either '<' or '>'!")

	if any(opr.sign == "s" for opr in operands.values()):
		generic_opc = "G_SMIN" if operator == "<" else "G_SMAX"
	else:
		generic_opc = "G_UMIN" if operator == "<" else "G_UMAX"

	types = operand_types(operands)

	mm_operands = to_metamodel_operands(operands)
	return (
		behav.Conditional(
			[binary_op_helper(operands, operator)],
			[
				mm_operands["rs1"],
				mm_operands["rs2"],
			],
		),
		GMIRLegalization([generic_opc], types),
	)


def mm_abs(operands: Dict[str, Operand]):
	"""rs1 < 0 ? -rs1 : rs1"""
	types = operand_types(operands)
	mm_operands = to_metamodel_operands(operands)
	return (
		behav.Ternary(
			behav.BinaryOperation(
				mm_operands["rs1"],
				behav.Operator("<"),
				behav.IntLiteral(0),
			),
			behav.UnaryOperation(behav.Operator("-"), mm_operands["rs1"]),
			mm_operands["rs1"],
		),
		GMIRLegalization(["G_ABS"], types),
	)


def ext(operands: Dict[str, Operand]):
	"""{S,Z}ext(rs1)"""
	# TODO Not sure how to handle this, There is a GMIR op for this but
	# extensions happen implicitly in CDSL2 afaik
	# Need to ask Philipp
	return (operands["rs1"].to_metamodel_ref("rs1"), None)


OPS: OpcodeDict = {
	"abs": partial(mm_abs),
	"slet": partial(slet),
	"min": partial(min_max, operator="<"),
	"max": partial(min_max, operator=">"),
	"ext": partial(ext),
	"addN": partial(alu_n, operator="+"),
	"subN": partial(alu_n, operator="-"),
	"addRN": partial(alu_rn, operator="+"),
	"subRN": partial(alu_rn, operator="-"),
	"add": partial(binary_op, operator="+"),
	"addI": partial(alu_imm, operator="+"),
}
