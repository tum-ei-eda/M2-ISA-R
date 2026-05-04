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

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Union
import logging

logger = logging.getLogger("type_info_logger")
class TypeKind(Enum):
    NONE = auto() # NumberLiteral with no type, e.g. 0 or 1
    VOID = auto()
    UINT = auto()
    INT = auto()
    CHAR = auto()
    # BOOL = auto() Expressed as unsigned<1>
    FLOAT = auto()
    STR = auto()

    @property
    def is_int(self):
        return self in (TypeKind.INT, TypeKind.UINT)

    @property
    def is_numeric(self):
        return self in (TypeKind.INT, TypeKind.UINT, TypeKind.FLOAT)

    @property
    def is_void(self):
        return self == TypeKind.VOID

    @property
    def is_scalar(self):
        return self in (TypeKind.INT, TypeKind.UINT, TypeKind.CHAR, TypeKind.FLOAT)


class PrimitiveType:
    def __init__(self, kind: TypeKind, size: int):
        self.kind = kind
        self.size = size

class BitFieldType():
    def __init__(self, kind: TypeKind):
        self.kind = kind


class FloatType:
    def __init__(self, exponent: int, mantissa: int, size: int):
        self.exponent = exponent
        self.mantissa = mantissa
        self.size = size

class ArrayType:
    def __init__(self, element_type : Union[PrimitiveType, FloatType], length: int):
        self.element_kind : Union[PrimitiveType, FloatType] = element_type
        self.length = length # allow shaped later or TYPE_ARRAY in element_type?

@dataclass
class PointerType:
    ty: PrimitiveType


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
