"""SIMD ALU instructions of the core v extension"""

from functools import partial
from typing import Callable, Dict, List, Union

from ....metamodel import arch, behav
from ..operands import Operand

XLEN = 32

def binary_op(
	operands: Dict[str, Operand], operator: str
) -> behav.BinaryOperation:
	"""rs1 {operator} rs2"""
	return behav.BinaryOperation(operands["rs1"].to_metemodel_ref("rs1"), behav.Operator(operator), operands["rs2"].to_metemodel_ref("rs2"))

# Simd ops can be modeled in 2 ways,
# 1.: A list of assignments for each of the lanes
# 2.: A Concatonation of the results

def simd_arithmetics(
	operands: Dict[str, Operand], operator: str
) -> List[behav.BaseNode]:
	"""rd[] = rs1[] {operator} rs2[]"""
	rd_slices = operands["rd"].to_simd_slices("rd")
	rs1_slices = operands["rs1"].to_simd_slices("rs1")
	rs2_slices = operands["rs2"].to_simd_slices("rs2")

	assingments = []
	for i, rd in enumerate(rd_slices):
		op = behav.BinaryOperation(rs1_slices[i], behav.Operator(operator), rs2_slices[i])
		assingments.append(behav.Assignment(rd, op))

	return assingments


OPS: Dict[str, Callable[[Dict[str, Operand]], Union[behav.BaseNode, List[behav.BaseNode]]]] = {
	"simd_sub": partial(simd_arithmetics, operator="-"),
	"simd_add": partial(simd_arithmetics, operator="+"),
}
