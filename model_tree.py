from lark import Transformer, v_args, Discard
import model_classes
from collections import defaultdict
from functools import partial
from typing import Set

#@v_args(inline=True)
class ModelTree(Transformer):
    def __init__(self):
        self.__constants = {}
        self.__address_spaces = {}
        self.__registers = {}
        self.__register_file = {}
        self.__register_alias = {}
        self.__instructions = {}
        self.__instruction_sets = {}
        self.__read_types = {}

        self.__scalars = defaultdict(dict)
        self.__fields = defaultdict(partial(defaultdict, list))
        self.__current_instr_idx = 0


    def get_constant_or_val(self, name_or_val):
        if type(name_or_val) == int:
            return name_or_val
        else:
            return self.__constants[name_or_val]

    def Base(self, args):
        return args

    def constants(self, constants):
        return constants

    def address_spaces(self, address_spaces):
        return address_spaces

    def registers(self, registers):
        return registers

    def constant_defs(self, constants):
        return constants

    def instructions(self, instructions):
        return instructions

    def range_spec(self, args) -> model_classes.RangeSpec:
        return model_classes.RangeSpec(*args)

    def CONST_ATTRIBUTE(self, args) -> model_classes.ConstAttribute:
        return model_classes.ConstAttribute[args.value.upper()]

    def const_attributes(self, args) -> Set[model_classes.ConstAttribute]:
        return set(args)

    def REG_ATTRIBUTE(self, args):
        return model_classes.RegAttribute[args.value.upper()]

    def reg_attributes(self, args):
        return set(args)

    def SPACE_ATTRIBUTE(self, args):
        return model_classes.SpaceAttribute[args.value.upper()]

    def space_attributes(self, args):
        return set(args)

    def INSTR_ATTRIBUTE(self, args):
        return model_classes.InstrAttribute[args.value.upper()]

    def instr_attributes(self, args):
        return set(args)

    def DATA_TYPE(self, args):
        return model_classes.DataType[args.value.upper()]

    def constant_decl(self, args):
        name, default_value = args

        if name in self.__constants:
            raise ValueError(f'Constant {name} already defined!')

        if name in self.__constants: return self.__constants[name]
        c = model_classes.Constant(name, default_value, set())
        self.__constants[name] = c
        return c

    def constant_def(self, args):
        name, value, attributes = args
        if name in self.__constants:
            c = self.__constants[name]
            c.value = value
            c.attributes = attributes
        else:
            c = model_classes.Constant(name, value, attributes)
            self.__constants[name] = c

        return c

    def address_space(self, args):
        name, size, power, length, attribs = args

        if name in self.__address_spaces:
            raise ValueError(f'Address space {name} already defined!')

        if name in self.__address_spaces: return self.__address_spaces[name]

        size = self.get_constant_or_val(size)
        length = self.get_constant_or_val(length)

        a = model_classes.AddressSpace(name, power, length, size, attribs)

        self.__address_spaces[name] = a
        return a

    def register(self, args):
        name, size, attributes = args

        if name in self.__registers:
            raise ValueError(f'Register {name} already defined!')

        if name in self.__registers: return self.__registers[name]

        size = self.get_constant_or_val(size)

        r = model_classes.Register(name, attributes, None, size)

        self.__registers[name] = r
        return r

    def register_file(self, args):
        _range, name, size, attributes = args

        if name in self.__register_file:
            raise ValueError(f'Register file {name} already defined!')

        if name in self.__register_file: return self.__register_file[name]

        size = self.get_constant_or_val(size)

        r = model_classes.RegisterFile(name, _range, attributes, size)

        self.__register_file[name] = r
        return r

    def register_alias(self, args):
        name, size, actual, index, attributes = args

        if name in self.__register_alias:
            raise ValueError(f'Register alias {name} already defined!')

        if name in self.__register_alias: return self.__register_alias[name]
        actual_reg = self.__register_file.get(actual) or self.__registers.get(actual)
        assert actual_reg
        size = self.get_constant_or_val(size)

        r = model_classes.RegisterAlias(name, actual_reg, index, attributes, None, size)

        self.__register_alias[name] = r
        return r

    def bit_field(self, args):
        name, _range, data_type = args
        if not data_type:
            data_type = model_classes.DataType.NONE

        b = model_classes.BitField(name, _range, data_type)

        self.__fields[self.__current_instr_idx][name].append(b)
        return b

    def BVAL(self, num):
        return model_classes.BitVal(len(num) - 1, int('0'+num, 2))

    def bit_size_spec(self, args):
        size, = args
        return size
    # def scalar_definition(self, args):
    #     name, size = args

    #     assert name not in self.__scalars[self.__current_instr_idx]
    #     if type(size) == int:
    #         s = model_classes.Scalar(name, size=size)
    #     else:
    #         size_const = self.__constants[size]
    #         s = model_classes.Scalar(name, size_const=size_const)

    #     self.__scalars[self.__current_instr_idx][name] = s
    #     return s

    def encoding(self, args):
        return args

    #def operation(self, args):
    #    return args

    # def indexed_reference(self, args):
    #     name, index_expr = args
    #     var = self.__address_spaces.get(name) or self.__register_file.get(name)

    #     assert var
    #     return var, index_expr

    # def named_reference(self, args):
    #     name, = args
    #     var = self.__scalars[self.__current_instr_idx].get(name) or \
    #         self.__fields[self.__current_instr_idx].get(name) or \
    #         self.__constants.get(name) or \
    #         self.__register_alias.get(name) or \
    #         self.__registers.get(name)

    #     assert var
    #     return var

    def instruction(self, args):
        name, attributes, encoding, disass, operation = args

        i = model_classes.Instruction(name, attributes, encoding, disass, operation)
        if name in self.__instructions:
            print(f'WARN: overwriting instruction {name}')

        self.__instructions[name] = i
        self.__current_instr_idx += 1

        return i

    def instruction_set(self, args):
        name, extension, constants, address_spaces, registers, instructions = args
        constants = {obj.name: obj for obj in constants} if constants else None
        address_spaces = {obj.name: obj for obj in address_spaces} if address_spaces else None
        registers = {obj.name: obj for obj in registers} if registers else None
        instructions = {obj.name: obj for obj in instructions} if instructions else None

        i_s = model_classes.InstructionSet(name, extension, constants, address_spaces, registers, instructions)
        self.__instruction_sets[name] = i_s
        self.__read_types[name] = None

        raise Discard
        return i_s

    def register_default(self, args):
        name, value_or_ref = args

        reg = self.__register_alias.get(name) or self.__registers.get(name)
        assert reg

        val = self.get_constant_or_val(value_or_ref)

        reg._initval = val

        raise Discard

    def core_def(self, args):
        name, _, template, _, _, _, _, _ = args
        merged_registers = {**self.__register_file, **self.__registers, **self.__register_alias}
        c = model_classes.CoreDef(name, list(self.__read_types.keys()), template, self.__constants, self.__address_spaces, self.__register_file, self.__registers, self.__register_alias, self.__instructions)
        return c