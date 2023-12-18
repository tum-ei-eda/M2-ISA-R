"""Classes used to turn the parsed input into M2-ISA-R Metamodel"""

from dataclasses import dataclass
from typing import List, Dict, Union
from copy import deepcopy


from ...metamodel import arch, behav
from .op_parsing import parse_op


@dataclass(init=False)
class ComplexOperand:
	"""A Operand with a list of bitwidths and signs"""

	def __init__(
		self,
		width: Union[Union[int, str], List[Union[int, str]]],
		sign: Union[str, List[str]],
		immediate: bool = False,
	) -> None:
		self.width = width if isinstance(width, list) else [width]
		self.sign: List[str] = sign if isinstance(sign, list) else [sign]
		self.immediate: bool = immediate


@dataclass
class Operand:
	"""A simple operand used in the Instruction Class"""

	# width can only be str when the references havn't been resolved yet
	width: Union[int, str]
	sign: str
	immediate: bool = False


def simplify_operands(operands: Dict[str, ComplexOperand]) -> Dict[str, List[Operand]]:
	"""Simplifying the operands, returns a list where
	the ComplexOperands have been turned into simple Operands
	with only 1 sign and width
	Width or sign references need to be resolved once the operands are put into groups
	"""
	operand_lists: Dict[str, List[Operand]] = {}
	for operand_name, operand in operands.items():
		operand_lists[operand_name] = []
		for index, w in enumerate(operand.width):
			# option 1: sign is specified per width
			if len(operand.sign) == len(operand.width):
				if operand.sign[index] in ("us", "su"):
					operand_lists[operand_name].extend(
						[Operand(w, "u"), Operand(w, "s")]
					)
				else:
					operand_lists[operand_name].append(Operand(w, operand.sign[index]))
				continue
			elif len(operand.sign) > 1:
				raise ValueError(
					"Number of specified signs neither matches the number of widths nor is 1"
				)
			# option 2: only 1 sign, so its the same for all widths
			if operand.sign[0] in ("us", "su"):
				operand_lists[operand_name].extend([Operand(w, "u"), Operand(w, "s")])
			else:
				operand_lists[operand_name].append(Operand(w, operand.sign[0]))
	return operand_lists


def create_operand_combinations(
	operand_lists: Dict[str, List[Operand]]
) -> List[Dict[str, Operand]]:
	"""Create every posible combination of the supplied operands"""
	operand_combinations: List[Dict[str, Operand]] = []
	for operand_name, operand_variants in operand_lists.items():
		if len(operand_combinations) == 0:
			# if the list is empty we need to create a first set of operands
			operand_combinations.extend(
				[{operand_name: oper} for oper in operand_variants]
			)
		else:
			# if we allready added the first operand,
			# we create a copy for each variant of the next operand
			list_copy = deepcopy(operand_combinations)
			for d in operand_combinations:
				# adding the first operand_variant to current list
				d[operand_name] = deepcopy(operand_variants[0])
			# if len == 1 the for loop wont get executed
			for i in range(1, len(operand_variants)):
				# adding copies with the remaining operator variants
				new_list = deepcopy(list_copy)
				for d in new_list:
					d[operand_name] = deepcopy(operand_variants[i])
				operand_combinations.extend(new_list)
	return operand_combinations


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

	def _reg_indexed_ref(self, reg_name: str) -> behav.IndexedReference:
		# TODO get memories of the dummy core from main.py
		registers = arch.Memory(
			"X", arch.RangeSpec(32), 32, {arch.MemoryAttribute.IS_MAIN_MEM: []}
		)
		return behav.IndexedReference(
			reference=registers,
			index=behav.NamedReference(
				arch.BitFieldDescr(
					reg_name,
					5,
					arch.DataType.S
					if self.operands[reg_name].sign == "s"
					else arch.DataType.U,
				)
			),
		)

	def to_metamodel(self) -> arch.Instruction:
		"""Transforms this Instruction into a M2-ISA-R Metamodel Instruction"""
		name = self.name
		encoding: List[Union[arch.BitField, arch.BitVal]] = []  # TODO
		disass = self.name  # TODO

		## Registers
		# currently no load and store support so we need only the registers, not main mem
		# TODO immediates
		registers = {
			reg_name: self._reg_indexed_ref(reg_name)
			for reg_name in self.operands.keys()
		}

		operands: Dict[str, Union[behav.IndexedReference, behav.NamedReference]] = {}

		for opr_name, opr in self.operands.items():
			if opr.immediate:
				operands[opr_name] = behav.NamedReference(
					behav.BitFieldDescr(
						opr_name,
						opr.width,  # type: ignore
						arch.DataType.S if opr.sign == "s" else arch.DataType.U,
					)
				)
			else:
				operands[opr_name] = self._reg_indexed_ref(opr_name)
		operation = parse_op(operands=registers, name=self.op)

		return arch.Instruction(
			name=name,
			attributes={},
			encoding=encoding,
			disass=disass,
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
