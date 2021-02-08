class BinaryOperation:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

class NumberLiteral:
    def __init__(self, value):
        self.value = value

class Assignment:
    def __init__(self, target, expr):
        self.target = target
        self.expr = expr

class Conditional:
    def __init__(self, cond, then_stmts, else_stmts):
        self.cond = cond
        self.then_stmts = then_stmts
        self.else_stmts = else_stmts

class Return:
    def __init__(self, expr):
        self.expr = expr

class UnaryOperation:
    def __init__(self, op, right):
        self.op = op
        self.right = right

class NamedReference:
    def __init__(self, name, size):
        self.name = name
        self.size = size

class IndexedReference:
    def __init__(self, name, index, size):
        self.name = name
        self.index = index
        self.size = size

class TypeConv:
    def __init__(self, data_type, expr):
        self.data_type = data_type
        self.expr = expr