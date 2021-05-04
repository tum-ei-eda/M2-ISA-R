from typing import List, Union

import model_classes.arch


class BaseNode:
    def generate(self, context):
        raise NotImplementedError()

class Operator(BaseNode):
    def __init__(self, op):
        self.value = op

class Operation(BaseNode):
    def __init__(self, statements: List[BaseNode]) -> None:
        self.statements = statements

class BinaryOperation(BaseNode):
    def __init__(self, left: BaseNode, op: Operator, right: BaseNode):
        self.left = left
        self.op = op
        self.right = right

class NumberLiteral(BaseNode):
    def __init__(self, value):
        self.value = value

class Assignment(BaseNode):
    def __init__(self, target, expr):
        self.target = target
        self.expr = expr

class Conditional(BaseNode):
    def __init__(self, cond, then_stmts, else_stmts):
        self.cond = cond
        self.then_stmts = then_stmts if then_stmts is not None else []
        self.else_stmts = else_stmts if else_stmts is not None else []

class ScalarDefinition(BaseNode):
    def __init__(self, scalar: model_classes.arch.Scalar):
        self.scalar = scalar

class Return(BaseNode):
    def __init__(self, expr: BaseNode):
        self.expr = expr

class UnaryOperation(BaseNode):
    def __init__(self, op, right):
        self.op = op
        self.right = right

class NamedReference(BaseNode):
    def __init__(self, reference):
        self.reference = reference

class IndexedReference(BaseNode):
    def __init__(self, reference, index):
        self.reference = reference
        self.index = index

class TypeConv(BaseNode):
    def __init__(self, data_type, size, expr: BaseNode):
        self.data_type = data_type
        self.size = size
        self.expr = expr

class FunctionCall(BaseNode):
    def __init__(self, ref_or_name: Union[str, model_classes.arch.Function], args) -> None:
        self.ref_or_name = ref_or_name
        self.args = args

class Group(BaseNode):
    def __init__(self, expr):
        self.expr = expr

