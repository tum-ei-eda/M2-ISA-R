"""
Unittests for the encoding generation
These tests currently only work when executed independently, and not when running all at once
This happens due to the fact that the encoding generator gets instantiated on import
and produces different results when calling it repeatedly
"""

import m2isar.frontends.gen_custom_insns.instr_encodings as enc_gen
from m2isar.frontends.gen_custom_insns.operands import Operand
from m2isar.metamodel import arch


def test_r_format_encoding():
	"""Testing if R-Format instructions generate a correct encoding"""
	enc_gen._reset_enc_generators()
	operands = {
		"rs1": Operand(width=16, sign="s"),
		"rs2": Operand(width=16, sign="s"),
		"rd": Operand(32, "s"),
	}
	encoding = enc_gen.get_mm_encoding(operands=operands)
	assert encoding[0].value == 0  # type: ignore
	assert encoding[1].name == "rs2"  # type: ignore
	assert encoding[2].name == "rs1"  # type: ignore
	assert encoding[3].value == 0  # type: ignore
	assert encoding[4].name == "rd"  # type: ignore
	assert encoding[5].value == 0b111_1011  # type: ignore


def test_multiple_r_formats():
	"""Testing if multiple R-Format instructions generate a correct encoding"""
	enc_gen._reset_enc_generators()
	operands = {
		"rs1": Operand(width=16, sign="s"),
		"rs2": Operand(width=16, sign="s"),
		"rd": Operand(32, "s"),
	}
	_ = enc_gen.get_mm_encoding(operands=operands)
	encoding2 = enc_gen.get_mm_encoding(operands=operands)
	assert encoding2[0].value == 1  # type: ignore
	assert encoding2[1].name == "rs2"  # type: ignore
	assert encoding2[2].name == "rs1"  # type: ignore
	assert encoding2[3].value == 0  # type: ignore
	assert encoding2[4].name == "rd"  # type: ignore
	assert encoding2[5].value == 0b111_1011  # type: ignore


def test_mixed_formats():
	"""Testing if mixed encoding formats get generated correctly"""
	enc_gen._reset_enc_generators()
	operands1 = {
		"rs1": Operand(width=16, sign="s"),
		"rs2": Operand(width=16, sign="s"),
		"rd": Operand(32, "s"),
	}
	operands2 = {
		"rs1": Operand(width=16, sign="s"),
		"imm12": Operand(width=12, sign="s", immediate=True),
		"rd": Operand(32, "s"),
	}
	encoding1 = enc_gen.get_mm_encoding(operands=operands1)
	assert encoding1[0].value == 0  # type: ignore
	assert encoding1[3].value == 0  # type: ignore
	assert encoding1[5].value == 0b111_1011  # type: ignore
	encoding2 = enc_gen.get_mm_encoding(operands=operands2)
	assert encoding2[2].value == 1  # type: ignore
	assert encoding2[4].value == 0b111_1011  # type: ignore
	encoding3 = enc_gen.get_mm_encoding(operands=operands1)
	assert encoding3[0].value == 1  # type: ignore
	assert encoding3[3].value == 0  # type: ignore
	assert encoding3[5].value == 0b111_1011  # type: ignore


def test_r_format_encodings_count():
	"""Testing if the correct amount of R-Format encodings are available"""
	enc_gen._reset_enc_generators()
	count = 0
	operands = {
		"rs1": Operand(width=16, sign="s"),
		"rs2": Operand(width=16, sign="s"),
		"rd": Operand(32, "s"),
	}

	while True:
		try:
			enc_gen.get_mm_encoding(operands)
			count += 1
		except RuntimeError:
			break
	assert count == 2**10 * 4


def test_i_format_encoding():
	"""Testing if I-Format encodings get generated correctly"""
	enc_gen._reset_enc_generators()
	operands = {
		"rs1": Operand(width=16, sign="s"),
		"imm12": Operand(width=12, sign="s", immediate=True),
		"rd": Operand(32, "s"),
	}
	encoding = enc_gen.get_mm_encoding(operands=operands)
	assert encoding[0].name == "imm12"  # type: ignore
	assert encoding[1].name == "rs1"  # type: ignore
	assert isinstance(encoding[2], arch.BitVal)
	assert encoding[2].value == 0  # type: ignore
	assert encoding[3].name == "rd"  # type: ignore
	assert isinstance(encoding[4], arch.BitVal)
	assert encoding[4].value == 0b111_1011  # type: ignore


def test_i_format_encodings_count():
	"""Testing if the correct amount of I-Format encodings are available"""
	enc_gen._reset_enc_generators()
	count = 0
	operands = {
		"rs1": Operand(width=16, sign="s"),
		"imm12": Operand(width=12, sign="s", immediate=True),
		"rd": Operand(32, "s"),
	}

	while True:
		try:
			enc_gen.get_mm_encoding(operands)
			count += 1
		except RuntimeError:
			break
	assert count == (2**3) * 4
