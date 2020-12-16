from enum import Enum, auto

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
