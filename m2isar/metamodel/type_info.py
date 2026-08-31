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
    NONE = auto()  # NumberLiteral with no type, e.g. 0 or 1
    AUTO = auto()  # detect automatically
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

    @property
    def is_literal(self):
        return self is not (TypeKind.VOID, TypeKind.NONE)


class PrimitiveType:
    def __init__(self, kind: TypeKind, size: int):
        self.kind = kind
        self.size = size
    def __str__(self):
        return f"{self.kind.name}<{self.size}>"

class BitFieldType():
    def __init__(self, kind: TypeKind):
        self.kind = kind
    def __str__(self):
        return f"BITFIELD<{self.kind.name}>"

class FloatType:
    def __init__(self, exponent: int, mantissa: int, size: int):
        self.exponent = exponent
        self.mantissa = mantissa
        self.size = size
    def __str__(self):        return f"FLOAT<e{self.exponent}m{self.mantissa}s{self.size}>"

class ArrayType:
    def __init__(self, element_type : Union[PrimitiveType, FloatType], length: int):
        self.element_type : Union[PrimitiveType, FloatType] = element_type
        self.length = length # allow shaped later or TYPE_ARRAY in element_type?
    def __str__(self):
        return f"ARRAY<{self.element_type}, {self.length}>"

@dataclass
class PointerType:
    ty: Union[PrimitiveType, FloatType, ArrayType]
    def __str__(self):
        return f"POINTER<{self.ty}>"

class FunctionType():
    size : int
    kind : TypeKind

    def __init__(self, size: int, kind: TypeKind):
        self.size = size
        self.kind = kind

    def __str__(self):
        return f"FUNCTION<{self.kind.name} {self.size}>"
