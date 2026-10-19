"""Integer/array type rules from the MINRES 2.0.21 source analyzer.

Unknown types are deferred, not treated as evidence of successful validation.
Composite types and intrinsic size evaluation still need their own providers.
"""
from dataclasses import dataclass


@dataclass(frozen=True, eq=False)
class DslType:
    kind: str
    width: int = None
    signed: bool = False
    element: 'DslType' = None
    count: int = None
    identity: int = None
    name: str = None

    def equality_key(self):
        # MINRES EnumType inherits CoreDslType's generated equality, which
        # compares only runtime class and bit size, not declaration/base type.
        if self.kind == 'enum':
            return self.kind, self.width
        if self.kind in ('struct', 'union'):
            return self.kind, self.identity
        return self.kind, self.width, self.signed, self.element, self.count, self.identity

    def __eq__(self, other):
        if not isinstance(other, DslType):
            return NotImplemented
        return self.equality_key() == other.equality_key()

    def __hash__(self):
        return hash(self.equality_key())

    @property
    def integer(self):
        return self.kind == 'integer' and self.width is not None

    @property
    def scalar(self):
        return self.integer

    def __str__(self):
        if self.kind == 'enum':
            return f'enum {self.name} ({self.element})'
        if self.kind in ('struct', 'union'):
            return f'{self.kind} {self.name}'
        if self.integer:
            return f'{"signed" if self.signed else "unsigned"}<{self.width}>'
        if self.kind in ('array', 'address'):
            return f'{self.element}[{self.count}]'
        return self.kind


UNKNOWN = DslType('unknown')
VOID = DslType('void')
BOOL = DslType('integer', 1)


def integer(width, signed=False):
    return UNKNOWN if width is None else DslType('integer', width, signed)


def common_integer(left, right):
    signed = left.signed or right.signed
    width = max(left.width + int(signed and not left.signed),
                right.width + int(signed and not right.signed))
    return integer(width, signed)


def convertible(source, target):
    if UNKNOWN in (source, target) or source == target:
        return True
    if source.kind == 'enum' and target.integer:
        return convertible(source.element, target)
    if source.integer and target.kind == 'enum':
        return convertible(source, target.element)
    if source.integer and target.integer:
        return (source.width <= target.width
                and not (source.signed and not target.signed)
                and not (not source.signed and target.signed and source.width == target.width))
    return False


def holds_value(ty, value):
    if ty.kind == 'enum':
        return holds_value(ty.element, value)
    if not ty.integer:
        return False
    # bit_length avoids constructing a gigantic 2**width for large DSL widths.
    if ty.signed:
        return (max(1, value.bit_length()) if value >= 0 else (~value).bit_length()) < ty.width
    return value >= 0 and value.bit_length() <= ty.width
