
from enum import Enum, IntEnum, auto, IntFlag
from dataclasses import dataclass

class MemoryAttribute(Enum):
	IS_MAIN_MEM = auto()
	IS_CSR_REG = auto()
	DELETE = auto()
	ETISS_CAN_FAIL = auto()
	ETISS_IS_GLOBAL_IRQ_EN = auto()
	ETISS_IS_IRQ_EN = auto()
	ETISS_IS_IRQ_PENDING = auto()
	ETISS_IS_PROCNO = auto()

class RegisterAttribute(Enum):
	IS_PC = auto()
	IS_MAIN_REG = auto()
	IS_FLOAT_REG = auto()
	IS_VECTOR_REG = auto()

class FunctionAttribute(Enum):
	ETISS_STATICFN = auto()
	ETISS_NEEDS_ARCH = auto()
	ETISS_TRAP_ENTRY_FN = auto()
	ETISS_TRAP_TRANSLATE_FN = auto()

class FunctionThrows(IntEnum):
	NO = 0
	YES = 1
	MAYBE = 2

class ConstAttribute(Enum):
	IS_REG_WIDTH = auto()
	IS_ADDR_WIDTH = auto()

class InstrAttribute(Enum):
	NO_CONT = auto()
	COND = auto()
	FLUSH = auto()
	SIM_EXIT = auto()
	ENABLE = auto()
	ETISS_ERROR_INSTRUCTION = auto()


class AccessAttribute(IntFlag):
	"""Describes the staticness of a Scalar or Function"""

	NONE = 0 #no access at all
	READ = auto() # read access only
	WRITE = auto() # write access only
	RW = READ | WRITE

@dataclass
class AccessContext:
	"""A datakeeping class for the var staticness transformations."""

	access_is_static: AccessAttribute = AccessAttribute.RW

class Qualifier(IntFlag):
    NONE = 0
    CONST = auto()
    STATIC = auto()
