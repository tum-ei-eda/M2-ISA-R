# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

""" Deprecated module, only used for legacy reasons. Monkey patching can be avoided
by a custom ExprVisitor subclass and a custom generate function.
See :mod:`m2isar.metamodel.utils.ExprVisitor` for more details on how to do this.
This module contains classes for modeling the behavioral part
of an M2-ISA-R model, this means the functional behavior of functions
and instructions. Behavior is modeled as a tree of instances of the classes
in this module. This object tree can then be traversed with transformation
functions to generate code or transform the tree.

All classes in this module should inherit from :class:`BaseNode`, but never implement
the `generate` method here. This method is dynamically overwritten during runtime depending
on which translation module is loaded using :func:`patch_model`.
"""

from typing import TYPE_CHECKING, Union, Optional
from .type_info import PrimitiveType, TypeKind, ArrayType
import numpy as np

if TYPE_CHECKING:
	from .arch import (BitFieldDescr, Parameter, FnParam, Function, Intrinsic,
	                   Memory, Variable, RegisterBank)
	from .code_info import LineInfo

# pylint: disable=abstract-method

class BaseNode:
	"""The base class for all behavior model classes. Only implements an
	empty generate function which raises a :exc:`NotImplementedError` if it is
	not overridden."""

	def __init__(self, line_info: "LineInfo"=None) -> None:
		self.line_info = line_info
		self.ty = None

	def generate(self, context):
		raise NotImplementedError()

class CodeLiteral(BaseNode):
	def __init__(self, val, line_info=None) -> None:
		super().__init__(line_info)
		self.val = val

class Operator(BaseNode):
	"""Class representing an operator (of either a :class:`.UnaryOperation` or a
	:class:`.BinaryOperation`)."""

	def __init__(self, op: str, line_info=None):
		super().__init__(line_info)
		self.value = op

class Operation(BaseNode):
	"""Top-level collection class containing a list of actual operations."""

	def __init__(self, statements: "list[BaseNode]", line_info=None) -> None:
		super().__init__(line_info)
		self.statements = statements

class Block(Operation):
	"""A separated code block with optional behavioral attributes."""

	def __init__(self, statements: "list[BaseNode]", line_info=None, attributes=None, explicit_attributes=None) -> None:
		super().__init__(statements, line_info)
		self.attributes = attributes if attributes is not None else {}
		self.explicit_attributes = explicit_attributes if explicit_attributes is not None else set(self.attributes)

class BinaryOperation(BaseNode):
	"""A binary operation with a left-hand and a right-hand operand as well
	as an operator."""

	def __init__(self, left: BaseNode, op: Operator, right: BaseNode, line_info=None):
		super().__init__(line_info)
		self.left = left
		self.op = op
		self.right = right

class SliceOperation(BaseNode):
	"""A slicing operation for extracting bit runs from scalar values."""

	def __init__(self, expr: BaseNode, left: BaseNode, right: BaseNode, line_info=None):
		super().__init__(line_info)
		self.expr = expr
		self.left = left
		self.right = right

class ConcatOperation(BaseNode):
	"""A concatenating operation."""

	def __init__(self, left: BaseNode, right: BaseNode, line_info=None) -> None:
		super().__init__(line_info)
		self.left = left
		self.right = right


class Literal(BaseNode):
	def __init__(self, value:int, ty =  PrimitiveType(TypeKind.NONE, None), base: Optional[int]=10, line_info=None):
		super().__init__(line_info)

		#assert ty.kind.is_literal
		self._value: Union[int, str] = value
		self.ty = ty    # assigned during type checking

		#Optional type information (not always given)
		self.base:  Optional[int] = base   # 2, 10, 16

	def __repr__(self):
		return f"Literal(value={self.value}, type={self.ty}, base={self.base})"

	def __int__(self):
		if isinstance(self.value, int):
			return int(self.value, self.base)
		else:
			raise ValueError(f"Cannot convert {self.value} to int")

	# compile time constant
	@property
	def value(self) -> int:
		"""Returns the resolved value."""
		return self._value

### Diverted from Literals as every value needs to be a constant or not-initialized for now!!!
class Tensor(BaseNode):
	def __init__(self, value: list[int], ty = ArrayType(PrimitiveType(TypeKind.NONE, None), None), line_info=None):
		super().__init__(line_info)

		#assert ty.kind.is_literal
		self._value: np.ndarray = np.array(value)
		self.ty = ty    # assigned during type checking

	def __repr__(self):
		return f"Tensor(values={self.value}, type={self.ty})"

	# compile time constant
	@property
	def value(self) -> np.ndarray:
		"""Returns the resolved array."""
		return self._value


class Assignment(BaseNode):
	"""An assignment statement."""

	def __init__(self, target: BaseNode, expr: BaseNode, line_info=None):
		super().__init__(line_info)
		self.target = target
		self.expr = expr

