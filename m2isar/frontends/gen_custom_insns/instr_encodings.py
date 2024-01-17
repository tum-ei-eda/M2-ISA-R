"""
This module will create Objects on import which are used to generate Opcodes for custom instructions

Currently this only includes Greenfield instructions and
only uses the major opcodes Custom[0-3] as specified by the RISC-V standart

This could be changed in the future by adding a function which adds unused opcodes to the list
"""

from typing import Dict, List, Union
from dataclasses import dataclass

from ...metamodel import arch
from .operands import Operand, get_immediates


# only using the major op-codes custom-[0,3] as specified in table 19.1 in "Volume I: RISC-V User-Level ISA V2.2"
# bits 1:0 are always 11; 00, 01 and 10 are used by the compressed instructions
# bits 4:2 = 111 could be used if we decide to limit the usage to 32 bit instrucions/rv32
unused_opcodes = [0b000_1011, 0b010_1011, 0b101_1011, 0b111_1011]
# If the opcodes dont need to be standart compatible, 
# this list could be extended at runtime with the opcodes of the unused extensions

# R-Format: funct7 | rs2 | rs1 | funct3 | rd | opcode
# 			 31:25 |24:20|19:15| 14:12  |11:7| 6:0
# 1 opcode => 2^(7+3)= 1024 possilbe instructions
#
# I-Format: imm   | rs1 | func3 | rd | opcode
# 			31:20 |19:15| 14:12 |11:7| 6:0
# 1 opcode => 2^(3)= 8 possilbe instructions


@dataclass
class BaseOpcode:
	"""Dataclass to store and get the next free opcode and funct3"""

	opcode: int = 0
	funct3: int = 0

	def get(self) -> tuple[int, int]:
		"""
		Get a new opcode as a tuple of (minor, major) opcode,
		Returns (funct3, opcode)
		"""
		# checking if there are minor opcodes left or the major opcode is unset
		if self.funct3 > MAX_FUNCT3 or self.opcode == 0:
			try:
				self.opcode = unused_opcodes.pop()
			except IndexError as e:
				raise RuntimeError("No Major opcode left!") from e

		funct3 = self.funct3
		self.funct3 += 1
		return (funct3, self.opcode)


@dataclass
class RFormatOpcode(BaseOpcode):
	"""Extending the Base Opcode class to generate R-Format opcodes"""

	current_funct3: Union[int, None] = None
	funct7: int = 0

	def get(self) -> tuple[int, int, int]:
		if self.current_funct3 is None or self.funct7 > MAX_FUNCT7:
			self.funct3, self.opcode = super().get()
			self.funct7 = 0

		funct7 = self.funct7
		self.funct7 += 1

		return (funct7, self.funct3, self.opcode)

MAX_FUNCT7 = 0b111_1111
MAX_FUNCT3 = 0b111

r_opcodes = RFormatOpcode()
i_opcodes = BaseOpcode()


def get_mm_encoding(
	operands: Dict[str, Operand]
) -> List[Union[arch.BitField, arch.BitVal]]:
	"""
	Finds the next available Opcode and creates the encoding for use with the m2isar metamodel
	"""
	# figure out the format
	immediates = get_immediates(operands)
	imm_count = len(immediates)
	reg_count = len(operands) - imm_count

	if imm_count > 1:
		raise NotImplementedError(
			"Currently instructions with more than two immediates are not supported!"
		)
	if imm_count == 1:
		# if its 5 bits or smaller we can use the R-Format and use rs2 as imm field
		# this is the encoding for e.g. cv.clip
		if immediates[0].width <= 5:
			# R-Format: funct7 | rs2 | rs1 | funct3 | rd | opcode
			funct7, funct3, opcode = r_opcodes.get()
			imm_sign = arch.DataType.S if immediates[0].sign == "s" else arch.DataType.U
			return [
				arch.BitVal(7, funct7),
				arch.BitField("imm5", arch.RangeSpec(11, 0), imm_sign),
				reg_bitfield("rs1"),
				arch.BitVal(3, funct3),
				reg_bitfield("rd"),
				arch.BitVal(7, opcode),
			]
		if immediates[0].width > 12:
			raise ValueError(f"Bitwidth(={immediates[0].width}) of the immediate is too large!")

		# otherwise we just use the I-Format
		# I-Format: imm12 | rs1 | funct3 | rd | opcode
		funct3, major = i_opcodes.get()
		imm_sign = arch.DataType.S if immediates[0].sign == "s" else arch.DataType.U
		return [
			arch.BitField("imm12", arch.RangeSpec(11, 0), imm_sign),
			reg_bitfield("rs1"),
			arch.BitVal(3, funct3),
			reg_bitfield("rd"),
			arch.BitVal(7, major),
		]

	if reg_count == 3:
		# R-Format: funct7 | rs2 | rs1 | funct3 | rd | opcode
		funct7, funct3, major = r_opcodes.get()
		return [
			arch.BitVal(7, funct7),
			reg_bitfield("rs2"),
			reg_bitfield("rs1"),
			arch.BitVal(3, funct3),
			reg_bitfield("rd"),
			arch.BitVal(7, major),
		]
	if len(operands) == 2:
		# no imm's and only 2 regs, e.g. cv.abs -> just set rs2 to 0
		# R-Format: funct7 | rs2 | rs1 | funct3 | rd | opcode
		funct7, funct3, major = r_opcodes.get()
		return [
			arch.BitVal(7, funct7),
			arch.BitVal(5, 0),
			reg_bitfield("rs1"),
			arch.BitVal(3, funct3),
			reg_bitfield("rd"),
			arch.BitVal(7, major),
		]

	raise NotImplementedError("Unknown instruction format!")


def reg_bitfield(name: str) -> arch.BitField:
	"""
	Helper funtion to reduce boilerplate code
	Returns a BitField Object with the specified name"""
	return arch.BitField(name, arch.RangeSpec(4, 0), arch.DataType.U)
