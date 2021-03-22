from enum import Enum, auto
from typing import Iterable, Union


class Named:
    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f'<{type(self).__name__} object>: name={self.name}'

    def __repr__(self) -> str:
        return f'<{type(self).__name__} object>: name={self.name}'

class Constant(Named):
    def __init__(self, name, value: int, attributes: Iterable[str]):
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


class RangeSpec:
    def __init__(self, upper_base: val_or_const, lower_base: val_or_const, upper_power: val_or_const=1, lower_power: val_or_const=1):
        self._upper_base = upper_base
        self._lower_base = lower_base

        self._upper_power = upper_power
        self._lower_power = lower_power

    @property
    def upper_power(self):
        if isinstance(self._upper_power, Constant):
            return self._upper_power.value
        return self._upper_power

    @property
    def lower_power(self):
        if isinstance(self._lower_power, Constant):
            return self._lower_power.value
        return self._lower_power

    @property
    def upper_base(self):
        if isinstance(self._upper_base, Constant):
            return self._upper_base.value
        return self._upper_base

    @property
    def lower_base(self):
        if isinstance(self._lower_base, Constant):
            return self._lower_base.value
        return self._lower_base

    @property
    def upper(self):
        return self.upper_base ** self.upper_power

    @property
    def lower(self):
        return self.lower_base ** self.lower_power

    @property
    def length(self):
        return self.upper - self.lower + 1

    def __str__(self) -> str:
        return f'<RangeSpec object>, len {self.length}: {self.upper_base}:{self.lower_base}'

class MemoryAttribute(Enum):
    IS_PC = auto()
    IS_MAIN_MEM = auto()
    IS_MAIN_REG = auto()

class RegAttribute(Enum):
    IS_PC = auto()
    DELETE = auto()
    IS_MAIN_REG = auto()

class SpaceAttribute(Enum):
    IS_MAIN_MEM = auto()

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
