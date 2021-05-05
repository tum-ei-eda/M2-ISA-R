from typing import Mapping

from lark import Transformer

import model_classes
from etiss_instruction_utils import StaticType


class EtissModelBuilder(Transformer):
    def __init__(self, constants: Mapping[str, model_classes.Constant], memories: Mapping[str, model_classes.Memory], memory_aliases: Mapping[str, model_classes.Memory],
        fields: Mapping[str, model_classes.BitFieldDescr], functions: Mapping[str, model_classes.Function]):

        self.__constants = constants
        self.__memories = memories
        self.__memory_aliases = memory_aliases
        self.__fields = fields
        self.__scalars = {}
        self.__functions = functions

    def get_constant_or_val(self, name_or_val):
        if type(name_or_val) == int:
            return name_or_val
        else:
            return self.__constants[name_or_val]

    def FUNCTIONNAME(self, args):
        return args.value

    PROCEDURENAME = FUNCTIONNAME

    def ADD_OP(self, args):
        return model_classes.Operator(args.value)

    BOOL_OR_OP = ADD_OP
    BOOL_AND_OP = ADD_OP

    BIT_OR_OP = ADD_OP
    BIT_XOR_OP = ADD_OP
    BIT_AND_OP = ADD_OP

    EQ_OP = ADD_OP
    COMP_OP = ADD_OP
    SHIFT_OP = ADD_OP
    MULT_OP = ADD_OP
    UNITARY_OP = ADD_OP

    def stmt_list(self, args):
        return args

    def operation(self, args):
        return model_classes.Operation(args)

    def scalar_definition(self, args):
        name, data_type, size = args

        if name in self.__scalars:
            raise ValueError(f"Scalar {name} already defined!")

        size_val = self.get_constant_or_val(size)

        if not data_type:
            data_type = model_classes.DataType.U

        s = model_classes.Scalar(name, None, StaticType.WRITE, size_val, data_type)

        self.__scalars[name] = s
        return model_classes.ScalarDefinition(s)

    def return_(self, args):
        return model_classes.Return(args[0])

    def assignment(self, args):
        target, expr = args

        return model_classes.Assignment(target, expr)

    def indexed_reference(self, args):
        name, index_expr, size = args
        referred_mem = self.__memory_aliases.get(name) or self.__memories.get(name)

        if referred_mem is None:
            raise ValueError(f"Indexed reference {name} does not exist!")

        ref = model_classes.IndexedReference(referred_mem, index_expr)
        if size is None:
            return ref
        else:
            return model_classes.TypeConv(None, size, ref)

    def named_reference(self, args):
        name, size = args
        var = self.__scalars.get(name) or \
            self.__fields.get(name) or \
            self.__constants.get(name) or \
            self.__memory_aliases.get(name) or \
            self.__memories.get(name)

        if var is None:
            raise ValueError(f"Named reference {name} does not exist!")

        ref = model_classes.NamedReference(var)
        if size is None:
            return ref
        else:
            return model_classes.TypeConv(None, size, ref)

    def two_op_expr(self, args):
        left, op, right = args

        return model_classes.BinaryOperation(left, op, right)

    def unitary_expr(self, args):
        op, right = args

        return model_classes.UnaryOperation(op, right)

    def number_literal(self, args):
        lit, = args
        return model_classes.NumberLiteral(int(lit))

    def type_conv(self, args):
        expr, data_type = args

        return model_classes.TypeConv(data_type, None, expr)

    def conditional(self, args):
        cond, then_stmts, else_stmts = args

        return model_classes.Conditional(cond, then_stmts, else_stmts)

    def procedure(self, args):
        return self.function(args)

    def function(self, args):
        name, fn_args = args

        if name not in self.__functions:
            print(f"WARN: Function {name} not defined in instruction set, generator must add it later!")
        else:
            name = self.__functions[name]

        return model_classes.FunctionCall(name, fn_args)

    def fn_args(self, args):
        return args

    def parens(self, args):
        expr, = args
        return model_classes.Group(expr)