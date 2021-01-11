from enum import Flag, auto
from itertools import chain
from string import Template

from lark import Transformer

import etiss_replacements
import model_classes
import model_classes.arch

data_type_map = {
    model_classes.DataType.S: 'etiss_int',
    model_classes.DataType.U: 'etiss_uint',
    model_classes.DataType.NONE: 'void'
}

class StaticType(Flag):
    NONE = 0
    READ = auto()
    WRITE = auto()
    RW = READ | WRITE

def make_static(val):
    return f'" + std::to_string({val}) + "'


MEM_VAL_REPL = 'mem_val_'

class CodeString:
    def __init__(self, code, static, size, signed, is_mem_access, regs_affected=None):
        self.code = code
        self.static = StaticType(static)
        self.size = size
        self.actual_size = 1 << (size - 1).bit_length()
        self.signed = signed
        self.is_mem_access = is_mem_access
        self.mem_ids = []
        self.regs_affected = regs_affected if isinstance(regs_affected, set) else set()
        self.scalar = None

    def __str__(self):
        return self.code

    def __format__(self, format_spec):
        return self.code

class EtissInstructionWriter(Transformer):
    def __init__(self, constants, spaces, registers, register_files, register_aliases, fields, attribs, functions, instr_size, native_size, arch_name, ignore_static=False):
        self.__constants = constants
        self.__spaces = spaces
        self.__registers = registers
        self.__register_files = register_files
        self.__register_aliases = register_aliases
        self.__fields = fields
        self.__attribs = attribs if attribs else []
        self.__scalars = {}
        self.__functions = functions
        self.__instr_size = instr_size
        self.__native_size = native_size
        self.__arch_name = arch_name

        self.ignore_static = ignore_static

        self.code_lines = []

        self.pc_reg = None

        for _, reg_descr in chain(self.__registers.items(), self.__register_aliases.items()):
            if model_classes.RegAttribute.IS_PC in reg_descr.attributes:
                self.pc_reg = reg_descr
                break

        self.generates_exception = False
        self.is_exception = False
        self.temp_var_count = 0
        self.mem_var_count = 0
        self.affected_regs = set()
        self.dependent_regs = set()

    def get_constant_or_val(self, name_or_val):
        if type(name_or_val) == int:
            return name_or_val
        else:
            return self.__constants[name_or_val]

    def operation(self, args):
        code_str = '\n'.join(args)

        if self.is_exception:
            code_str += '\npartInit.code() += "return exception;\\n";'
        elif self.generates_exception:
            code_str += '\npartInit.code() += "if (exception) return exception;\\n";'
        elif model_classes.InstrAttribute.NO_CONT in self.__attribs:
            code_str += '\npartInit.code() += "return 0;\\n";'

        return code_str

    def return_(self, args):
        return f'return {args[0].code};'

    def scalar_definition(self, args):
        name, data_type, size = args
        size_val = self.get_constant_or_val(size)
        if not data_type:
            data_type = model_classes.DataType.U

        s = model_classes.arch.Scalar(name, None, StaticType.WRITE, size_val, data_type)

        self.__scalars[name] = s
        actual_size = 1 << (s.size - 1).bit_length()
        c = CodeString(f'{data_type_map[data_type]}{actual_size} {name}', StaticType.WRITE, s.size, data_type == model_classes.DataType.S, False)
        c.scalar = s
        return c

    def fn_args(self, args):
        return args

    def procedure(self, args):
        name, fn_args = args

        if name == 'wait':
            self.generates_exception = True
            return 'partInit.code() += "exception = ETISS_RETURNCODE_CPUFINISHED;\\n";'

        elif name == 'raise':
            sender, code = fn_args
            exc_id = (int(sender.code), int(code.code))
            if exc_id not in etiss_replacements.exception_mapping:
                raise ValueError(f'Exception {exc_id} not defined!')

            self.generates_exception = True
            return f'partInit.code() += "exception = {etiss_replacements.exception_mapping[exc_id]};\\n";'

    def function(self, args):
        name, fn_args = args

        if name == 'choose':
            cond, then_stmts, else_stmts = fn_args
            static = StaticType.NONE not in [x.static for x in fn_args]
            if not static:
                if cond.static:
                    cond.code = Template(make_static(cond.code)).safe_substitute(etiss_replacements.rename_static)
                if then_stmts.static:
                    then_stmts.code = Template(make_static(then_stmts.code)).safe_substitute(etiss_replacements.rename_static)
                if else_stmts.static:
                    else_stmts.code = Template(make_static(else_stmts.code)).safe_substitute(etiss_replacements.rename_static)

            c = CodeString(f'({cond}) ? ({then_stmts}) : ({else_stmts})', static, then_stmts.size if then_stmts.size > else_stmts.size else else_stmts.size, then_stmts.signed or else_stmts.signed, False, set.union(cond.regs_affected, then_stmts.regs_affected, else_stmts.regs_affected))
            c.mem_ids = cond.mem_ids + then_stmts.mem_ids + else_stmts.mem_ids

            return c

        elif name == 'sext':
            expr = fn_args[0]
            if len(fn_args) == 1:
                size = expr.size
            else:
                size = int(fn_args[1].code)

            c = CodeString(f'(etiss_int{size})({expr.code})', expr.static, size, True, expr.is_mem_access, expr.regs_affected)
            c.mem_ids = expr.mem_ids

            return c

        elif name == 'zext':
            expr = fn_args[0]

            return expr

        elif name == 'shll':
            expr, amount = fn_args
            if amount.static:
                amount.code = make_static(amount.code)
            return CodeString(f'({expr.code}) << ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

        elif name == 'shrl':
            expr, amount = fn_args
            if amount.static:
                amount.code = make_static(amount.code)
            return CodeString(f'({expr.code}) >> ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

        elif name == 'shra':
            expr, amount = fn_args
            if amount.static:
                amount.code = make_static(amount.code)
            return CodeString(f'(etiss_int{expr.actual_size})({expr.code}) >> ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

        elif name in self.__functions:
            for arg in fn_args:
                if arg.static:
                    arg.code = make_static(arg.code)

            arg_str = ', '.join([arg.code for arg in fn_args])
            max_size = max([arg.size for arg in fn_args])
            mem_access = True in [arg.is_mem_access for arg in fn_args]
            signed = True in [arg.signed for arg in fn_args]
            regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))

            c = CodeString(f'{name}(cpu, system, plugin_pointers, {arg_str})', StaticType.NONE, max_size, signed, mem_access, regs_affected)
            c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

            return c

        elif name.startswith('fdispatch'):
            pass

        else:
            raise ValueError(f'Function {name} not recognized!')

    def conditional(self, args):
        cond, then_stmts, else_stmts = args

        code_str = f'if ({cond}) {{'
        if not cond.static:
            code_str = f'partInit.code() += "{code_str}\\n";'
            self.dependent_regs.update(cond.regs_affected)

        code_str += '\n'
        code_str += '\n'.join(then_stmts)
        code_str += '\n}' if cond.static else '\npartInit.code() += "}\\n";'

        if else_stmts:
            code_str += ' else {\n' if cond.static else '\npartInit.code() += " else {\\n";\n'
            code_str += '\n'.join(else_stmts)
            code_str += '\n}' if cond.static else '\npartInit.code() += "}\\n";'

        return code_str

    def stmt_list(self, args):
        return args

    def assignment(self, args):
        target, expr = args
        static = bool(target.static & StaticType.WRITE) and bool(expr.static)

        if target.scalar:
            if expr.static:
                target.scalar.static = StaticType.READ
            else:
                target.scalar.static = StaticType.NONE
                target.static = StaticType.NONE

        if not expr.static and bool(target.static & StaticType.WRITE):
            raise ValueError('Static target cannot be assigned to non-static expression!')

        if expr.static:
            if bool(target.static & StaticType.WRITE):
                expr.code = Template(f'{expr.code}').safe_substitute(**etiss_replacements.rename_static)

            else:
                expr.code = Template(make_static(expr.code)).safe_substitute(**etiss_replacements.rename_static)

        if bool(target.static & StaticType.READ):
            target.code = Template(target.code).safe_substitute(etiss_replacements.rename_dynamic)
        code_str = ''

        self.affected_regs.update(target.regs_affected)
        self.dependent_regs.update(expr.regs_affected)

        if not target.is_mem_access and not expr.is_mem_access:
            code_str = f'{target.code} = {expr.code};'
            if not static:
                code_str = f'partInit.code() += "{code_str}\\n";'

        elif not target.is_mem_access and expr.is_mem_access:
            self.generates_exception = True
            for mem_space, mem_id, index in expr.mem_ids:
                code_str += f'partInit.code() += "etiss_uint{expr.actual_size} {MEM_VAL_REPL}{mem_id};\\n";\n'
                #code_str += f'partInit.code() += "exception = read_mem(""{mem_space.name}"", {int(expr.size / 8)}, &{MEM_VAL_REPL}{mem_id}, {index.code});\\n";\n'
                code_str += f'partInit.code() += "exception = (*(system->dread))(system->handle, cpu, {index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{mem_id}, {int(expr.actual_size / 8)});\\n";\n'
                #code_str += 'partInit.code() += "if (exception) return exception;\\n";\n'

            code_str += f'partInit.code() += "{target.code} = {expr.code};\\n";'

        elif target.is_mem_access and not expr.is_mem_access:
            code_str = ''
            if len(target.mem_ids) != 1:
                raise ValueError('Only one memory access is allowed as assignment target!')

            self.generates_exception = True
            mem_space, mem_id, index = target.mem_ids[0]

            code_str += f'partInit.code() += "etiss_uint{target.actual_size} {MEM_VAL_REPL}{mem_id} = {expr.code};\\n";\n'
            #code_str += f'partInit.code() += "exception = write_mem(""{mem_space.name}"", {int(target.size / 8)}, &{MEM_VAL_REPL}{mem_id}, {index.code});\\n";\n'
            code_str += f'partInit.code() += "exception = (*(system->dwrite))(system->handle, cpu, {index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{mem_id}, {int(target.actual_size / 8)});\\n";\n'
            #code_str += 'partInit.code() += "if (exception) return exception;\\n";\n'
            pass

        return code_str


    def two_op_expr(self, args):
        left, op, right = args

        if not left.static and right.static:
            right.code = make_static(right.code)
        if not right.static and left.static:
            left.code = make_static(left.code)

        return CodeString(f'{left.code} {op.value} {right.code}', left.static and right.static, left.size if left.size > right.size else right.size, left.signed or right.signed, False, set.union(left.regs_affected, right.regs_affected))

    def unitary_expr(self, args):
        op, right = args
        return CodeString(f'{op.value}({right.code})', right.static, right.size, right.signed, right.is_mem_access, right.regs_affected)

    def named_reference(self, args):
        name, size = args
        referred_var = self.__registers.get(name) or self.__register_aliases.get(name) or self.__scalars.get(name) or self.__constants.get(name) or self.__fields.get(name)
        if not referred_var:
            raise ValueError(f'Named reference {name} does not exist!')

        static = StaticType.NONE

        if name in etiss_replacements.rename_static:
            name = f'${{{name}}}'
            static = StaticType.READ

        if isinstance(referred_var, model_classes.arch.Register):
            if not static:
                name = etiss_replacements.prefixes.get(name, etiss_replacements.default_prefix) + name
            signed = False
            size = referred_var.size
        elif isinstance(referred_var, model_classes.arch.BitFieldDescr):
            signed = referred_var.data_type == model_classes.DataType.S
            size = referred_var.size
            static = StaticType.READ
        elif isinstance(referred_var, model_classes.arch.Scalar):
            signed = referred_var.data_type == model_classes.DataType.S
            size = referred_var.size
            static = referred_var.static
        elif isinstance(referred_var, model_classes.arch.Constant):
            signed = referred_var.value < 0
            size = self.__native_size
            static = StaticType.READ
            name = f'{referred_var.value}'
        elif isinstance(referred_var, model_classes.arch.FnParam):
            signed = referred_var.data_type == model_classes.DataType.S
            size = referred_var.size
            static = StaticType.RW
        else:
            signed = False

        if self.ignore_static:
            static = StaticType.RW

        return CodeString(name, static, size, signed, False)

    def indexed_reference(self, args):
        name, index, size = args

        referred_var = self.__register_files.get(name) or self.__spaces.get(name)
        if not referred_var:
            raise ValueError(f'Indexed reference {name} does not exist!')

        if not size:
            size = referred_var.size

        index_code = index.code
        if index.static and not self.ignore_static:
            index.code = make_static(index.code)

        if self.ignore_static:
            static = StaticType.RW
        else:
            static = StaticType.NONE

        if isinstance(referred_var, model_classes.arch.RegisterFile) or (isinstance(referred_var, model_classes.arch.AddressSpace) and model_classes.SpaceAttribute.MAIN_MEM not in referred_var.attributes):
            code_str = f'{etiss_replacements.prefixes.get(name, etiss_replacements.default_prefix)}{name}[{index.code}]'
            if size != referred_var.size:
                code_str = f'(etiss_uint{size})' + code_str
            c = CodeString(code_str, static, size, False, False)

            if isinstance(referred_var, model_classes.arch.RegisterFile):# and referred_var.name == 'X': # TODO: Hack, remove
                c.regs_affected.add(index_code)

            return c

        elif isinstance(referred_var, model_classes.arch.AddressSpace):
            c = CodeString(f'{MEM_VAL_REPL}{self.mem_var_count}', static, size, False, True)
            c.mem_ids.append((referred_var, self.mem_var_count, index))
            self.mem_var_count += 1
            return c

    def number_literal(self, args):
        lit, = args
        return CodeString(str(lit), True, self.__native_size, int(lit) < 0, False)

    def type_conv(self, args):
        expr, data_type = args
        return CodeString(f'({data_type_map[data_type]}{expr.actual_size})({expr.code})', expr.static, expr.size, data_type == model_classes.DataType.S, expr.is_mem_access, expr.regs_affected)

    def parens(self, args):
        expr, = args
        if isinstance(expr, CodeString):
            expr.code = f'({expr.code})'
        else:
            expr = f'({expr})'
        return expr