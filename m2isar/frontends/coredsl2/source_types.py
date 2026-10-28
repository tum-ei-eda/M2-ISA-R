"""Integer/array type rules from the MINRES 2.0.21 source analyzer.

Unknown types are deferred, not treated as evidence of successful validation.
Composite types and intrinsic size evaluation still need their own providers.
"""
from dataclasses import dataclass
from typing import Union

from ...metamodel import type_info

MetaType = Union[type_info.PrimitiveType, type_info.ArrayType, type_info.PointerType, type_info.CompositeType]


@dataclass(frozen=True, eq=False)
class DslType:
    """Source validator view of a CoreDSL type, built around a metamodel type.

    Every known type is backed by ``meta`` and reads its width, signedness and
    count from it; an address is a pointer to its array and a struct/union is a
    metamodel composite type. Enums are a frontend-only concept: their ``meta``
    is the base integer type and their members live in ``members``.
    Sizes inside ``meta`` are always resolved ints. Only unknown types have no
    metamodel equivalent.
    """
    kind: str
    meta: MetaType = None
    element: 'DslType' = None  # array/address element or enum base type
    identity: int = None
    name: str = None
    members: dict = None  # enum member name -> value, in declaration order

    @property
    def width(self):
        if self.kind in ('integer', 'enum', 'struct', 'union'):
            # An enum over an unresolved base has no metamodel type.
            return None if self.meta is None else self.meta.size
        return None

    @property
    def signed(self):
        return self.kind == 'integer' and self.meta.kind == type_info.TypeKind.INT

    @property
    def count(self):
        if self.kind == 'array':
            return self.meta.length
        if self.kind == 'address':
            return self.meta.ty.length
        return None

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
VOID = DslType('void', type_info.PrimitiveType(type_info.TypeKind.VOID, 0))


def integer(width, signed=False):
    if width is None:
        return UNKNOWN
    return DslType('integer', type_info.PrimitiveType(type_info.TypeKind.INT if signed else type_info.TypeKind.UINT, width))


BOOL = integer(1)


def array(element, count):
    # An unknown element has no metamodel type and leaves element_type empty;
    # the DslType element stays authoritative.
    return DslType('array', type_info.ArrayType(element.meta, count), element=element)


def address(element, count):
    return DslType('address', type_info.PointerType(type_info.ArrayType(element.meta, count)), element=element)


def enum(base, members=None, identity=None, name=None):
    """Build an enum over integer ``base`` from a member name -> value mapping."""
    return DslType('enum', base.meta, element=base, identity=identity, name=name, members=dict(members or {}))


def composite(kind, fields, identity, name):
    """Build a struct/union from (name, DslType, bit size) members in declaration order."""
    meta_class = type_info.StructType if kind == 'struct' else type_info.UnionType
    meta = meta_class(name, [(field_name, ty.meta, size) for field_name, ty, size in fields])
    return DslType(kind, meta, identity=identity, name=name)


def from_meta(ty, resolve=lambda value: value):
    """Wrap a metamodel type, using ``resolve`` to turn parameter or expression sizes into ints."""
    if isinstance(ty, type_info.PrimitiveType):
        if ty.kind == type_info.TypeKind.VOID:
            return VOID
        if not ty.kind.is_int:
            return UNKNOWN
        width = resolve(ty.size)
        if width is None:
            return UNKNOWN
        return DslType('integer', ty if isinstance(ty.size, int) else type_info.PrimitiveType(ty.kind, width))
    if isinstance(ty, type_info.ArrayType):
        return array(from_meta(ty.element_type, resolve), resolve(ty.length))
    return UNKNOWN


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
