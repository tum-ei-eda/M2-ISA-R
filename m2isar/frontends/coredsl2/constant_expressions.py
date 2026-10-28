"""Evaluate a subset of release 2.0.21 constant expressions.

With no resolver the evaluator is literal-only. A caller may supply a scoped
ISA-parameter resolver; symbol legality and evaluation cycles belong to it.

A None result means evaluation needs elaboration/type information, or an
unsupported node. It is never proof that an expression is an invalid constant.
"""
import operator
import re

from .parser_gen import CoreDSL2Parser as P


def integer_literal(text):
    """Return value, bit size and signedness as IntegerValueConverter does."""
    text = re.sub(r'[uUlL]+$', '', text.replace('_', ''))
    if "'" in text:
        width, digits = text.split("'", 1)
        width = int(width)
        signed = digits.startswith('s')
        if signed:
            digits = digits[1:]
        value = int(digits[1:], {'b': 2, 'o': 8, 'd': 10, 'h': 16}[digits[0]])
        if width <= 0 or width > 2147483647 or value.bit_length() > width:
            raise ValueError(f'Value {value} does not fit into {width} bits')
        if signed and value.bit_length() == width:
            value -= 1 << width
        return value, width, signed
    if len(text) > 1 and text.startswith('0') and text[1] not in 'xXbB':
        value = int(text, 8)
    else:
        value = int(text, 0)
    return value, max(1, value.bit_length()), False


def integer_value(text):
    return integer_literal(text)[0]


BINARY = {
    '+': operator.add, '-': operator.sub, '*': operator.mul,
    '&': operator.and_, '|': operator.or_, '^': operator.xor,
    '==': operator.eq, '!=': operator.ne, '<': operator.lt,
    '>': operator.gt, '<=': operator.le, '>=': operator.ge,
}


def constant_value(ctx, resolve=None, unsupported=None):
    if isinstance(ctx, P.Primary_expressionContext):
        return constant_value(ctx.primary(), resolve, unsupported)
    if isinstance(ctx, P.Constant_expressionContext):
        return constant_value(ctx.const_expr, resolve, unsupported)
    if isinstance(ctx, P.ConstantContext):
        return constant_value(ctx.getChild(0), resolve, unsupported)
    if isinstance(ctx, P.Reference_expressionContext):
        return None if resolve is None else resolve(ctx)
    if isinstance(ctx, P.Integer_constantContext):
        return integer_value(ctx.value.text)
    if isinstance(ctx, P.Bool_constantContext):
        return int(ctx.getText() == 'true')
    if isinstance(ctx, P.Parens_expressionContext):
        return constant_value(ctx.expr, resolve, unsupported)
    if isinstance(ctx, P.Prefix_expressionContext):
        # The reference constant evaluator only supports unary minus.
        if ctx.prefix.text != '-':
            return None if unsupported is None else unsupported(ctx)
        value = constant_value(ctx.right, resolve, unsupported)
        return None if value is None else -value
    if isinstance(ctx, P.Binary_expressionContext):
        left, right = constant_value(ctx.left, resolve, unsupported), constant_value(ctx.right, resolve, unsupported)
        if left is None or right is None:
            return None
        operation = ctx.bop.text
        if operation in BINARY:
            return int(BINARY[operation](left, right))
        if operation == '/':
            if right == 0:
                raise ZeroDivisionError('Division by zero')
            # BigInteger division truncates toward zero, unlike Python //.
            value = abs(left) // abs(right)
            return -value if (left < 0) != (right < 0) else value
        if operation in ('<<', '>>'):
            # Defer enormous values rather than allocating an unbounded integer.
            if abs(right) > 100000:
                return None
            if operation == '>>':
                right = -right
            return left << right if right >= 0 else left >> -right
        # MINRES does not support %, &&, || in constant evaluation.
    return None if unsupported is None else unsupported(ctx)
