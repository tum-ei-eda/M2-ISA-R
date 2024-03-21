"""Named Tuple containing information about instruction legalization needed by Seal5"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import yaml

from .operands import Operand


@dataclass
class GMIRLegalization:
	"""Class to collect the legalization information needed by Seal5"""

	name: list[str]
	types: list[str]

	def __add__(self, other):
		"""Combines two Legalizations"""
		names = self.name + [n for n in other.name if n not in self.name]
		types = self.types + [t for t in other.types if t not in self.types]
		return GMIRLegalization(name=names, types=types)


def operand_types(operands: dict[str, Operand]) -> list[str]:
	"""Creates a list of types that need to be legalized, entries are unique"""
	# TODO i need to adapt this for simd, maybe an optional parameter which adds vXsY

	return list(
		{"s" + str(operand.width) for name, operand in operands.items() if name != "rd" and not operand.immediate}
	)


def legalization_signdness(operands: dict[str, Operand]) -> Literal["S", "U"]:
	"""Returns the type needed for the GMIR legalization"""
	return (
		"S"
		if any(
			"s" in operand.sign.lower()
			for name, operand in operands.items()
			if name != "rd"
		)
		else "U"
	)


def arithmetic_legalization(
	operands: dict[str, Operand], operator: str
) -> Optional[GMIRLegalization]:
	"""Create legalization for basic arithmetic operators"""
	types = operand_types(operands)
	for ty in types:
		if "32" in ty:
			types.remove(ty)
	sign = legalization_signdness(operands)

	op_dict = {
		"+": ["G_ADD"],
		"-": ["G_SUB"],
		"*": ["G_MUL"],
		"/": [f"G_{sign}DIV"],
		"%": [f"G_{sign}REM"],
		"&": ["G_AND"],
		"|": ["G_OR"],
		"^": ["G_XOR"],
	}
	if types:
		return GMIRLegalization(op_dict[operator], types)
	return None


def save_legalizations_yaml(
	extension: str, legalizations: dict[str, list[GMIRLegalization]], path: Path
):
	"""Save a yaml file with new legalizations for Seal5"""

	legalized_ops: list[dict] = []
	for ext_name, legs in legalizations.items():
		for leg in legs:
			fixed_name = ext_name.lower().replace("_", "")
			legalized_ops.append(
				{
					"name": leg.name,
					"types": leg.types,
					"onlyif": ["HasVendor" + fixed_name],
				}
			)

	content = {"riscv": {"legalization": {"gisel": {"ops": legalized_ops}}}}

	with open(path / "legalizations.yaml", "w", encoding="utf-8") as file:
		yaml.safe_dump(content, file)


def save_extensions_yaml(
	extension_name: str,
	extensions: list[str],
	ext_prefix: Optional[str],
	path: Path,
):
	"""Create the config file needed by seal5 containing the extension information"""
	content = {
		"extensions": {},
		"passes": {"per_model": {}},
	}

	if ext_prefix is None:  # TODO this is currently not used
		ext_prefix = extension_name

	for ext in extensions:
		content["extensions"][ext] = {
			"arch": "x" + ext.lower().replace("_", ""),
			"experimental": False,
			"feature": ext.replace(
				"_", ""
			),  # TODO replace the full name with the prefix
			"vendor": True,
			"version": "1.0",
		}

	with open(path / (extension_name + ".yaml"), "w", encoding="utf-8") as file:
		yaml.safe_dump(content, file)
