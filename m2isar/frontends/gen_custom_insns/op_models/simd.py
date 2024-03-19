"""SIMD ALU instructions of the core v extension"""

from functools import partial
from typing import Dict, List
from enum import Enum, auto

from ....metamodel import arch, behav
from ..operands import Operand
from .template import OpcodeDict
from ..seal5_support import GMIRLegalization

# Simd ops can be modeled in 2 ways,
# 1.: A list of assignments for each of the lanes
# 2.: A Concatonation of the results


class SimdMode(Enum):
	"""Modes used by the Core V simd instructions (see https://cv32e40p.readthedocs.io/en/latest/instruction_set_extensions.html#simd)"""

	NORMAL = auto()
	SC = auto()
	SCI = auto()
	DIV = auto()


# TODO would need to be changed for XLEN 64
types_dict = {2: ["v2i16"], 4: ["v4i8"]}
# TODO this could be moved to seal5_support.py, just like the dict in alu_ops.py
op_dict = {"+": ["G_ADD"], "-": ["G_SUB"]}


def simd_arithmetics(
	operands: Dict[str, Operand],
	operator: str,
	mode: SimdMode = SimdMode.NORMAL,
	div: int = 0,
):
	"""rd[] = rs1[] {operator} rs2[]"""  # FIXME: update docstring for sc(i) and div
	rd_slices = operands["rd"].to_simd_slices("rd")
	rs1_slices = operands["rs1"].to_simd_slices("rs1")

	legalization = GMIRLegalization(op_dict[operator], types_dict[len(rd_slices)])

	assingments = []

	if mode == SimdMode.NORMAL:
		rs2_slices = operands["rs2"].to_simd_slices("rs2")
		for i, rd in enumerate(rd_slices):
			op = behav.BinaryOperation(
				rs1_slices[i], behav.Operator(operator), rs2_slices[i]
			)
			assingments.append(behav.Assignment(rd, op))

	if mode == SimdMode.DIV:
		rs2_slices = operands["rs2"].to_simd_slices("rs2")
		for i, rd in enumerate(rd_slices):
			op = behav.BinaryOperation(
				behav.BinaryOperation(
					rs1_slices[i], behav.Operator(operator), rs2_slices[i]
				),
				behav.Operator(">>"),
				behav.IntLiteral(div, signed=False),
			)
			assingments.append(behav.Assignment(rd, op))

	if mode == SimdMode.SC:
		rs2 = operands["rs2"]
		left_index = behav.IntLiteral(rs2.width - 1)
		right_index = behav.IntLiteral(0)
		rs2_slice = behav.SliceOperation(
			rs2.to_metamodel_ref("rs2"), left_index, right_index
		)
		for i, rd in enumerate(rd_slices):
			op = behav.BinaryOperation(
				rs1_slices[i], behav.Operator(operator), rs2_slice
			)
			assingments.append(behav.Assignment(rd, op))

	if mode == SimdMode.SCI:
		# TODO not sure how i want to implement the sci immediates
		# option 1: user needs to specify a operand["sci"] in which the size/datatype can be set
		try:
			sci = operands["sci"]
			sci_ref = behav.NamedReference(
				arch.BitFieldDescr(
					"sci",
					sci.width,
					arch.DataType.S if sci.sign == "s" else arch.DataType.U,
				)
			)
		except KeyError:
			# option 2: only offer a fixed immediate size
			sci_ref = behav.NamedReference(
				arch.BitFieldDescr("sci", 5, arch.DataType.S)
			)

		for i, rd in enumerate(rd_slices):
			op = behav.BinaryOperation(rs1_slices[i], behav.Operator(operator), sci_ref)
			assingments.append(behav.Assignment(rd, op))

	return (assingments, legalization)


OPS: OpcodeDict = {
	"simd_sub": partial(simd_arithmetics, operator="-"),
	"simd_add": partial(simd_arithmetics, operator="+"),
	"simd_add.sc": partial(simd_arithmetics, operator="+", mode=SimdMode.SC),
	"simd_add.sci": partial(simd_arithmetics, operator="+", mode=SimdMode.SCI),
	"simd_sub.div": partial(simd_arithmetics, operator="-", mode=SimdMode.DIV, div=2),
}