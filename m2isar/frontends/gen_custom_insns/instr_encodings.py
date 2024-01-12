"""
This module will create Objects on import which are used to generate Opcodes for custom instructions

Currently this only includes Greenfield instructions and
only uses the major opcodes Custom 0-3 as specified by the RISC-V standart 

This could be changed in the future by adding a function which adds unused opcodes to the list
"""

from typing import Dict, List, Union
from enum import Enum, auto
from dataclasses import dataclass

from ...metamodel import arch
from .operands import Operand


# only using the major op-codes custom-[0,3] as specified in table 19.1 in "Volume I: RISC-V User-Level ISA V2.2"
# bits 1:0 are always 11; 00, 01 and 10 are used by the compressed instructions
# bits 4:2 = 111 could be used if we decide to limit the usage to 32 bit instrucions/rv32
unused_opcodes = [0b00_010_11, 0b01_010_11, 0b10_110_11, 0b11_110_11]


class InstFormat(Enum):
	"""Instructions Format used by RISC-V instructions"""

	I = auto()
	R = auto()


# R-Format: funct7 | rs2 | rs1 | funct3 | rd | opcode
# 			 31:25 |24:20|19:15| 14:12  |11:7| 6:0
# 1 opcode => 2^(7+3)= 1024 possilbe instructions
#
# I-Format: imm   | rs1 | func3 | rd | opcode
# 			31:20 |19:15| 14:12 |11:7| 6:0
# 1 opcode => 2^(3)= 8 possilbe instructions

# This could be set as the value in the enum
# 	but this could cause problems if 2 encodings have the same amount of minor opcodes
max_minor_opcode = {InstFormat.I: 0b111, InstFormat.R: 0b11_1111_1111}


@dataclass
class Opcode:
	"""Simple Dataclass to store the next free opcode"""

	_instr_format: InstFormat
	_major: int = 0
	_minor: int = 0

	def get(self):
		"""
		Get a new opcode as a tuple of (minor, major) opcode,
		The Minor opcode gets returned as int and still has to be split up if needed by the format
		"""
		# checking if there are minor opcodes left or the major opcode is unset
		if self._minor > max_minor_opcode[self._instr_format] or self._major == 0:
			try:
				self._major = unused_opcodes.pop()
			except IndexError as e:
				raise RuntimeError(
					f"No Major opcode left for a new set of {self._instr_format} Format opcode!"
				) from e
		minor = self._minor
		self._minor += 1

		return (minor, self._major)


r_opcodes = Opcode(InstFormat.R)

i_opcodes = Opcode(InstFormat.I)


def get_mm_encoding(
	operands: Dict[str, Operand]
) -> List[Union[arch.BitField, arch.BitVal]]:
	"""
	Finds the next available Opcode and creates the encoding for use with the m2isar metamodel
	Currently only works with instructions following the RISC-V Instructions Format
	"""
	# figure out the format
	if len(operands) == 3:
		if any(opr.immediate for opr in operands.values()):
			# I-Format: imm | rs1 | func3 | rd | opcode
			funct3, major = i_opcodes.get()

			return [
				arch.BitField("imm12", arch.RangeSpec(11, 0), arch.DataType.S),
				reg_bitfield("rs1"),
				arch.BitVal(3, funct3),
				reg_bitfield("rd"),
				arch.BitVal(7, major),
			]
		else:
			# R-Format: funct7 | rs2 | rs1 | funct3 | rd | opcode
			minor, major = r_opcodes.get()
			funct7 = minor | 0b11_1111_1000
			funct3 = minor | 0b111

			return [
				arch.BitVal(7, funct7),
				reg_bitfield("rs2"),
				reg_bitfield("rs1"),
				arch.BitVal(3, funct3),
				reg_bitfield("rd"),
				arch.BitVal(7, major),
			]
	else:
		raise NotImplementedError("Unknown instruction format!")


def reg_bitfield(name: str) -> arch.BitField:
	"""
	Helper funtion to reduce boilerplate code
	Returns a BitField Object with the specified name"""
	return arch.BitField(name, arch.RangeSpec(4, 0), arch.DataType.U)
