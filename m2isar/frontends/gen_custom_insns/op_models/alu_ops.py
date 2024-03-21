"""ALU instructions of the core v extension"""

from functools import partial
from typing import Dict, Optional
from copy import copy

from ....metamodel import behav, arch
from ..operands import Operand, to_metamodel_operands
from ..seal5_support import GMIRLegalization, legalization_signdness, operand_types
from .template import OpcodeDict


def arithmetic_legalization(
	operands: Dict[str, Operand], operator: str
) -> Optional[GMIRLegalization]:
	"""Create legalization for basic arithmetic operators"""
	types = operand_types(operands)
	for ty in types:
		if "32" in ty:  # Would need to be addapted for XLEN 64 support
			types.remove(ty)
	sign = legalization_signdness(operands)

	op_dict = {
		"+": ["G_ADD"],
		"-": ["G_SUB"],
		"*": ["G_MUL"],
		"/": [f"G_{sign}DIV"],
		"%": [f"G_{sign}REM"],
		"&": ["G_AND"],  # TODO make sure G_AND means bitwise and
		"|": ["G_OR"],
		"^": ["G_XOR"],
	}
	if types:
		return GMIRLegalization(op_dict[operator], types)
	return None


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
	legalization = arithmetic_legalization(operands, operator)
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

	legalization = arithmetic_legalization(operands, operator)

	return (
		behav.BinaryOperation(
			mm_operands["rs1"],
			behav.Operator(operator),
			immediate,
		),
		legalization,
	)


def arithmetic_n(operands: Dict[str, Operand], operator: str):
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


def arithmetic_rn(operands: Dict[str, Operand], operator: str):
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


def arithmetic_nr(operands: Dict[str, Operand], operator: str):
	"""(rd +/- rs1) >> rs2[4:0], see cv.addNr"""
	mm_operands = to_metamodel_operands(operands)
	return (
		behav.BinaryOperation(
			behav.BinaryOperation(
				mm_operands["rd"], behav.Operator(operator), mm_operands["rs1"]
			),
			behav.Operator(">>"),
			behav.SliceOperation(
				mm_operands["rs2"], behav.IntLiteral(4), behav.IntLiteral(0)
			),
		),
		None,
	)


def arithmetic_rnr(operands: Dict[str, Operand], operator: str):
	"""(rD + rs1 + 2^(rs2[4:0]-1)) >>> rs2[4:0]; e.g. cv.addRNr"""
	mm_operands = to_metamodel_operands(operands)
	rs2_slice = behav.SliceOperation(
		mm_operands["rs2"], behav.IntLiteral(4), behav.IntLiteral(0)
	)
	pow2_part = behav.BinaryOperation(
		behav.IntLiteral(2),
		behav.Operator("^"),
		behav.BinaryOperation(
			copy(rs2_slice),
			behav.Operator("-"),
			behav.IntLiteral(1),
		),
	)
	return (
		behav.BinaryOperation(
			behav.BinaryOperation(
				behav.BinaryOperation(
					mm_operands["rd"], behav.Operator(operator), mm_operands["rs1"]
				),
				behav.Operator("+"),
				pow2_part,
			),
			behav.Operator(">>"),
			copy(rs2_slice),
		),
		None,
	)


def slet(operands: Dict[str, Operand]):
	"""rs1 <= rs2 ? 1:0"""
	mm_operands = to_metamodel_operands(operands)
	return (
		behav.Ternary(
			behav.BinaryOperation(
				mm_operands["rs1"],
				behav.Operator("<="),
				mm_operands["rs2"],
			),
			behav.IntLiteral(1),
			behav.IntLiteral(0),
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

	types = operand_types(operands)
	sign = legalization_signdness(operands)
	gmir_op = {
		"<": [f"G_{sign}MIN"],
		">": [f"G_{sign}MAX"],
	}

	mm_operands = to_metamodel_operands(operands)
	return (
		behav.Ternary(
			binary_op_helper(operands, operator),
			mm_operands["rs1"],
			mm_operands["rs2"],
		),
		GMIRLegalization(gmir_op[operator], types),
	)


def min_max_immediate(operands: Dict[str, Operand], operator: str = "<"):
	"""min/max(rs1, imm)"""
	if operator not in ("<", ">"):
		raise ValueError("Operator must be either '<' or '>'!")

	mm_operands = to_metamodel_operands(operands)
	return (
		behav.Ternary(
			behav.BinaryOperation(
				mm_operands["rs1"], behav.Operator(operator), mm_operands["imm5"]
			),
			mm_operands["rs1"],
			mm_operands["imm5"],
		),
		None,
	)


def mm_abs(operands: Dict[str, Operand]):
	"""rs1 < 0 ? -rs1 : rs1"""
	types = operand_types(operands)
	mm_operands = to_metamodel_operands(operands)
	return (
		behav.Ternary(
			behav.BinaryOperation(
				behav.TypeConv(arch.DataType.S, None, mm_operands["rs1"]),
				behav.Operator("<"),
				behav.IntLiteral(0),
			),
			behav.UnaryOperation(behav.Operator("-"), mm_operands["rs1"]),
			mm_operands["rs1"],
		),
		GMIRLegalization(["G_ABS"], types),
	)


def ext(operands: Dict[str, Operand], signed: bool, width: int):
	"""[S,Z]ext(rs1[width-1:0])\n
	This operation disregards the operands width and sign specified in the yaml file"""
	rs1 = operands["rs1"].to_metamodel_ref("rs1", cast=False)
	rs1_slice = behav.SliceOperation(
		rs1, behav.IntLiteral(width - 1), behav.IntLiteral(0)
	)
	sign = arch.DataType.S if signed else arch.DataType.U

	legalization = GMIRLegalization(
		name=["G_SEXT" if signed else "G_ZEXT"], types=["s" + str(width)]
	)

	return (behav.TypeConv(sign, None, rs1_slice), legalization)


# TODO add Clip
OPS: OpcodeDict = {
	"abs": partial(mm_abs),
	"slet": partial(slet),
	"min": partial(min_max, operator="<"),
	"max": partial(min_max, operator=">"),
	"mini": partial(min_max_immediate, operator="<"),
	"maxi": partial(min_max_immediate, operator=">"),
	"exths": partial(ext, signed=True, width=16),
	"exthz": partial(ext, signed=False, width=16),
	"extbs": partial(ext, signed=True, width=8),
	"extbz": partial(ext, signed=False, width=8),
	"addN": partial(arithmetic_n, operator="+"),
	"subN": partial(arithmetic_n, operator="-"),
	"addRN": partial(arithmetic_rn, operator="+"),
	"subRN": partial(arithmetic_rn, operator="-"),
	"addNr": partial(arithmetic_nr, operator="+"),
	"subNr": partial(arithmetic_nr, operator="-"),
	"addRNr": partial(arithmetic_rnr, operator="+"),
	"subRNr": partial(arithmetic_rnr, operator="-"),
	"add": partial(binary_op, operator="+"),
	"addI": partial(alu_imm, operator="+"),
}
