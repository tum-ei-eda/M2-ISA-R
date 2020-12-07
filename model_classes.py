from collections import defaultdict, namedtuple
from enum import Enum, auto
from os import stat

from lark import Tree

#RangeSpec = namedtuple('RangeSpec', ['upper', 'lower'])
BitVal = namedtuple('BitVal', ['length', 'value'])

class RangeSpec:
    def __init__(self, upper, lower):
        self.upper = upper
        self.lower = lower

    @property
    def length(self):
        return self.upper - self.lower + 1


class RegAttribute(Enum):
    IS_PC = auto()
    DELETE = auto()

class SpaceAttribute(Enum):
    MAIN_MEM = auto()

class ConstAttribute(Enum):
    IS_REG_WIDTH = auto()
    IS_ADDR_WIDTH = auto()

class InstrAttribute(Enum):
    NO_CONT = auto()
    COND = auto()
    FLUSH = auto()

class DataType(Enum):
    NONE = auto()
    U = auto()
    S = auto()
    F = auto()
    D = auto()
    Q = auto()
    B = auto()

class Named:
    def __init__(self, name):
        self.name = name

    def __str__(self) -> str:
        return f'<{type(self).__name__} object>: name={self.name}'

    def __repr__(self) -> str:
        return f'<{type(self).__name__} object>: name={self.name}'

class Constant(Named):
    def __init__(self, name, value, attributes):
        self.value = value
        self.attributes = attributes if attributes else []
        super().__init__(name)

    def __str__(self) -> str:
        return f'{super().__str__()}, value={self.value}'

class SizedRefOrConst(Named):
    def __init__(self, name, size):
        self._size = size
        super().__init__(name)

    @property
    def size(self):
        if isinstance(self._size, Constant):
            return self._size.value
        else:
            return self._size

    @property
    def actual_size(self):
        temp = 1 << (self.size - 1).bit_length()
        return temp if temp >= 8 else 8

    def __str__(self) -> str:
        return f'{super().__str__()}, size={self.size}, actual_size={self.actual_size}'

class FnParam(SizedRefOrConst):
    def __init__(self, name, size, data_type):
        self.data_type = data_type
        super().__init__(name, size)

    def __str__(self) -> str:
        return f'{super().__str__()}, data_type={self.data_type}'

class Scalar(SizedRefOrConst):
    def __init__(self, name, value, static, size, data_type):
        self.value = value
        self.static = static
        self.data_type = data_type
        super().__init__(name, size)

class AddressSpace(SizedRefOrConst):
    def __init__(self, name, power, length, size, attributes):
        self._length = length
        self._power = power
        self.attributes = attributes if attributes else []
        super().__init__(name, size)

    @property
    def length(self):
        if isinstance(self._length, Constant):
            temp = self._length.value
        else:
            temp = self._length

        if self._power:
            return self._power ** temp
        else:
            return temp

    def __str__(self) -> str:
        return f'{super().__str__()}, size={self.size}, length={self.length}'

class InstructionSet(Named):
    def __init__(self, name, extension, constants, address_spaces, registers, instructions):
        self.extension = extension
        self.constants = constants
        self.address_spaces = address_spaces
        self.registers = registers
        self.instructions = instructions

        super().__init__(name)

class Register(SizedRefOrConst):
    def __init__(self, name, attributes, initval, size):
        self.attributes = attributes if attributes else []
        self._initval = initval

        super().__init__(name, size)

    @property
    def initval(self):
        if isinstance(self._initval, Constant):
            return self._initval.value
        else:
            return self._initval

class RegisterFile(SizedRefOrConst):
    def __init__(self, name, _range, attributes, size):
        self.range = _range
        self.attributes = attributes if attributes else []

        super().__init__(name, size)

class RegisterAlias(Register):
    def __init__(self, name, actual, index, attributes, initval, size):
        self.actual = actual
        self.index = index

        super().__init__(name, attributes, initval, size)

    def __str__(self) -> str:
        return f'{super().__str__()}, actual={self.actual}, index={self.index}'

class CoreDef(Named):
    def __init__(self, name, contributing_types, template, constants, address_spaces, register_files, registers, register_aliases, functions, instructions):
        self.contributing_types = contributing_types
        self.template = template
        self.constants = constants
        self.address_spaces = address_spaces
        self.register_files = register_files
        self.registers = registers
        self.register_aliases = register_aliases
        self.functions = functions
        self.instructions = instructions

        super().__init__(name)

class BitField(Named):
    def __init__(self, name, _range, data_type):
        self.range = _range
        self.data_type = data_type
        if not self.data_type: self.data_type = DataType.U

        super().__init__(name)

    def __str__(self) -> str:
        return f'{super().__repr__()}, range={self.range}, data_type={self.data_type}'

    def __repr__(self):
        return self.__str__()

class BitFieldDescr(Named):
    def __init__(self, name, size, data_type):
        self.size = size
        self.data_type = data_type
        self.upper = 0

        super().__init__(name)

class Instruction(SizedRefOrConst):
    def __init__(self, name, attributes, encoding, disass, operation):
        self.ext_name = ""
        self.attributes = attributes if attributes else []
        self.encoding = encoding
        self.fields = {}
        self.scalars = {}
        self.disass = disass
        self.operation = operation if operation is not None else Tree('operation', [])

        self.mask = 0
        self.code = 0

        super().__init__(name, 0)

        for e in reversed(self.encoding):
            if isinstance(e, BitField):
                self._size += e.range.length

                if e.name in self.fields:
                    f = self.fields[e.name]
                    if f.data_type != e.data_type:
                        raise ValueError(f'non-matching datatypes for BitField {e.name} in instruction {name}')
                    f.size += e.range.upper - e.range.lower + 1
                else:
                    f = BitFieldDescr(e.name, e.range.upper - e.range.lower + 1, e.data_type)
                    self.fields[e.name] = f
            else:
                self.mask |= (2**e.length - 1) << self._size
                self.code |= e.value << self._size

                self._size += e.length

    def __str__(self) -> str:
        code_and_mask = 'code={code:#x{size}}, mask={mask:#x{size}}'.format(code=self.code, mask=self.mask, size=self.size)
        return f'{super().__str__()}, ext_name={self.ext_name}, {code_and_mask}'

class Function(SizedRefOrConst):
    def __init__(self, name, return_len, data_type, args, operation):
        self.data_type = data_type
        self.args = {arg.name: arg for arg in args}
        self.operation = operation if operation is not None else Tree('operation', [])

        super().__init__(name, return_len)

    def __str__(self) -> str:
        return f'{super().__str__()}, data_type={self.data_type}'

class Expression:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
