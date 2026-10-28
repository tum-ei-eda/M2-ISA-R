"""Pure evaluation of the release's integer constant subset in model nodes."""
import operator

from ...metamodel import arch, behav, type_info

INDETERMINATE = object()
BINARY = {'+': operator.add, '-': operator.sub, '*': operator.mul,
          '&': operator.and_, '|': operator.or_, '^': operator.xor,
          '==': operator.eq, '!=': operator.ne, '<': operator.lt,
          '<=': operator.le, '>': operator.gt, '>=': operator.ge}


def constant_value(node, active=frozenset(), on_error=None):
    if isinstance(node, arch.Parameter):
        if id(node) in active or node._value is None:
            return INDETERMINATE
        if isinstance(node._value, int):
            return node._value
        return constant_value(node._value, active | {id(node)}, on_error)
    if isinstance(node, behav.Literal):
        if isinstance(node.ty, type_info.PrimitiveType) and node.ty.kind.is_int:
            return int(node.value)
    if isinstance(node, behav.NamedReference) and isinstance(node.reference, arch.Parameter):
        return constant_value(node.reference, active, on_error)
    if isinstance(node, behav.Group):
        return constant_value(node.expr, active, on_error)
    if isinstance(node, behav.UnaryOperation) and node.op.value == '-':
        value = constant_value(node.right, active, on_error)
        return value if value is None or value is INDETERMINATE else -value
    if isinstance(node, behav.BinaryOperation):
        op = node.op.value
        left, right = constant_value(node.left, active, on_error), constant_value(node.right, active, on_error)
        if left is None or right is None:
            return None
        if left is INDETERMINATE or right is INDETERMINATE:
            return INDETERMINATE
        if op not in BINARY and op not in ('/', '<<', '>>'):
            return None
        if op in BINARY:
            return int(BINARY[op](left, right))
        if op == '/':
            if right == 0:
                error = ZeroDivisionError('Division by zero')
                if on_error is not None:
                    on_error(node, error)
                    return None
                raise error
            value = abs(left) // abs(right)
            return -value if (left < 0) != (right < 0) else value
        if abs(right) > 100000:
            return None
        shift = -right if op == '>>' else right
        return left << shift if shift >= 0 else left >> -shift
    return None


def holds_value(ty, value):
    width = arch.get_const_or_val(ty.size)
    if ty.kind == type_info.TypeKind.INT:
        return (max(1, value.bit_length()) if value >= 0 else (~value).bit_length()) < width
    return value >= 0 and value.bit_length() <= width


def range_size(start, end, suppress_errors=True, on_error=None):
    def evaluate(node):
        try:
            return constant_value(node, on_error=on_error)
        except ZeroDivisionError as error:
            if on_error is not None:
                on_error(node, error)
            elif not suppress_errors:
                raise
            return None

    if isinstance(start, behav.NamedReference) and isinstance(end, behav.NamedReference):
        return 1 if start.reference is end.reference else None
    if ((isinstance(start, behav.NamedReference) and isinstance(end, behav.BinaryOperation))
            or (isinstance(end, behav.NamedReference) and isinstance(start, behav.BinaryOperation))):
        reference, infix = (start, end) if isinstance(start, behav.NamedReference) else (end, start)
        if (infix.op.value in ('+', '-') and isinstance(infix.left, behav.NamedReference)
                and infix.left.reference is reference.reference):
            difference = evaluate(infix.right)
            return abs(difference) + 1 if isinstance(difference, int) else None
        return None
    first, last = evaluate(start), evaluate(end)
    return abs(last - first) + 1 if isinstance(first, int) and isinstance(last, int) else None

