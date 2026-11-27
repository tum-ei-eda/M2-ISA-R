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

from copy import deepcopy
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
    FIXED = auto()  # signed binary fixed point, see FixedType
    UFIXED = auto()  # unsigned binary fixed point, see FixedType

    @property
    def is_int(self):
        return self in (TypeKind.INT, TypeKind.UINT)

    @property
    def is_fixed(self):
        return self in (TypeKind.FIXED, TypeKind.UFIXED)

    @property
    def is_signed(self):
        return self in (TypeKind.INT, TypeKind.FIXED)

    @property
    def is_numeric(self):
        return self in (TypeKind.INT, TypeKind.UINT, TypeKind.FLOAT, TypeKind.FIXED, TypeKind.UFIXED)

    @property
    def is_void(self):
        return self == TypeKind.VOID

    @property
    def is_scalar(self):
        return self in (TypeKind.INT, TypeKind.UINT, TypeKind.CHAR, TypeKind.FLOAT, TypeKind.FIXED, TypeKind.UFIXED)

    @property
    def is_literal(self):
        return self is not (TypeKind.VOID, TypeKind.NONE)


class PrimitiveType:
    def __init__(self, kind: TypeKind, size: int):
        self.kind = kind
        self.size = size

    def __str__(self):
        return f"{self.kind.name}<{self.size}>"


class BitFieldType:
    def __init__(self, kind: TypeKind):
        self.kind = kind

    def __str__(self):
        return f"BITFIELD<{self.kind.name}>"


class FloatType:
    def __init__(self, exponent: int, mantissa: int, size: int):
        self.exponent = exponent
        self.mantissa = mantissa
        self.size = size

    def __str__(self):
        return f"FLOAT<e{self.exponent}m{self.mantissa}s{self.size}>"


class QuantizationMode(Enum):
    """ac_fixed's ac_q_mode: how a conversion drops fraction bits."""
    AC_TRN = auto()  # towards minus infinity
    AC_RND = auto()  # to nearest, ties towards plus infinity
    AC_TRN_ZERO = auto()  # towards zero
    AC_RND_ZERO = auto()  # to nearest, ties towards zero
    AC_RND_INF = auto()  # to nearest, ties away from zero
    AC_RND_MIN_INF = auto()  # to nearest, ties towards minus infinity
    AC_RND_CONV = auto()  # to nearest, ties to even
    AC_RND_CONV_ODD = auto()  # to nearest, ties to odd


class OverflowMode(Enum):
    """ac_fixed's ac_o_mode: how a conversion handles a value outside the target range."""
    AC_WRAP = auto()  # drop the high bits
    AC_SAT = auto()  # saturate to the minimum or maximum
    AC_SAT_ZERO = auto()  # set to zero
    AC_SAT_SYM = auto()  # saturate symmetrically, to -maximum or maximum


