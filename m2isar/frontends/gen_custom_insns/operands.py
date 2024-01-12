"""Operands used in parsing the instructions"""
from typing import Union, List, Dict
from dataclasses import dataclass
from copy import deepcopy

from ...metamodel import behav, arch

XLEN = 32  # Could be changed later to support rv64

@dataclass(init=False)
class ComplexOperand:
	"""A Operand with a list of bitwidths and signs."""

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

	# width can only be str when operands references havn't been resolved yet
	width: int
	sign: str
	immediate: bool = False

	def to_metemodel_ref(
		self, name: str
	) -> Union[behav.IndexedReference, behav.NamedReference, behav.SliceOperation]:
		"""
		Creating a M2-ISA-R Metamodel Reference or SliceOperation use in modeling operations
		If the operands width is smaller than XLEN a SliceOperation will be returned instead
		"""
		if self.immediate:
			return behav.NamedReference(
				behav.BitFieldDescr(
					name,
					self.width,
					arch.DataType.S if self.sign == "s" else arch.DataType.U,
				)
			)

		registers = arch.Memory(
			"X", arch.RangeSpec(32), 32, {arch.MemoryAttribute.IS_MAIN_MEM: []}
		)
		ref = behav.IndexedReference(
			reference=registers,
			index=behav.NamedReference(
				arch.BitFieldDescr(
					name,
					5,
					arch.DataType.S if self.sign == "s" else arch.DataType.U,
				)
			),
		)

		if self.width < XLEN:
			ref = behav.SliceOperation(ref, behav.IntLiteral(self.width - 1), behav.IntLiteral(0))
		return ref

	def to_simd_slices(self, name: str) -> List[behav.SliceOperation]:
		"""Returns a list of SliceOperations on register['name']"""
		if XLEN % self.width != 0:
			raise ValueError(f"Operands width(={self.width}) can't be packed into XLEN(={XLEN})!")
		if self.immediate:
			raise TypeError("Immediate slicing is not supported!")

		lanes = XLEN // self.width
		slices = []
		for l in range(lanes):
			left_index = behav.IntLiteral(self.width * (1 + l) - 1)
			right_index = behav.IntLiteral(self.width * l)
			slices.append(behav.SliceOperation(self.to_metemodel_ref(name), left_index, right_index))

		return slices


def simplify_operands(operands: Dict[str, ComplexOperand]) -> Dict[str, List[Operand]]:
	"""
	Simplifying the operands, returns a list where
	the ComplexOperands have been turned into simple Operands with only 1 sign and width
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
			elif len(operand.sign) > 1:
				raise ValueError(
					"Number of specified signs neither matches the number of widths nor is 1"
				)
			# option 2: only 1 sign, so its the same for all widths
			elif operand.sign[0] in ("us", "su"):
				operand_lists[operand_name].extend([Operand(w, "u"), Operand(w, "s")])
			else:
				operand_lists[operand_name].append(Operand(w, operand.sign[0]))
	return operand_lists


def create_operand_combinations(
	operand_lists: Dict[str, List[Operand]]
) -> List[Dict[str, Operand]]:
	"""Create every possible combination of the supplied operands"""
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
