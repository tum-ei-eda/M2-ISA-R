from lark import Transformer, v_args, Discard
import model_classes
#from model_classes import DataType, InstrAttribute
from collections import defaultdict
from functools import partial
from itertools import chain

data_type_map = {
    model_classes.DataType.S: 'etiss_int',
    model_classes.DataType.U: 'etiss_uint',
    model_classes.DataType.NONE: 'etiss_uint'
}

MEM_VAL_REPL = 'mem_val_'

class CodeString:
    def __init__(self, code, static, size, signed, is_mem_access):
        self.code = code
        self.static = static
        self.size = size
        self.actual_size = 1 << (size - 1).bit_length()
        self.signed = signed
        self.is_mem_access = is_mem_access
        self.mem_ids = []

    def __str__(self):
        return self.code

    def __format__(self, format_spec):
        return self.code

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

        self.pc_reg = None

        for _, reg_descr in chain(self.__registers.items(), self.__register_aliases.items()):
            if model_classes.RegAttribute.IS_PC in reg_descr.attributes:
                self.pc_reg = reg_descr
                break

        self.generates_exception = False
        self.temp_var_count = 0
        self.mem_var_count = 0

    def get_constant_or_val(self, name_or_val):
        if type(name_or_val) == int:
            return name_or_val
        else:
            return self.__constants[name_or_val]

    def operation(self, args):
        code_str = '\n'.join(args)

        if model_classes.InstrAttribute.NO_CONT not in self.__attribs:
            code_str += f'\npartInit.code() += "{self.pc_reg.name} += {int(self.__instr_size / 8)};";'

        if self.generates_exception:
            code_str += '\npartInit.code() += "if (exception) return exception;";'
        elif model_classes.InstrAttribute.NO_CONT in self.__attribs:
            code_str += '\npartInit.code() += "return 0;";'

        return code_str

    def scalar_definition(self, args):
        name, data_type, size = args
        size_val = self.get_constant_or_val(size)
        if not data_type:
            data_type = model_classes.DataType.NONE

        s = model_classes.Scalar(name, None, size_val, data_type)

        self.__scalars[name] = s

        return CodeString(f'{data_type_map[data_type]}{s.size} {name}', False, s.size, data_type == model_classes.DataType.S, False)

    def fn_args(self, args):
        return args

    def function(self, args):
        name, fn_args = args

        if name == 'choose':
            cond, then_stmts, else_stmts = fn_args

            c = CodeString(f'({cond}) ? ({then_stmts}) : ({else_stmts})', False not in [x.static for x in fn_args], then_stmts.size if then_stmts.size > else_stmts.size else else_stmts.size, then_stmts.signed or else_stmts.signed, False)
            c.mem_ids = cond.mem_ids + then_stmts.mem_ids + else_stmts.mem_ids

            return c

        elif name == 'sext':
            expr = fn_args[0]
            if len(fn_args) == 1:
                fn_args.append(expr.size)

            size = fn_args[1]
            c = CodeString(f'(etiss_int{size})({expr.code})', expr.static, size, True, expr.is_mem_access)
            c.mem_ids = expr.mem_ids

            return c

        elif name == 'zext':
            expr = fn_args[0]

            return expr

    def conditional(self, args):
        cond, then_stmts, else_stmts = args

        code_str = f'if ({cond}) {{\n\t'
        if not cond.static:
            code_str = f'partInit.code() += "{code_str}"'

        code_str += '\n\t'.join(then_stmts)
        code_str += '\n}' if cond.static else 'partInit.code() += "\n}";'

        if else_stmts:
            code_str += ' else {\n\t' if cond.static else 'partInit.code() += "else {\n\t";'
            code_str += ' else {\n\t'
            code_str += '\n\t'.join(else_stmts)
            code_str += '\n}' if cond.static else 'partInit.code() += "\n}";'

        return code_str
        #return CodeString(code_str, False, None, None, None)

    def then_stmts(self, args):
        return args

    def else_stmts(self, args):
        return args

    def assignment(self, args):
        target, bit_size, expr = args
        static = target.static and expr.static

        if not expr.static and target.static:
            raise ValueError('Static target cannot be assigned to non-static expression!')

        if expr.static and not target.static:
            expr.code = f'" + toString({expr.code}) + "'

        code_str = ''

        if not target.is_mem_access and not expr.is_mem_access:
            code_str = f'{target.code} = {expr.code};'
            if not static:
                code_str = f'partInit.code() += "{code_str}";'

        elif not target.is_mem_access and expr.is_mem_access:
            for mem_space, mem_id, index in expr.mem_ids:
                code_str += f'partInit.code() += "etiss_uint{expr.size} {MEM_VAL_REPL}{mem_id};";\n'
                code_str += f'partInit.code() += "exception = read_mem(""{mem_space.name}"", {int(expr.size / 8)}, &{MEM_VAL_REPL}{mem_id}, {index.code});";\n'
                code_str += 'partInit.code() += "if (exception) return exception;";\n'

            code_str += f'partInit.code() += "{target.code} = {expr.code};";'

        elif target.is_mem_access and not expr.is_mem_access:
            code_str = ''
            if len(target.mem_ids) != 1:
                raise ValueError('Only one memory access is allowed as assignment target!')

            mem_space, mem_id, index = target.mem_ids[0]

            code_str += f'partInit.code() += "etiss_uint{target.size} {MEM_VAL_REPL}{mem_id} = {expr.code};";\n'
            code_str += f'partInit.code() += "exception = write_mem(""{mem_space.name}"", {int(target.size / 8)}, &{MEM_VAL_REPL}{mem_id}, {index.code});";\n'
            code_str += 'partInit.code() += "if (exception) return exception;";\n'
            pass

        return code_str


    def two_op_expr(self, args):
        left, op, right = args

        if not left.static and right.static:
            right.code = f'" + toString({right.code}) + "'
        if not right.static and left.static:
            left.code = f'" + toString({left.code}) + "'

        return CodeString(f'{left.code} {op.value} {right.code}', left.static and right.static, left.size if left.size > right.size else right.size, left.signed or right.signed, False)

    def unitary_expr(self, args):
        op, right = args
        return CodeString(f'{op.value}({right.code})', right.static, right.size, right.signed, right.is_mem_access)

    def named_reference(self, args):
        name, size = args
        referred_var = self.__registers.get(name) or self.__register_aliases.get(name) or self.__scalars.get(name) or self.__constants.get(name) or self.__fields.get(name)
        if not referred_var:
            raise ValueError(f'Named reference {name} does not exist!')

        if isinstance(referred_var, model_classes.Register):
            signed = False
            size = referred_var.size
        elif isinstance(referred_var, model_classes.BitFieldDescr) or isinstance(referred_var, model_classes.Scalar):
            signed = referred_var.data_type == model_classes.DataType.S
            size = referred_var.size
        elif isinstance(referred_var, model_classes.Constant):
            signed = referred_var.value < 0
            size = referred_var.size
        else:
            signed = False

        return CodeString(name, name in self.__fields, size, signed, False)

    def indexed_reference(self, args):
        name, index, size = args

        referred_var = self.__register_files.get(name) or self.__spaces.get(name)
        if not referred_var:
            raise ValueError(f'Indexed reference {name} does not exist!')

        if not size:
            size = referred_var.size

        if index.static:
            index.code = f'" + toString({index.code}) + "'

        if isinstance(referred_var, model_classes.RegisterFile):
            code_str = f'{name}[{index.code}]'
            if size != referred_var.size:
                code_str = f'(etiss_uint{size})' + code_str

            return CodeString(code_str, False, size, False, False)

        elif isinstance(referred_var, model_classes.AddressSpace):
            c = CodeString(f'{MEM_VAL_REPL}{self.mem_var_count}', False, size, False, True)
            c.mem_ids.append((referred_var, self.mem_var_count, index))
            self.mem_var_count += 1
            return c

    def number_literal(self, args):
        lit, = args
        return CodeString(lit, True, self.__native_size, int(lit) < 0, False)

    def type_conv(self, args):
        expr, data_type = args
        return CodeString(f'({data_type_map[data_type]}{expr.actual_size})({expr.code})', expr.static, expr.size, data_type == model_classes.DataType.S, expr.is_mem_access)