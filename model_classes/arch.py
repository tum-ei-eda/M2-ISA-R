from collections import namedtuple
from typing import Iterable, Sequence, Union, Mapping

from lark import Tree

from . import *


class Named:
    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f'<{type(self).__name__} object>: name={self.name}'

    def __repr__(self) -> str:
        return f'<{type(self).__name__} object>: name={self.name}'

class Constant(Named):
    def __init__(self, name, value: int, attributes: Sequence[str]):
        self.value = value
        self.attributes = attributes if attributes else []
        super().__init__(name)

    def __str__(self) -> str:
        return f'{super().__str__()}, value={self.value}'

val_or_const = Union[int, Constant]

class SizedRefOrConst(Named):
    def __init__(self, name, size: val_or_const):
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
    def __init__(self, name, size, data_type: DataType):
        self.data_type = data_type
        super().__init__(name, size)

    def __str__(self) -> str:
        return f'{super().__str__()}, data_type={self.data_type}'

class Scalar(SizedRefOrConst):
    def __init__(self, name, value: int, static: bool, size, data_type: DataType):
        self.value = value
        self.static = static
        self.data_type = data_type
        super().__init__(name, size)

class AddressSpace(SizedRefOrConst):
    def __init__(self, name, power: int, length: val_or_const, size, attributes: Iterable[SpaceAttribute]):
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

class Register(SizedRefOrConst):
    def __init__(self, name, attributes: Iterable[RegAttribute], initval: int, size):
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
    def __init__(self, name, _range: RangeSpec, attributes: Iterable[RegAttribute], size):
        self.range = _range
        self.attributes = attributes if attributes else []

        super().__init__(name, size)

class RegisterAlias(Register):
    def __init__(self, name, actual: str, index: int, attributes: Iterable[RegAttribute], initval: int, size):
        self.actual = actual
        self.index = index

        super().__init__(name, attributes, initval, size)

    def __str__(self) -> str:
        return f'{super().__str__()}, actual={self.actual}, index={self.index}'



BitVal = namedtuple('BitVal', ['length', 'value'])

class BitField(Named):
    def __init__(self, name, _range: RangeSpec, data_type: DataType):
        self.range = _range
        self.data_type = data_type
        if not self.data_type: self.data_type = DataType.U

        super().__init__(name)

    def __str__(self) -> str:
        return f'{super().__repr__()}, range={self.range}, data_type={self.data_type}'

    def __repr__(self):
        return self.__str__()

class BitFieldDescr(Named):
    def __init__(self, name, size: val_or_const, data_type: DataType):
        self.size = size
        self.data_type = data_type
        self.upper = 0

        super().__init__(name)

class Instruction(SizedRefOrConst):
    def __init__(self, name, attributes: Iterable[InstrAttribute], encoding: Iterable[Union[BitField, BitVal]], disass: str, operation: Tree):
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
    def __init__(self, name, return_len, data_type: DataType, args: Iterable[FnParam], operation):
        self.data_type = data_type
        self.args = {arg.name: arg for arg in args}
        self.operation = operation if operation is not None else Tree('operation', [])
        self.static = False

        super().__init__(name, return_len)

    def __str__(self) -> str:
        return f'{super().__str__()}, data_type={self.data_type}'

class InstructionSet(Named):
    def __init__(self, name, extension: Iterable[str], constants: Mapping[str, Constant], address_spaces: Mapping[str, AddressSpace], registers: Mapping[str, Register], instructions: Mapping[str, Instruction]):
        self.extension = extension
        self.constants = constants
        self.address_spaces = address_spaces
        self.registers = registers
        self.instructions = instructions

        super().__init__(name)

class CoreDef(Named):
    def __init__(self, name, contributing_types: Iterable[str], template: str, constants: Mapping[str, Constant], address_spaces: Mapping[str, AddressSpace], register_files: Mapping[str, RegisterFile], registers: Mapping[str, Register], register_aliases: Mapping[str, RegisterAlias], functions: Mapping[str, Function], instructions: Mapping[str, Instruction]):
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