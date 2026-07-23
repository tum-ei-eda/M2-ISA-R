# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026
# Chair of Embedded Computing Systems
# Technical University of Vienna

from typing import Union

from m2isar.metamodel import arch, behav, type_info
from m2isar import M2TypeError


def type_shape_is_equal(lhs_type : Union[type_info.PrimitiveType, type_info.ArrayType], rhs_type : Union[type_info.PrimitiveType, type_info.ArrayType]):
    if isinstance(lhs_type, type_info.ArrayType) and isinstance(rhs_type, type_info.ArrayType):
        return type_shape_is_equal(lhs_type.element_type, rhs_type.element_type) and arch.get_const_or_val(lhs_type.length) == arch.get_const_or_val(rhs_type.length)
    elif isinstance(lhs_type, type_info.PrimitiveType) and isinstance(rhs_type, type_info.PrimitiveType):
        return lhs_type.kind == rhs_type.kind and lhs_type.size == rhs_type.size
    else:
        raise M2TypeError(f"Cannot compare types of different dimensions: {lhs_type} and {rhs_type}")


def shape_compare(lhs_type : Union[type_info.PrimitiveType, type_info.ArrayType], rhs_type : Union[type_info.PrimitiveType, type_info.ArrayType], space_ship_op: callable):
    if isinstance(lhs_type, type_info.ArrayType) and isinstance(rhs_type, type_info.ArrayType):
        if space_ship_op(arch.get_const_or_val(lhs_type.length), arch.get_const_or_val(rhs_type.length)):
            return True
        else:
            return shape_compare(lhs_type.element_type, rhs_type.element_type, space_ship_op)
    elif isinstance(lhs_type, type_info.PrimitiveType) and isinstance(rhs_type, type_info.PrimitiveType):
        return space_ship_op(arch.get_const_or_val(lhs_type.size), arch.get_const_or_val(rhs_type.size))
    else:
        raise M2TypeError(f"Cannot compare types of different dimension: {lhs_type} and {rhs_type}")


def measure_dimensions(lhs_type : Union[type_info.PrimitiveType, type_info.ArrayType]):
    if isinstance(lhs_type, type_info.ArrayType):
        return measure_dimensions(lhs_type.element_type) + 1
    else:
        return 0


def measure_dim_difference(lhs_type: Union[type_info.PrimitiveType, type_info.ArrayType], rhs_type: Union[type_info.PrimitiveType, type_info.ArrayType]):
    lhs_dims = measure_dimensions(lhs_type)
    rhs_dims = measure_dimensions(rhs_type)
    return abs(lhs_dims - rhs_dims)


def get_innermost_element_type(top_level_type : Union[type_info.PrimitiveType, type_info.ArrayType]):
    if isinstance(top_level_type, type_info.ArrayType):
        return get_innermost_element_type(top_level_type.element_type)
    else:
        assert isinstance(top_level_type, type_info.PrimitiveType)
        return top_level_type


def compare_innermost_element_type(lhs_type : Union[type_info.PrimitiveType, type_info.ArrayType], rhs_type : Union[type_info.PrimitiveType, type_info.ArrayType]):
    lhs_innermost = get_innermost_element_type(lhs_type)
    rhs_innermost = get_innermost_element_type(rhs_type)

    if not type_shape_is_equal(lhs_innermost, rhs_innermost):
        raise M2TypeError(f"Type mismatch: {lhs_innermost} and {rhs_innermost}")
    else:
        return True


# Deep-copies type of new tensor and updates innermost element type to given type (for literals, bitfields, floats)
def update_innermost_element_type(top_level_type : Union[type_info.PrimitiveType, type_info.ArrayType], innermost_type : type_info.PrimitiveType):
    if isinstance(top_level_type, type_info.ArrayType):
        top_level_type = type_info.ArrayType(get_innermost_element_type(top_level_type.element_type), top_level_type.length)
        if  isinstance(top_level_type.element_type, type_info.PrimitiveType):
            top_level_type.element_type = innermost_type
            return top_level_type
    else:
        assert isinstance(top_level_type, type_info.PrimitiveType)
        return innermost_type


# Simple expression evaluation for ranged mem indexes
def helper_expr_size(sub_expr: behav.BaseNode):
    expr = None
    if type(sub_expr) == behav.Group:
            expr = sub_expr.expr
            return helper_expr_size(expr)
    elif type(sub_expr) == behav.BinaryOperation:
            expr = sub_expr
            assert isinstance(expr.left, behav.NamedReference)

            if expr.op.value == "+":
                    if type(expr.right) == behav.Literal:
                            return int(expr.right.value)

            elif expr.op.value == "-":
                    if type(expr.right) == behav.Literal:
                            return (-1 * int(expr.right.value))
            else:
                    raise M2TypeError(f"Not supported Operation value Type {expr.op.value} within mem access range")

    elif type(sub_expr) == behav.NamedReference:
            return 0
    else:
            raise M2TypeError(f"Not supported expr Type {type(sub_expr)} within mem access range")
