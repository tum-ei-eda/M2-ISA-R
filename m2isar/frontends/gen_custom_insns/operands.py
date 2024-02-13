"""Operands used in parsing the instructions"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

from ...metamodel import arch, behav

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

	def to_metamodel_ref(
		self, name: str
	) -> Union[behav.IndexedReference, behav.NamedReference, behav.TypeConv]:
		"""
		Creating a M2-ISA-R Metamodel Reference or SliceOperation used in modeling operations\n
		If the operands width is smaller than XLEN a SliceOperation will be returned instead
		This can be turned off, by setting "slicing" to False, which is needed when creating simd slices
		"""
		registers = arch.Memory(
			"X", arch.RangeSpec(32), 32, {arch.MemoryAttribute.IS_MAIN_MEM: []}
		)
		sign = arch.DataType.S if self.sign == "s" else arch.DataType.U

		if self.immediate:
			ref = behav.NamedReference(
				arch.BitFieldDescr(
					name,
					self.width,
					sign,
				)
			)
		else:
			ref = behav.IndexedReference(
				reference=registers,
				index=behav.NamedReference(
					arch.BitFieldDescr(
						name,
						5,
						sign,
					)
				),
			)

		# The destination register is not typecast in CoreDSL as it gets deduced from the operands
		if name not in ("rd", "rD"):
			if self.width < XLEN or sign is arch.DataType.S:
				ref = behav.TypeConv(sign, self.width, ref)

		return ref

	def to_simd_slices(self, name: str) -> List[behav.SliceOperation]:
		"""Returns a list of SliceOperations on register['name']"""
		if XLEN % self.width != 0:
			raise ValueError(
				f"Operands width(={self.width}) can't be packed into XLEN(={XLEN})!"
			)
		if self.immediate:
			raise TypeError("Immediate slicing is not supported!")

		lanes = XLEN // self.width
		slices = []
		for l in range(lanes):
			left_index = behav.IntLiteral(self.width * (1 + l) - 1)
			right_index = behav.IntLiteral(self.width * l)
			slices.append(
				behav.SliceOperation(
					self.to_metamodel_ref(name), left_index, right_index
				)
			)

		return slices


def get_immediates(operands: Dict[str, Operand]) -> List[Operand]:
	"""returns a subset of the given operands that are immediates"""
	return [operand for operand in operands.values() if operand.immediate]


def get_immediates_with_name(operands: Dict[str, Operand]) -> List[Tuple[str, Operand]]:
	"""returns a list of tuples, with immediate operands and their name"""
	return [(name, operand) for name, operand in operands.items() if operand.immediate]


def simplify_operands(operands: Dict[str, ComplexOperand]) -> Dict[str, List[Operand]]:
	"""
	Simplifying the operands, returns a list where
	the ComplexOperands have been turned into simple Operands with only 1 sign and width
	Width or sign references need to be resolved once the operands are put into groups
	"""
	operand_lists: Dict[str, List[Operand]] = {}
	for operand_name, operand in operands.items():
		operand_lists[operand_name] = []
		imm = operand.immediate
		for index, w in enumerate(operand.width):
			# option 1: sign is specified per width
			if len(operand.sign) == len(operand.width):
				if operand.sign[index] in ("us", "su"):
					operand_lists[operand_name].extend(
						[Operand(w, "u", imm), Operand(w, "s", imm)]  # type: ignore
					)
				else:
					operand_lists[operand_name].append(Operand(w, operand.sign[index], imm))  # type: ignore
			elif len(operand.sign) > 1:
				raise ValueError(
					"Number of specified signs neither matches the number of widths nor is 1"
				)
			# option 2: only 1 sign, so its the same for all widths
			elif operand.sign[0] in ("us", "su"):
				operand_lists[operand_name].extend([Operand(w, "u", imm), Operand(w, "s", imm)])  # type: ignore
			else:
				operand_lists[operand_name].append(Operand(w, operand.sign[0], imm))  # type: ignore
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