class FixedType:
    """A binary fixed-point number like ``ac_fixed<W, I, S, Q, O>``: ``size`` bits, of
    which ``int_bits`` lie in front of the binary point, two's complement when ``kind``
    is FIXED.

    The stored bits are an integer ``n`` (signed or unsigned, like ``signed<W>`` or
    ``unsigned<W>``) and the value is ``n * 2**-(W - I)``: the ``W - I`` fraction bits
    lie behind the binary point. For example ``fixed<8, 3, true>``, with 3 integer bits
    (the sign bit among them) and 5 fraction bits, weighs its bits as::

        weight  -4   2   1  .  1/2  1/4  1/8  1/16  1/32
        bit      s   i   i  .   f    f    f    f     f

        0b011_01000  =       2 + 1 + 1/4                    =  3.25
        0b111_11000  =  -4 + 2 + 1 + 1/2 + 1/4              = -0.25
        0b100_00000  =  -4                                  = -4.0      (the minimum)
        0b011_11111  =       2 + 1 + 1/2 + ... + 1/32       =  3.96875  (the maximum)

    so it covers ``-2**(I-1) .. 2**(I-1) - 2**-(W-I) = -4.0 .. 3.96875`` in steps of
    ``2**-(W-I) = 1/32``. The unsigned ``fixed<8, 3, false>`` weighs its top bit ``+4``
    instead of ``-4`` and covers ``0 .. 2**I - 2**-(W-I) = 0 .. 7.96875``.

    ``int_bits`` may be negative or exceed ``size``, which places the binary point
    outside the stored bits. ``q_mode`` and ``o_mode`` say how a value converted into
    this type (assigned, initialized or cast) is rounded and kept in range; the
    results of arithmetic operations use the defaults AC_TRN and AC_WRAP, as in ac_fixed.

    This is the type stored in the model. The arithmetic rules work on resolved
    :class:`~m2isar.metamodel.utils.fixed_point.FixedFormat` values instead, which
    integers map to as well; see :mod:`m2isar.metamodel.utils.fixed_point`.
    """

    def __init__(self, kind: TypeKind, size: int, int_bits: int,
                 q_mode: QuantizationMode = QuantizationMode.AC_TRN, o_mode: OverflowMode = OverflowMode.AC_WRAP):
        assert kind.is_fixed
        self.kind = kind
        self.size = size
        self.int_bits = int_bits
        self.q_mode = q_mode
        self.o_mode = o_mode

    @property
    def signed(self):
        return self.kind == TypeKind.FIXED

    @property
    def frac_bits(self):
        return self.size - self.int_bits

    def _modes(self):
        """The trailing template arguments that differ from their defaults."""
        if self.o_mode != OverflowMode.AC_WRAP:
            return [self.q_mode.name, self.o_mode.name]
        return [self.q_mode.name] if self.q_mode != QuantizationMode.AC_TRN else []

    def source_name(self):
        """The CoreDSL spelling, with default template arguments left out."""
        arguments = [str(self.size), str(self.int_bits)]
        modes = self._modes()
        if modes or not self.signed:
            arguments.append("true" if self.signed else "false")
        return f"fixed<{', '.join(arguments + modes)}>"

    def __str__(self):
        return f"{self.kind.name}<{','.join([str(self.size), str(self.int_bits)] + self._modes())}>"


class ArrayType:
    def __init__(self, element_type: Union[PrimitiveType, FloatType, FixedType], length: int):
        self.element_type: Union[PrimitiveType, FloatType, FixedType] = element_type
        self.length = length  # allow shaped later or TYPE_ARRAY in element_type?

    def __str__(self):
        return f"ARRAY<{self.element_type}, {self.length}>"


@dataclass
class CompositeField:
    name: str
    ty: Any  # metamodel type of the field
    size: int  # bit size
    offset: int  # bit offset from the start of the composite, always 0 in a union


class CompositeType:
    """Common base of struct and union types. Fields are kept in declaration order."""
    keyword = None

    def __init__(self, name: str, fields: "list[CompositeField]"):
        self.name = name
        self.fields = fields

    @property
    def size(self):
        raise NotImplementedError

    def field(self, name: str) -> Union[CompositeField, None]:
        return next((field for field in self.fields if field.name == name), None)

    def __str__(self):
        return f"{self.keyword}<{self.name}>"


class StructType(CompositeType):
    keyword = "STRUCT"

    def __init__(self, name: str, fields: "list[tuple[str, Any, int]]"):
        """Lay out (name, type, bit size) members one after another."""
        laid_out, offset = [], 0
        for field_name, ty, size in fields:
            laid_out.append(CompositeField(field_name, ty, size, offset))
            offset += size
        super().__init__(name, laid_out)

    @property
    def size(self):
        return sum(field.size for field in self.fields)


class UnionType(CompositeType):
    keyword = "UNION"

    def __init__(self, name: str, fields: "list[tuple[str, Any, int]]"):
        """Overlay (name, type, bit size) members at offset 0."""
        super().__init__(name, [CompositeField(field_name, ty, size, 0) for field_name, ty, size in fields])

    @property
    def size(self):
        return max((field.size for field in self.fields), default=0)


@dataclass
class PointerType:
    ty: Union[PrimitiveType, FloatType, ArrayType]

    def __str__(self):
        return f"POINTER<{self.ty}>"


class FunctionType:
    size: int
    kind: TypeKind
    fixed_type: Union[FixedType, None] = None  # the declared return type, if fixed point

    def __init__(self, size: int, kind: TypeKind, fixed_type: Union[FixedType, None] = None):
        self.size = size
        self.kind = kind
        self.fixed_type = fixed_type

    @property
    def return_type(self):
        """The scalar type a call returns, None for a void function."""
        if self.kind.is_void:
            return None
        return deepcopy(self.fixed_type) if self.fixed_type is not None else PrimitiveType(self.kind, self.size)

    def __str__(self):
        return f"FUNCTION<{self.kind.name} {self.size}>"
