import logging
from typing import List, Mapping, Set, Tuple

from lark import Discard, Transformer, Tree

import model_classes

logger = logging.getLogger("architecture")

class ArchitectureModelBuilder(Transformer):
    _constants: Mapping[str, model_classes.Constant]
    _address_spaces: Mapping[str, model_classes.AddressSpace]
    _registers: Mapping[str, model_classes.Register]
    _register_files: Mapping[str, model_classes.RegisterFile]
    _register_alias: Mapping[str, model_classes.RegisterAlias]
    _instructions: Mapping[str, model_classes.Instruction]
    _functions: Mapping[str, model_classes.Function]
    _instruction_sets: Mapping[str, model_classes.InstructionSet]
    _read_types: Mapping[str, str]
    _memories: Mapping[str, model_classes.Memory]
    _memory_aliases: Mapping[str, model_classes.Memory]
    _overwritten_instrs: List[Tuple[model_classes.Instruction, model_classes.Instruction]]

    def __init__(self):
        self._constants = {}
        self._address_spaces = {}
        self._registers = {}
        self._register_files = {}
        self._register_alias = {}
        self._instructions = {}
        self._functions = {}
        self._instruction_sets = {}
        self._read_types = {}
        self._memories = {}
        self._memory_aliases = {}

        self._overwritten_instrs = []

    def transform(self, tree: Tree):
        ret = super().transform(tree)
        for orig, overwritten in self._overwritten_instrs:
            logger.warning("instr %s from extension %s was overwritten by %s from %s", orig.name, orig.ext_name, overwritten.name, overwritten.ext_name)

        return ret

    def get_constant_or_val(self, name_or_val):
        if type(name_or_val) == int:
            return name_or_val
        else:
            return self._constants[name_or_val]

    def Base(self, args):
        return args

    def make_list(self, args):
        return args

    def make_set(self, args):
        return set(args)

    def constants(self, constants):
        return constants

    def address_spaces(self, address_spaces):
        return address_spaces

    def registers(self, registers):
        return registers

    def constant_defs(self, constants):
        return constants

    def functions(self, functions):
        return functions

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

    def TEXT(self, args):
        return args.value

    def constant_decl(self, args):
        name, default_value = args

        if name in self._constants:
            raise ValueError(f'Constant {name} already defined!')

        if name in self._constants: return self._constants[name]
        c = model_classes.Constant(name, default_value, set())
        self._constants[name] = c
        logger.debug(f'constant_decl {str(c)}')
        return c

    def constant_def(self, args):
        name, value, attributes = args
        if name in self._constants:
            c = self._constants[name]
            c.value = value
            c.attributes = attributes

            logger.debug(f'constant_def {str(c)}, used existing')
        else:
            c = model_classes.Constant(name, value, attributes)
            self._constants[name] = c

            logger.debug(f'constant_def {str(c)}')

        return c

    def address_space(self, args):
        name, size, length_base, length_power, attribs = args

        if name in self._address_spaces:
            raise ValueError(f'Address space {name} already defined!')

        if name in self._address_spaces: return self._address_spaces[name]

        size = self.get_constant_or_val(size)
        length_base = self.get_constant_or_val(length_base)
        length_power = self.get_constant_or_val(length_power) if length_power is not None else 1

        a = model_classes.AddressSpace(name, length_base, length_power, size, attribs)
        self._address_spaces[name] = a

        m = model_classes.Memory(name, model_classes.RangeSpec(length_base, 0, length_power), size, attribs)
        self._memories[name] = m

        logger.debug(f'address_space {str(m)}')
        return a

    def register(self, args):
        name, size, attributes = args

        if name in self._registers:
            raise ValueError(f'Register {name} already defined!')

        size = self.get_constant_or_val(size)

        r = model_classes.Register(name, attributes, None, size)
        self._registers[name] = r

        m = model_classes.Memory(name, model_classes.RangeSpec(0, 0), size, attributes)
        self._memories[name] = m

        logger.debug(f'register {str(m)}')
        return r

    def register_file(self, args):
        _range, name, size, attributes = args

        if name in self._register_files:
            raise ValueError(f'Register file {name} already defined!')

        if name in self._register_files: return self._register_files[name]

        size = self.get_constant_or_val(size)

        r = model_classes.RegisterFile(name, _range, attributes, size)
        self._register_files[name] = r

        m = model_classes.Memory(name, _range, size, attributes)
        self._memories[name] = m

        logger.debug(f'register_file {str(m)}')
        return r

    def register_alias(self, args):
        name, size, actual, index, attributes = args

        if name in self._register_alias:
            raise ValueError(f'Register alias {name} already defined!')

        actual_reg = self._register_files.get(actual) or self._registers.get(actual) or self._register_alias.get(actual)
        if actual_reg is None:
            raise ValueError(f'Parent register {actual} for alias {name} not defined!')

        size = self.get_constant_or_val(size)

        r = model_classes.RegisterAlias(name, actual_reg, index, attributes, None, size)
        self._register_alias[name] = r

        if not isinstance(index, model_classes.RangeSpec):
            index = model_classes.RangeSpec(index, index)

        parent_mem = self._memories.get(actual) or self._memory_aliases.get(actual)
        if parent_mem is None:
            raise ValueError(f'Parent register {actual} for alias {name} not defined!')

        m = model_classes.Memory(name, index, size, attributes)
        parent_mem.children.append(m)
        self._memory_aliases[name] = m

        logger.debug(f'register_alias {str(m)}, parent {str(parent_mem)}')
        return r

    def bit_field(self, args):
        name, _range, data_type = args
        if not data_type:
            data_type = model_classes.DataType.U

        b = model_classes.BitField(name, _range, data_type)

        logger.debug(f'bit_field {str(b)}')
        return b

    def BVAL(self, num):
        return model_classes.BitVal(len(num) - 1, int('0'+num, 2))

    def bit_size_spec(self, args):
        size, = args
        return size

    def encoding(self, args):
        return args

    def instruction(self, args):
        name, attributes, encoding, disass, operation = args

        i = model_classes.Instruction(name, attributes, encoding, disass, operation)

        instr_id = (i.code, i.mask)

        if instr_id in self._instructions:
            self._overwritten_instrs.append((self._instructions[instr_id], i))

        self._instructions[instr_id] = i

        logger.debug(f'instruction {str(i)}')
        return i

    def fn_args_def(self, args):
        return args

    def fn_arg_def(self, args):
        name, data_type, size = args
        if not data_type:
            data_type = model_classes.DataType.U

        size = self.get_constant_or_val(size)

        fp = model_classes.FnParam(name, size, data_type)
        logger.debug(f'fn_param {str(fp)}')
        return fp

    def function_def(self, args):
        return_len, name, fn_args, data_type, attributes, operation = args

        if not data_type and not return_len:
            data_type = model_classes.DataType.NONE
        elif not data_type:
            data_type = model_classes.DataType.U

        return_len = self.get_constant_or_val(return_len) if return_len else None
        f = model_classes.Function(name, return_len, data_type, fn_args, operation)

        self._functions[name] = f

        logger.debug(f'function {str(f)}')
        return f

    def instruction_set(self, args):
        name, extension, constants, address_spaces, registers, functions, instructions = args
        constants = {obj.name: obj for obj in constants} if constants else None
        address_spaces = {obj.name: obj for obj in address_spaces} if address_spaces else None
        registers = {obj.name: obj for obj in registers} if registers else None

        instructions_dict = None
        if instructions:
            instructions_dict = {}
            for i in instructions:
                instr_id = (i.code, i.mask)
                instructions_dict[instr_id] = i
                i.ext_name = name

        functions_dict = None
        if functions:
            functions_dict = {}
            for f in functions:
                functions_dict[f.name] = f
                f.ext_name = name

        i_s = model_classes.InstructionSet(name, extension, constants, address_spaces, registers, functions_dict, instructions_dict)
        self._instruction_sets[name] = i_s
        self._read_types[name] = None

        logger.debug(f'instruction_set {str(i_s)}')
        raise Discard

    def register_default(self, args):
        name, value_or_ref = args

        reg = self._register_alias.get(name) or self._registers.get(name)
        assert reg

        val = self.get_constant_or_val(value_or_ref)

        reg._initval = val

        raise Discard

    def core_def(self, args):
        name, _, template, _, _, _, _, _, _ = args
        merged_registers = {**self._register_files, **self._registers, **self._register_alias}
        c = model_classes.CoreDef(name, list(self._read_types.keys()), template, self._constants, self._address_spaces, self._register_files, self._registers, self._register_alias, self._memories, self._memory_aliases, self._functions, self._instructions)

        logger.debug(f'core_def {str(c)}')
        return c
