from enum import Enum, auto
from collections import defaultdict, namedtuple

RangeSpec = namedtuple('RangeSpec', ['upper', 'lower'])
BitVal = namedtuple('BitVal', ['length', 'value'])

class RegAttribute(Enum):
    IS_PC = auto()
    DELETE = auto()

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

class Constant(Named):
    def __init__(self, name, value, attributes):
        self.value = value
        self.attributes = attributes
        super().__init__(name)

class SizedRefOrConst(Named):
    def __init__(self, name, size=None):
        self._size = size
        super().__init__(name)

    @property
    def size(self):
        if isinstance(self._size, Constant):
            return self._size.value
        else:
            return self._size

class Scalar(SizedRefOrConst):
    def __init__(self, name, value=None, size=None):
        self.value = value
        super().__init__(name, size)

class AddressSpace(SizedRefOrConst):
    def __init__(self, name, power, length, size=None):
        self._length = length
        self._power = power
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
        self.attributes = attributes
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
        self.attributes = attributes

        super().__init__(name, size)

class RegisterAlias(Register):
    def __init__(self, name, actual, index, attributes, initval, size):
        self.actual = actual
        self.index = index

        super().__init__(name, attributes, initval, size)

class CoreDef(Named):
    def __init__(self, name, contributing_types, template, constants, address_spaces, register_files, registers, register_aliases, instructions):
        self.contributing_types = contributing_types
        self.template = template
        self.constants = constants
        self.address_spaces = address_spaces
        self.register_files = register_files
        self.registers = registers
        self.register_aliases = register_aliases
        self.instructions = instructions

        super().__init__(name)

class BitField(Named):
    def __init__(self, name, _range, data_type):
        self.range = _range
        self.data_type = data_type
        if not self.data_type: self.data_type = DataType.U

        super().__init__(name)
    
    def __repr__(self):
        return f'BitField[{self.name}: {self.range} ({self.data_type})]'

class Instruction(Named):
    def __init__(self, name, attributes, encoding, disass, operation):
        self.attributes = attributes
        self.encoding = encoding
        self.fields = defaultdict(list)
        self.scalars = {}
        self.disass = disass
        self.operation = operation
        
        for e in self.encoding:
            if isinstance(e, BitField):
                self.fields[e.name].append(e)
        
        super().__init__(name)

class Expression:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right