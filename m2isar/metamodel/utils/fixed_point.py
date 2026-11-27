# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R

"""ac_fixed's arithmetic rules for fixed-point types, and finding where a core uses them.

Two views of a fixed-point number exist:

* :class:`~m2isar.metamodel.type_info.FixedType` is the *metamodel type*: stored in
  the model (on registers, variables, literals, casts), read by backends, mutable,
  carrying the quantization and overflow modes, and possibly holding a still
  unresolved parameter as its size.
* :class:`FixedFormat` (this module) is a *working value* for the rules below: a
  frozen ``(width, int_bits, signed)`` of plain ints. :func:`fixed_format` makes one
  from a resolved FixedType *or* integer PrimitiveType (an integer of width W reads as
  ``fixed<W, W>``, as ac_fixed treats an ac_int), so a single rule set covers
  fixed/fixed, fixed/integer and integer/fixed operands. The modes play no part in
  the rules; :meth:`FixedFormat.to_type` turns a result back into a FixedType with
  the default modes, as ac_fixed gives operation results.
"""

from fractions import Fraction
from dataclasses import dataclass
from typing import Union

from .. import arch, behav, type_info


@dataclass(frozen=True)
class FixedFormat:
	"""Resolved ``(width, int_bits, signed)`` of an integer or fixed-point scalar: the working
	value of the rules in this module, never stored in the model (see the module docstring)."""
	width: int
	int_bits: int
	signed: bool

	@property
	def frac_bits(self):
		return self.width - self.int_bits

	def to_type(self) -> type_info.FixedType:
		"""The metamodel type of this format, with the default modes AC_TRN and AC_WRAP."""
		kind = type_info.TypeKind.FIXED if self.signed else type_info.TypeKind.UFIXED
		return type_info.FixedType(kind, self.width, self.int_bits)


def fixed_format(ty) -> Union[FixedFormat, None]:
	"""The fixed-point view of a scalar type with resolved sizes, None for anything else.

	An integer of width W reads as a fixed-point number with W integer bits,
	as ac_fixed treats an ac_int<W, S> operand.
	"""
	if isinstance(ty, type_info.FixedType) and isinstance(ty.size, int) and isinstance(ty.int_bits, int):
		return FixedFormat(ty.size, ty.int_bits, ty.signed)
	if isinstance(ty, type_info.PrimitiveType) and ty.kind.is_int and isinstance(ty.size, int):
		return FixedFormat(ty.size, ty.size, ty.kind == type_info.TypeKind.INT)
	return None


def fixed_result(op: str, left: FixedFormat, right: FixedFormat) -> FixedFormat:
	"""The exact result format of ``left op right`` for + - * /, by ac_fixed's rt<> rules."""
	if op == '*':
		return FixedFormat(left.width + right.width, left.int_bits + right.int_bits, left.signed or right.signed)
	if op == '/':
		return FixedFormat(left.width + max(right.frac_bits, 0) + right.signed,
			left.int_bits + right.frac_bits + right.signed, left.signed or right.signed)
	if op in ('+', '-'):
		common = fixed_common(left, right)
		return FixedFormat(common.width + 1, common.int_bits + 1, common.signed or op == '-')
	raise ValueError(f"no fixed-point result rule for operator {op}")


def fixed_common(left: FixedFormat, right: FixedFormat) -> FixedFormat:
	"""The narrowest format that holds every value of both ``left`` and ``right``."""
	int_bits = max(left.int_bits + (right.signed and not left.signed),
		right.int_bits + (left.signed and not right.signed))
	return FixedFormat(int_bits + max(left.frac_bits, right.frac_bits), int_bits, left.signed or right.signed)


def fixed_negate(operand: FixedFormat) -> FixedFormat:
	"""The result format of ``-operand``."""
	return FixedFormat(operand.width + 1, operand.int_bits + 1, True)


def fixed_convertible(source: FixedFormat, target: FixedFormat) -> bool:
	"""Whether every value of ``source`` is exactly representable in ``target``."""
	if source.signed and not target.signed:
		return False
	return (target.frac_bits >= source.frac_bits
		and source.int_bits + (target.signed and not source.signed) <= target.int_bits)


def fixed_holds_value(fmt: FixedFormat, value) -> bool:
	"""Whether the exact rational ``value`` (int or Fraction) is representable in ``fmt``."""
	scaled = Fraction(value) * Fraction(2) ** fmt.frac_bits
	if scaled.denominator != 1:
		return False
	if fmt.signed:
		return -(1 << (fmt.width - 1)) <= scaled.numerator < (1 << (fmt.width - 1))
	return 0 <= scaled.numerator < (1 << fmt.width)


def is_fixed(ty) -> bool:
	"""Whether ``ty`` is, or is an array of or pointer to, a fixed-point type."""
	while isinstance(ty, (type_info.ArrayType, type_info.PointerType)):
		ty = ty.element_type if isinstance(ty, type_info.ArrayType) else ty.ty
	return isinstance(ty, type_info.FixedType) or isinstance(ty, type_info.FunctionType) and ty.kind.is_fixed


def _behavior_uses_fixed(node) -> bool:
	if isinstance(node, (list, tuple)):
		return any(_behavior_uses_fixed(item) for item in node)
	if not isinstance(node, behav.BaseNode):
		return False
	if is_fixed(getattr(node, 'ty', None)):
		return True
	if isinstance(node, behav.TypeConv) and node.data_type.is_fixed:
		return True
	if isinstance(node, behav.VarDefinition) and is_fixed(node.var.ty):
		return True
	return any(_behavior_uses_fixed(value) for value in vars(node).values())


def fixed_point_uses(core: arch.CoreDef) -> "list[str]":
	"""Names of the core's registers, functions, instructions and always blocks that use a fixed-point type."""
	uses = [f"register {name}" for name, reg in core.register_banks.items() if is_fixed(reg.ty)]
	for name, function in core.functions.items():
		if (is_fixed(function.ty) or any(is_fixed(arg.ty) for arg in function.args.values())
				or _behavior_uses_fixed(function.operation)):
			uses.append(f"function {name}")
	for instruction in core.instructions.values():
		if _behavior_uses_fixed(instruction.operation):
			uses.append(f"instruction {instruction.name}")
	for name, block in core.always_blocks.items():
		if _behavior_uses_fixed(block.operation):
			uses.append(f"always block {name}")
	return uses
