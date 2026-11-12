"""Fold typed constant expressions and shrink their inferred result widths."""

from functools import singledispatchmethod

from m2isar.metamodel import arch, behav, type_info
from m2isar.metamodel.utils.ExprMutator import ExprMutator
from ..validate_behav.constants import INDETERMINATE, constant_value


class ConstantFolder(ExprMutator):
    """Fold constant operations after type inference has annotated the tree.

    Literal widths and explicit conversions are preserved. Only operation results
    are eligible for shrinking, so source type declarations remain meaningful.
    """

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context=None):
        return self.default_visit(expr, context)

    def _fold(self, expr):
        if not isinstance(expr.ty, type_info.PrimitiveType) or not expr.ty.kind.is_int:
            return expr
        try:
            value = constant_value(expr)
        except ZeroDivisionError:
            # Leave invalid constant expressions intact for the validator to
            # report with the normal source diagnostic.
            return expr
        if not isinstance(value, int) or value is INDETERMINATE:
            return expr

        # Respect the inferred operation width before shrinking. This preserves
        # finite-width behavior for bitwise and shift operations.
        width = arch.get_const_or_val(expr.ty.size)
        if not isinstance(width, int) or width <= 0:
            return expr
        if expr.ty.kind == type_info.TypeKind.UINT:
            value %= 1 << width
            size = behav.required_bits(value)
        else:
            value %= 1 << width
            if value >= (1 << (width - 1)):
                value -= 1 << width
            size = behav.required_bits(value, signed=True)
        ty = type_info.PrimitiveType(expr.ty.kind, size)
        return behav.Literal(value, ty, line_info=expr.line_info)

    @generate.register
    def _(self, expr: behav.BinaryOperation, context=None):
        expr = self.default_visit(expr, context)
        return self._fold(expr)

    @generate.register
    def _(self, expr: behav.UnaryOperation, context=None):
        expr = self.default_visit(expr, context)
        if expr.op.value in ('++', '--'):
            return expr
        return self._fold(expr)

