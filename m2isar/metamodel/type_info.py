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

from enum import Enum, auto
from typing import Any, Union


class TypeKind(Enum):
    TYPE_NONE = auto() # NumberLiteral with no type, e.g. 0 or 1
    TYPE_VOID = auto()
    TYPE_UINT = auto()
    TYPE_INT = auto()
    # TYPE_BOOL = auto() Expressed as unsigned<1>
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


class MemoryType:
    size : int

    def __init__(self, size: int):
        self.size = size


class FunctionType():
    size : int
    kind : TypeKind

    def __init__(self, size: int, kind: TypeKind):
        self.size = size
        self.kind = kind
