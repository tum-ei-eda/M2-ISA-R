"""Classes used to turn the parsed input into M2-ISA-R Metamodel"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from ...metamodel import arch
from .instr_encodings import get_mm_encoding
from .op_parsing import parse_op
from .operands import (
	ComplexOperand,
	Operand,
	create_operand_combinations,
	simplify_operands,
)
from .seal5_support import GMIRLegalization


@dataclass
class Instruction:
	"""A single Instructions which can be turned into the M2-ISA Metamodel"""

	name: str
	op: str  # will later be changed to an object of the operand class
	operands: Dict[str, Operand]

	def format_name(self) -> None:
		"""Formates the instruction name using the operands"""
		# TODO build dict for format, which has width as ".b"/".h"
		self.name = self.name.format(**self.operands, op=self.op)

	def resolve_references(self) -> None:
		"""Resolves references to other operands"""
		for operand_name, operand in self.operands.items():
			# catching self references
			if operand_name in (operand.sign, operand.width):
				raise RuntimeError("Self reference in operand detected!")

			if operand.sign in self.operands.keys():
				if self.operands[operand.sign].sign in self.operands.keys():
					raise TypeError("Referencing another reference is not implemented!")
				operand.sign = self.operands[operand.sign].sign

			if operand.width in self.operands.keys():
				# ignoring the typing warnings as they can only be str if its in keys
				if self.operands[operand.width].width in self.operands.keys():  # type: ignore
					raise TypeError("Referencing another reference is not implemented!")
				operand.width = self.operands[operand.width].width  # type: ignore

	def to_metamodel(
		self, instruction_prefix: Optional[str] = None
	) -> tuple[arch.Instruction, Optional[GMIRLegalization]]:
		"""Transforms this Instruction into a M2-ISA-R Metamodel Instruction"""
		try:
			try:
				encoding = get_mm_encoding(self.operands)
			except (NotImplementedError, ValueError) as e:
				raise RuntimeError(
					f"Could not find a fitting encoding for instruction {self.name}!"
				) from e

			prefix = instruction_prefix + "." if instruction_prefix else ""
			mnemonic = prefix + self.name

			# Registers Assembly strings
			operand_names = [
				f"{{name({name})}}"
				for name, operand in self.operands.items()
				if not operand.immediate
			]
			operand_names.sort()
			# Immediates
			operand_names.extend(
				[
					f"{{{name}}}"
					for name, operand in self.operands.items()
					if operand.immediate
				]
			)
			assembly = ", ".join(operand_names)
			operation, legalization = parse_op(operands=self.operands, name=self.op)
		except Exception as e:
			raise RuntimeError("Failed to generate Metamodel Instruction!\n"
					  f"Operands: {self.operands}\n"
					  f"Op: {self.op}") from e

		return (arch.Instruction(
			name=self.name,
			attributes={},
			encoding=encoding,
			mnemonic=mnemonic,
			assembly=assembly,
			operation=operation,
		), legalization)


class InstructionCollection:
	"""A set of Instructions which can be turned
	into single instructions using the generate method"""

	def __init__(
		self, name: str, ops: Union[str, List], operands: Dict[str, ComplexOperand]
	) -> None:
		self.name: str = name
		self.ops: List[str] = ops if isinstance(ops, list) else [ops]
		self.operands: Dict[str, ComplexOperand] = operands

	def generate(self) -> List[Instruction]:
		"""Generating a list of unique instructions from the instruction specification"""
		# First, generating simpler operands
		# which only have a single sign and width
		operand_lists: Dict[str, List[Operand]] = simplify_operands(self.operands)

		# Second, generate all possible combinations
		operand_combinations: List[Dict[str, Operand]] = create_operand_combinations(
			operand_lists
		)

		# Third, create an instruction object for each op
		instructions: List[Instruction] = []
		for op in self.ops:
			instruction_ops = [
				Instruction(self.name, op, operands)
				for operands in operand_combinations
			]
			instructions.extend(instruction_ops)

		# Finaly, format names and resolve operand references
		for inst in instructions:
			inst.resolve_references()
			inst.format_name()

		return instructions


if __name__ == "__main__":
	# Just used for debuging
	instr = Instruction(
		name="simd_test",
		op="simd_add",
		operands={
			"rs1": Operand(width=8, sign="s"),
			"rs2": Operand(width=8, sign="s"),
			"rd": Operand(8, "s"),
		},
	)

	test = instr.to_metamodel("test")

	print(test)