class Conditional(BaseNode):
	"""A conditional statement with multiple conditions and statement blocks.

	Each statement block has a corresponding condition statement. The exception
	from this is the very last statement block, which when no corresponding
	condition is present is treated as an else statement.
	"""

	def __init__(self, conds: "list[BaseNode]", stmts: "list[BaseNode]", line_info=None):
		super().__init__(line_info)
		self.conds = conds
		self.stmts = stmts

class LoopBase(BaseNode):
	"""Common structural base for source and canonical loops.

	``init`` is executed once before the loop, ``updates`` at the loop latch,
	and ``post_test`` selects whether the condition is checked before or after
	the body. Source frontends should prefer one of the explicit loop classes.
	"""

	def __init__(self, cond: BaseNode, stmts: "list[BaseNode]", post_test: bool, line_info=None,
			init: "list[BaseNode]" = None, updates: "list[BaseNode]" = None):
		super().__init__(line_info)
		self.cond = cond
		self.stmts = stmts if stmts is not None else []
		self.post_test = post_test
		self.init = init if init is not None else []
		self.updates = updates if updates is not None else []

	@property
	def body(self):
		"""Return the loop body block."""
		return self.stmts[0] if len(self.stmts) == 1 and isinstance(self.stmts[0], Block) else Block(self.stmts)


class Loop(LoopBase):
	"""Canonical lowered loop representation."""


class ForLoop(LoopBase):
	"""Source-level ``for (init; cond; updates) body`` loop."""

	def __init__(self, init: "list[BaseNode]", cond: BaseNode,
			updates: "list[BaseNode]", body: Block, line_info=None):
		super().__init__(cond, [body], False, line_info, init=init, updates=updates)


class WhileLoop(LoopBase):
	"""Source-level pre-tested while loop."""

	def __init__(self, cond: BaseNode, body: Block, line_info=None):
		super().__init__(cond, [body], False, line_info)


class DoWhileLoop(LoopBase):
	"""Source-level post-tested do-while loop."""

	def __init__(self, body: Block, cond: BaseNode, line_info=None):
		super().__init__(cond, [body], True, line_info)

class Ternary(BaseNode):
	"""A ternary expression."""

	def __init__(self, cond: BaseNode, then_expr: BaseNode, else_expr: BaseNode, line_info=None):
		super().__init__(line_info)
		self.cond = cond
		self.then_expr = then_expr
		self.else_expr = else_expr

class VarDefinition(BaseNode):
	"""A var declaration without initialization. To initialize the var while
	declaring it, use the var definition as LHS of an assignment statement.
	"""

	def __init__(self, var: "Variable", line_info=None):
		super().__init__(line_info)
		self.var = var

class Return(BaseNode):
	"""A return expression."""

	def __init__(self, expr: BaseNode, line_info=None):
		super().__init__(line_info)
		self.expr = expr

class Break(BaseNode):
	"""A break statement."""

class Continue(BaseNode):
	"""A continue statement."""

class UnaryOperation(BaseNode):
	"""An unary operation, whith an operator and a right hand operand."""

	def __init__(self, op: Operator, right: BaseNode, line_info=None):
		super().__init__(line_info)
		self.op = op
		self.right = right

class NamedReference(BaseNode):
	"""A named reference to a :class:`arch.Memory`, BitFieldDescr, Variable, Parameter or FnParam."""

	def __init__(self, reference: Union["Memory", "BitFieldDescr", "Variable", "Parameter", "FnParam", "Intrinsic"], line_info=None):
		super().__init__(line_info)
		self.reference = reference

class IndexedReference(BaseNode):
	"""An indexed reference to a :class:`..arch.Memory/RegisterBank`. Can optionally specify a range of indices
	using the `right` parameter."""

	def __init__(self, reference: "Union[Memory, RegisterBank]", index: BaseNode, right: BaseNode=None, line_info=None):
		super().__init__(line_info)
		self.reference = reference
		self.index = index
		self.right = right

class TypeConv(BaseNode):
	"""A type conversion. Size can be None, in this case only the signedness is affected."""
	def __init__(self, data_type, size, expr: BaseNode, line_info=None):
		super().__init__(line_info)
		self.data_type = data_type
		self._size = size
		self.expr = expr

	@property
	def size(self) -> int:
		"""Returns the resolved size."""
		if isinstance(self._size, Literal):
			return int(self._size)
		return self._size

	@property
	def actual_size(self) -> int:
		"""Returns the actual size."""
		if self.size is not None:
			actual_size = 1 << (int(self.size) - 1).bit_length()
			actual_size = max(actual_size, 8)
			return actual_size
		return None

class Callable(BaseNode):
	"""A generic invocation of a callable."""

	def __init__(self, ref_or_name: Union[str, "Function"], args: "list[BaseNode]", line_info=None) -> None:
		super().__init__(line_info)
		self.ref_or_name = ref_or_name
		self.args = args if args is not None else []

class FunctionCall(Callable):
	"""A function (method with return value) call."""

class ProcedureCall(Callable):
	"""A procedure (method without return value) call."""

class Group(BaseNode):
	"""A group of expressions, used e.g. for parenthesized expressions."""
	def __init__(self, expr: BaseNode, line_info=None):
		super().__init__(line_info)
		self.expr = expr
