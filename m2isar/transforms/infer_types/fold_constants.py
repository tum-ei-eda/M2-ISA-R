"""Fold typed constant expressions and shrink their inferred result widths."""

from functools import singledispatchmethod
import logging

from m2isar.metamodel import arch, behav, type_info
from m2isar.metamodel.utils.ExprMutator import ExprMutator
from ..validate_behav.constants import INDETERMINATE, constant_value


class ConstantFolder(ExprMutator):
    """Fold constant operations after type inference has annotated the tree.

    Literal widths and explicit conversions are preserved. Only operation results
    are eligible for shrinking, so source type declarations remain meaningful.
    """

    def __init__(self, warn_shift_overflow=True):
        self.warn_shift_overflow = warn_shift_overflow

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context=None):
        return self.default_visit(expr, context)

    def _fold(self, expr):
        if not isinstance(expr.ty, type_info.PrimitiveType) or not expr.ty.kind.is_int:
            return expr
        try:
            # Explicit casts define the operand width of expressions such as
            # ``(unsigned<32>)1 << 31``. Evaluate them while folding their
            # enclosing operation, but leave standalone TypeConv nodes intact
            # so the source conversion itself is preserved.
            value = constant_value(expr, allow_casts=True)
        except ZeroDivisionError:
            # Leave invalid constant expressions intact for the validator to
            # report with the normal source diagnostic.
            return expr
        if not isinstance(value, int) or value is INDETERMINATE:
            return expr

        # CDSL arithmetic is evaluated at the inferred operation width. Keep
        # the resulting bit pattern, then shrink only its representation.
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
        if (self.warn_shift_overflow and expr.op.value in ('<<', '>>')
                and isinstance(expr.right, behav.Literal)
                and isinstance(expr.left.ty, type_info.PrimitiveType)):
            width = arch.get_const_or_val(expr.left.ty.size)
            if context is not None and isinstance(width, int) and width <= expr.right.value:
                context.emit_warning(
                    f"Shift count overflow for {expr.op.value} operation ({expr.left.ty.size} vs. {expr.right.value})",
                    'shift-overflow', logger=logging.getLogger('infer_types'), line_info=expr.line_info)
        return self._fold(expr)

    @generate.register
    def _(self, expr: behav.UnaryOperation, context=None):
        expr = self.default_visit(expr, context)
        if expr.op.value in ('++', '--'):
            return expr
        return self._fold(expr)

