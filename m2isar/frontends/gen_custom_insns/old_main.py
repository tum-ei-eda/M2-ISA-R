# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import argparse
import itertools
import logging
import pathlib
import pickle
import sys

import m2isar
from ... import M2Error, M2SyntaxError
from ...metamodel import arch, behav, patch_model
# from . import expr_interpreter
# from .architecture_model_builder import ArchitectureModelBuilder
# from .behavior_model_builder import BehaviorModelBuilder
# from .importer import recursive_import
# from .load_order import LoadOrder
# from .utils import make_parser


def main():
	parser = argparse.ArgumentParser()
	# parser.add_argument("top_level", help="The top-level CoreDSL file.")
	parser.add_argument("--output", "-o", default="generated.m2isarmodel", help="Output path of generated .m2isarmodel")
	parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])

	args = parser.parse_args()
	model_path = args.output

	# setup logging
	logging.basicConfig(level=getattr(logging, args.log.upper()))
	logger = logging.getLogger("parser")

	# Generate main memory and register file
	main_reg = m2isar.metamodel.arch.Memory("X", m2isar.metamodel.arch.RangeSpec(32), size=32, attributes={m2isar.metamodel.arch.MemoryAttribute.IS_MAIN_REG: []})
	main_mem = m2isar.metamodel.arch.Memory("MEM", m2isar.metamodel.arch.RangeSpec(1 << 32), size=8, attributes={m2isar.metamodel.arch.MemoryAttribute.IS_MAIN_MEM: []})
	pc = m2isar.metamodel.arch.Memory("PC", m2isar.metamodel.arch.RangeSpec(0), size=32, attributes={m2isar.metamodel.arch.MemoryAttribute.IS_PC: []})
	memories = {"X": main_reg, "MEM": main_mem, "PC": pc}
	constants = {"XLEN": m2isar.metamodel.arch.Constant("XLEN", value=32, attributes={}, size=None, signed=False)}
	functions = {}
	intrinsics = {}

	# Create new instruction (ADDI with imm hardcoded to 42)
	# encoding
	opcode = m2isar.metamodel.arch.BitVal(7, 0b0010011)
	rd = m2isar.metamodel.arch.BitField("rd", m2isar.metamodel.arch.RangeSpec(4, 0), m2isar.metamodel.arch.DataType.U)
	func3 = m2isar.metamodel.arch.BitVal(3, 0b000)
	rs1 = m2isar.metamodel.arch.BitField("rs1", m2isar.metamodel.arch.RangeSpec(4, 0), m2isar.metamodel.arch.DataType.U)
	imm = m2isar.metamodel.arch.BitField("imm", m2isar.metamodel.arch.RangeSpec(11, 0), m2isar.metamodel.arch.DataType.U)
	encoding = [imm, rs1, func3, rd, opcode]
	# assembly
	disass = "{name(rd)}, {name(rs1)}, {imm}"# FIXME: specify mnemonic
	# operation
	rd_desc = m2isar.metamodel.arch.BitField("rd", 5, m2isar.metamodel.arch.DataType.U)
	rs1_desc = m2isar.metamodel.arch.BitField("rs1", 5, m2isar.metamodel.arch.DataType.U)
	op = m2isar.metamodel.behav.Operation(
		[
			m2isar.metamodel.behav.Assignment(
				m2isar.metamodel.behav.IndexedReference(
					memories["X"],
					m2isar.metamodel.behav.NamedReference(rd_desc),
				),
				m2isar.metamodel.behav.BinaryOperation(
					m2isar.metamodel.behav.IndexedReference(
						memories["X"],
						m2isar.metamodel.behav.NamedReference(rs1_desc),
					),
					m2isar.metamodel.behav.Operator("+"),
					m2isar.metamodel.behav.IntLiteral(42),
				),
			)
		]
	)
	insn = m2isar.metamodel.arch.Instruction("MyInst", attributes={}, encoding=encoding, disass=disass, operation=op)
	insn.ext_name = "MySet"
	instructions = {(insn.mask, insn.code): insn}

	# Create new instruction set (single instruction)
	# i = arch.InstructionSet("MySet", [], constants, memories, functions, instructions)
	# FIXME: The actual instruction sets usually get merged into the CoreDef while parsing which is not great

	# Create dummy core (32-bit)
	name = "MyCore"
	contributing_types = ["MySet"]
	template = None
	memory_aliases = {}
	instr_classes = {32}
	core = m2isar.metamodel.arch.CoreDef(name, contributing_types, template, constants, memories, memory_aliases, functions, instructions, instr_classes, intrinsics)

	# Export metamodel
	models = {"MyCore": core}
	logger.info("dumping model")
	with open(model_path, 'wb') as f:
		pickle.dump(models, f)

if __name__ == '__main__':
	main()
