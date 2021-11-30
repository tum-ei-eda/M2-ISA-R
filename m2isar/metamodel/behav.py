from typing import TYPE_CHECKING, List, Union

if TYPE_CHECKING:
	from .arch import BitFieldDescr, Constant, FnParam, Function, Memory, Scalar


class BaseNode:
	def generate(self, context):
		raise NotImplementedError()

class Operator(BaseNode):
	def __init__(self, op: str):
		self.value = op

class Operation(BaseNode):
	def __init__(self, statements: List[BaseNode]) -> None:
		self.statements = statements

class BinaryOperation(BaseNode):
	def __init__(self, left: BaseNode, op: Operator, right: BaseNode):
		self.left = left
		self.op = op
		self.right = right

class SliceOperation(BaseNode):
	def __init__(self, expr: BaseNode, left: BaseNode, right: BaseNode):
		self.expr = expr
		self.left = left
		self.right = right

class NumberLiteral(BaseNode):
	def __init__(self, value):
		self.value = value

class IntLiteral(NumberLiteral):
	def __init__(self, value: int, bit_size: int=None, signed: bool=None):
		super().__init__(value)

		if bit_size is None:
			self.bit_size = value.bit_length()
		else:
			self.bit_size = bit_size

		if signed is None:
			self.signed = value < 0
		else:
			self.signed = signed

class Assignment(BaseNode):
	def __init__(self, target: BaseNode, expr: BaseNode):
		self.target = target
		self.expr = expr

class Conditional(BaseNode):
	def __init__(self, cond: BaseNode, then_stmts: List[BaseNode], else_stmts: List[BaseNode]):
		self.cond = cond
		self.then_stmts = then_stmts if then_stmts is not None else []
		self.else_stmts = else_stmts if else_stmts is not None else []

class Ternary(BaseNode):
	def __init__(self, cond: BaseNode, then_expr: BaseNode, else_expr: BaseNode):
		self.cond = cond
		self.then_expr = then_expr
		self.else_expr = else_expr

class ScalarDefinition(BaseNode):
	def __init__(self, scalar: "Scalar"):
		self.scalar = scalar

class Return(BaseNode):
	def __init__(self, expr: BaseNode):
		self.expr = expr

class UnaryOperation(BaseNode):
	def __init__(self, op: Operator, right: BaseNode):
		self.op = op
		self.right = right

class NamedReference(BaseNode):
	def __init__(self, reference: Union["Memory", "BitFieldDescr", "Scalar", "Constant", "FnParam"]):
		self.reference = reference

class IndexedReference(BaseNode):
	def __init__(self, reference: "Memory", index: BaseNode, right: BaseNode=None):
		self.reference = reference
		self.index = index
		self.right = right

class TypeConv(BaseNode):
	def __init__(self, data_type, size, expr: BaseNode):
		self.data_type = data_type
		self.size = size
		self.expr = expr

		if self.size is not None:
			self.actual_size = 1 << (self.size - 1).bit_length()
			if self.actual_size < 8:
				self.actual_size = 8
		else:
			self.actual_size = None

class Callable(BaseNode):
	def __init__(self, ref_or_name: Union[str, "Function"], args: List[BaseNode]) -> None:
		self.ref_or_name = ref_or_name
		self.args = args if args is not None else []

class FunctionCall(Callable):
	pass

class ProcedureCall(Callable):
	pass

class Group(BaseNode):
	def __init__(self, expr: BaseNode):
		self.expr = expr
