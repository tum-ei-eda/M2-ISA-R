"""SIMD ALU instructions of the core v extension"""

from functools import partial
from typing import Callable, Dict
from m2isar.m2isar.metamodel import arch, behav as mm


def binary_op(
    operands: Dict[str, mm.IndexedReference], operator: str
) -> mm.BinaryOperation:
    """rs1 {operator} rs2"""
    return mm.BinaryOperation(operands["rs1"], mm.Operator(operator), operands["rs2"])


def simd_arithmetics(
    operands: Dict[str, mm.IndexedReference], operator: str
) -> mm.BaseNode:
    target = []
    return mm.Operation(
        [
            mm.Assignment(target[index], binary_op(operands, operator))
            for index in range(4)
            # TODO index depends on the size of the operands(4x8/2x16)
        ]
    )


OPS: Dict[str, Callable[[Dict[str, mm.IndexedReference]], mm.BaseNode]] = {
    "simd_sub": partial(simd_arithmetics, operator="-"),
    "simd_add": partial(simd_arithmetics, operator="+"),
}
