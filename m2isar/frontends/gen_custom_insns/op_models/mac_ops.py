"""Instructions from Core-V Mac"""

from functools import partial
from typing import Dict

from ....metamodel import behav
from ..operands import Operand, to_metamodel_operands
from .template import OpcodeDict


def mac(operands: Dict[str, Operand], operator: str = "+"):
	"""rd {operator} rs1 * rs2"""
	mm_operands = to_metamodel_operands(operands)

	return (
		behav.BinaryOperation(
			mm_operands["rd"],
			behav.Operator(operator),
			behav.BinaryOperation(
				mm_operands["rs1"],
				behav.Operator("*"),
				mm_operands["rs2"],
			),
		),
		None,
	)


def mul_n(operands: Dict[str, Operand], hh: bool, mac_mode: bool):
	"""((rs1[i] * rs2[i]) {+ rd, if mac_mode}) >> Is3, where i is 15:0 if hh is false, else 31:16"""
	index = 1 if hh else 0
	rs1 = operands["rs1"].to_simd_slices("rs1")[index]
	rs2 = operands["rs2"].to_simd_slices("rs2")[index]

	if mac_mode:
		lhs = behav.BinaryOperation(
			behav.BinaryOperation(rs1, behav.Operator("*"), rs2),
			behav.Operator("+"),
			operands["rd"].to_metamodel_ref("rd"),
		)
	else:
		lhs = behav.BinaryOperation(rs1, behav.Operator("*"), rs2)
	return (
		behav.BinaryOperation(
			lhs,
			behav.Operator(">>"),
			operands["Is3"].to_metamodel_ref("Is3"),
		),
		None,
	)


def mul_rn(operands: Dict[str, Operand], hh: bool, mac_mode: bool):
	"""((rs1[i] * rs2[i]) {+ rd, if mac_mode} + 2^(Is3-1)) >> Is3,  where i is 15:0 if hh is false, else 31:16"""
	index = 1 if hh else 0
	rs1 = operands["rs1"].to_simd_slices("rs1")[index]
	rs2 = operands["rs2"].to_simd_slices("rs2")[index]

	pow2_part = behav.BinaryOperation(
		behav.IntLiteral(2),
		behav.Operator("^"),
		behav.BinaryOperation(
			operands["Is3"].to_metamodel_ref("Is3"),
			behav.Operator("-"),
			behav.IntLiteral(1),
		),
	)

	if mac_mode:
		lhs = behav.BinaryOperation(
			behav.BinaryOperation(rs1, behav.Operator("*"), rs2),
			behav.Operator("+"),
			operands["rd"].to_metamodel_ref("rd"),
		)
	else:
		lhs = behav.BinaryOperation(rs1, behav.Operator("*"), rs2)

	return (
		behav.BinaryOperation(
			behav.BinaryOperation(
				lhs,
				behav.Operator("+"),
				pow2_part,
			),
			behav.Operator(">>"),
			operands["Is3"].to_metamodel_ref("Is3"),
		),
		None,
	)


OPS: OpcodeDict = {
	"mac": partial(mac, operator="+"),
	"msu": partial(mac, operator="-"),
	"mulN": partial(mul_n, hh=False, mac_mode=False),
	"mulhhN": partial(mul_n, hh=True, mac_mode=False),
	"mulRN": partial(mul_rn, hh=False, mac_mode=False),
	"mulhhRN": partial(mul_rn, hh=True, mac_mode=False),
	"macN": partial(mul_n, hh=False, mac_mode=True),
	"machhN": partial(mul_n, hh=True, mac_mode=True),
	"macRN": partial(mul_rn, hh=False, mac_mode=True),
	"machhRN": partial(mul_rn, hh=True, mac_mode=True),
}
