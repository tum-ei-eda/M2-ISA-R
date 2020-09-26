from lark import Transformer, v_args, Discard
from model_classes import DataType, InstrAttribute
from collections import defaultdict
from functools import partial

data_type_map = {
    DataType.S: 'etiss_int32',
    DataType.U: 'etiss_uint32',
    DataType.NONE: 'etiss_uint32'
}

class CodeString:
    def __init__(self, code, static, size, signed):
        self.code = code
        self.static = static
        self.size = size
        self.signed = signed

class EtissInstructionWriter(Transformer):
    def __init__(self, constants, spaces, registers, register_files, register_aliases, fields, attribs, instr_size, native_size):
        self.__constants = constants
        self.__spaces = spaces
        self.__registers = registers
        self.__register_files = register_files
        self.__register_aliases = register_aliases
        self.__fields = fields
        self.__attribs = attribs if attribs else []
        self.__scalars = {}
        self.__instr_size = instr_size
        self.__native_size = native_size

        self.code_lines = []

        self.generates_exception = False
        self.temp_var_count = 0
    
    def operation(self, args):
        pass
        #return '\n'.join(args)

    def scalar_definition(self, args):
        name, dtype, size = args

    def fn_args(self, args):
        return args
    
    def function(self, args):
        name, fn_args = args

    def conditional(self, args):
        cond, then_stmts, else_stmts = args
    
    def then_stmts(self, args):
        return args

    def else_stmts(self, args):
        return args

    def assignment(self, args):
        target, bit_size, expr = args

    def two_op_expr(self, args):
        left, op, right = args
    
    def unitary_expr(self, args):
        op, right = args
  
    def named_reference(self, args):
        name, size = args
        referred_var = self.__registers.get(name) or self.__register_aliases.get(name) or self.__scalars.get(name) or self.__constants.get(name) or self.__fields.get(name)
        if not referred_var:
            raise ValueError(f'Named reference {name} does not exist!')
        
        return CodeString(name, name in self.__fields, size, False)
    
    def indexed_reference(self, args):
        name, index, size = args

    def number_literal(self, args):
        lit, = args
        return CodeString(lit, True, self.__native_size, int(lit) < 0)
    
    def type_conv(self, args):
        expr, data_type = args