# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2026
# Chair of Embedded Computing Systems
# Technical University of Wien

"""Infer missing instruction operand declarations from their behavior."""

import logging
from functools import singledispatchmethod

from ..metamodel import arch, attribute_info, behav, type_info
from ..metamodel.utils.ExprVisitor import ExprVisitor

logger = logging.getLogger("infer_operands")


class OperandAnalyzer(ExprVisitor):
    """Collect instruction fields and their usage from a behavior tree."""

    def __init__(self):
        self.uses = {}

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context=None):
        self.default_visit(expr, context or {"write": False, "register_index": False})

    def _record(self, reference, context):
        if not isinstance(reference, arch.BitFieldDescr):
            return

        use = self.uses.setdefault(
            reference.name,
            {"field": reference, "read": False, "write": False, "register": False, "immediate": False},
        )
        use["write" if context["write"] else "read"] = True
        use["register" if context["register_index"] else "immediate"] = True

    @generate.register
    def _(self, expr: behav.NamedReference, context=None):
        self._record(expr.reference, context or {"write": False, "register_index": False})

    @generate.register
    def _(self, expr: behav.Assignment, context=None):
        self.generate(expr.target, {"write": True, "register_index": False})
        self.generate(expr.expr, {"write": False, "register_index": False})

    @generate.register
    def _(self, expr: behav.IndexedReference, context=None):
        context = context or {"write": False, "register_index": False}
        self._record(expr.reference, context)
        self.generate(
            expr.index,
            {
                "write": context["write"],
                "register_index": _is_register(expr.reference),
            },
        )
        if expr.right is not None:
            self.generate(expr.right, {"write": False, "register_index": False})


def _is_register(reference):
    if isinstance(reference, (arch.Register, arch.RegisterBank)):
        return True
    return isinstance(reference, arch.Alias) and isinstance(reference.parent, (arch.Register, arch.RegisterBank))


def infer_operands(instruction: arch.Instruction):
    """Add behavior-referenced fields missing from an instruction's operands."""
    analyzer = OperandAnalyzer()
    analyzer.generate(instruction.operation)

    for name, use in analyzer.uses.items():
        field = instruction.fields.get(name)
        if field is None:
            continue

        operand = instruction.operands.get(name)
        if operand is None:
            attributes = {}
            if use["read"] and use["write"]:
                attributes[attribute_info.OperandAttribute.INOUT] = []
            elif use["read"]:
                attributes[attribute_info.OperandAttribute.IN] = []
            elif use["write"]:
                attributes[attribute_info.OperandAttribute.OUT] = []

            if use["register"] and not use["immediate"]:
                attributes[attribute_info.OperandAttribute.IS_REG] = []
            elif use["immediate"] and not use["register"]:
                attributes[attribute_info.OperandAttribute.IS_IMM] = []
            elif use["register"] and use["immediate"]:
                logger.warning(
                    "operand %s is used as both a register index and an immediate in instruction %s",
                    name,
                    instruction.name,
                )

            operand = arch.Parameter(
                name,
                None,
                attributes,
                field.ty.size,
                field.ty.kind == type_info.TypeKind.INT,
            )
            instruction.operands[name] = operand
        else:
            if operand.size != field.ty.size:
                logger.warning(
                    "operand %s in instruction %s has declared width %s but behavior uses width %s",
                    name,
                    instruction.name,
                    operand.size,
                    field.ty.size,
                )
            field.ty.kind = type_info.TypeKind.INT if operand.signed else type_info.TypeKind.UINT

    for name in instruction.operands.keys() - analyzer.uses.keys():
        logger.warning("operand %s is not referenced by behavior of instruction %s", name, instruction.name)

    return instruction
