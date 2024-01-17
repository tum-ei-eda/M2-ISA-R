"""Classes used to turn the parsed input into M2-ISA-R Metamodel"""

from dataclasses import dataclass
from typing import List, Dict, Union

from ...metamodel import arch
from .op_parsing import parse_op
from .operands import Operand, ComplexOperand, simplify_operands, create_operand_combinations

from .instr_encodings import get_mm_encoding


@dataclass
class Instruction:
	"""A single Instructions which can be turned into the M2-ISA Metamodel"""

	name: str
	op: str  # will later be changed to an object of the operand class
	operands: Dict[str, Operand]

	def format_name(self) -> None:
		"""Formates the instruction name using the operands"""
		self.name = self.name.format(**self.operands)

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

	def to_metamodel(self) -> arch.Instruction:
		"""Transforms this Instruction into a M2-ISA-R Metamodel Instruction"""
		name = self.name

		try:
			encoding = get_mm_encoding(self.operands)
		except (NotImplementedError, ValueError) as e:
			print(f"Could not find a fitting encoding for instruction {self.name}!")
			raise RuntimeError() from e

		extension_name = ""  # TODO pass extension name as argument
		mnemonic = extension_name + "." + self.name

		assembly = ""
		for n in self.operands.keys():
			assembly += "{name(" + n + ")}, "
		assembly = assembly[0:-2]  # removing the trailing ", "

		operation = parse_op(operands=self.operands, name=self.op)

		return arch.Instruction(
			name=name,
			attributes={},
			encoding=encoding,
			mnemonic=mnemonic,
			assembly=assembly,
			operation=operation,
		)


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
		name="adds32",
		op="add",
		operands={
			"rs1": Operand(width=32, sign="s"),
			"rs2": Operand(width=32, sign="s"),
			"rd": Operand(32, "s"),
		},
	)

	test = instr.to_metamodel()

	print(test)
