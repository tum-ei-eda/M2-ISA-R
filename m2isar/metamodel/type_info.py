# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026
# Chair of Embedded Computing Systems
# Technical University of Vienna

"""This module contains helper data_type classes for modeling Symbol and data types
for the architectural part of an M2-ISA-R model. The architectural part is
anything but the functional behavior of functions and instructions.
"""

from enum import Enum, IntEnum, auto
from typing import Any, Union


class TypeKind(Enum):
    TYPE_NONE = auto() # NumberLiteral with no type, e.g. 0 or 1
    TYPE_VOID = auto()
    TYPE_UINT = auto()
    TYPE_INT = auto()
    TYPE_BOOL = auto()
    TYPE_FLOAT = auto()
    TYPE_STR = auto()
    TYPE_ARRAY = auto()

class PrimitiveType:
    def __init__(self, kind: TypeKind, size: int):
        self.kind = kind
        self.size = size

class BitFieldType():
    def __init__(self, kind: TypeKind):
        self.kind = kind

#removed get_const_or_val
class IntegerType(PrimitiveType):
    def __init__(self, size: int, signed: bool, ptr: Any=None):
        self.ptr = ptr
        super().__init__(TypeKind.TYPE_INT if signed else TypeKind.TYPE_UINT, size)



class FloatType:
    def __init__(self, exponent: int, mantissa: int, size: int):
        self.exponent = exponent
        self.mantissa = mantissa
        self.size = size

class ArrayType:
    def __init__(self, element_type : Union[PrimitiveType, FloatType], length: int):
        self.element_kind : Union[PrimitiveType, FloatType] = element_type
        self.length = length # allow shaped later or TYPE_ARRAY in element_type?


class MemoryAttribute(Enum):
	IS_PC = auto()
	IS_MAIN_MEM = auto()
	IS_MAIN_REG = auto()
	DELETE = auto()
	ETISS_CAN_FAIL = auto()
	ETISS_IS_GLOBAL_IRQ_EN = auto()
	ETISS_IS_IRQ_EN = auto()
	ETISS_IS_IRQ_PENDING = auto()
	ETISS_IS_PROCNO = auto()


class MemoryType:
    size : int

    def __init__(self, size: int):
        self.size = size


class FunctionAttribute(Enum):
	ETISS_STATICFN = auto()
	ETISS_NEEDS_ARCH = auto()
	ETISS_TRAP_ENTRY_FN = auto()
	ETISS_TRAP_TRANSLATE_FN = auto()

class FunctionThrows(IntEnum):
	NO = 0
	YES = 1
	MAYBE = 2

class FunctionType():
    size : int
    kind : TypeKind

    def __init__(self, size: int, kind: TypeKind):
        self.size = size
        self.kind = kind

class ConstAttribute(Enum):
	IS_REG_WIDTH = auto()
	IS_ADDR_WIDTH = auto()

class InstrAttribute(Enum):
	NO_CONT = auto()
	COND = auto()
	FLUSH = auto()
	SIM_EXIT = auto()
	ENABLE = auto()
	ETISS_ERROR_INSTRUCTION = auto()
