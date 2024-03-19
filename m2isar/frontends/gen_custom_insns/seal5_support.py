"""Named Tuple containing information about instruction legalization needed by Seal5"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
	"""Gather a list of types that need to be legalized, entries are unique"""
	return list(
		{
			operand.sign + str(operand.width)
			for name, operand in operands.items()
			if name != "rd"
		}
	)


def save_legalizations_yaml(
	extension: str, legalizations: dict[str, list[GMIRLegalization]], path: Path
):
	"""Save a yaml file with new legalizations for Seal5"""

	legalized_ops: list[dict] = []
	for ext_name, legs in legalizations.items():
		for leg in legs:
			legalized_ops.append(
				{"name": leg.name, "types": leg.types, "onlyif": ["HasExt" + ext_name]}
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
	if ext_prefix is None:
		ext_prefix = extension_name

	for ext in extensions:
		content["extensions"][ext] = {
			"feature": ext,  # TODO replace the full name with the prefix
			"arch": ext,
			"version": "1.0",
			"experimental": False,
			"vendor": True,
		}

		content["passes"]["per_model"][ext] = (
			{  # TODO currently hard code, but it should be fine
				"skip": [
					"riscv_features",
					"riscv_isa_info",
					"riscv_instr_formats",
					"riscv_instr_info",
					"behav_to_pat",
				],
				"override": {"behav_to_pat": {"patterns": False}},
			}
		)

	with open(path / (extension_name + ".yaml"), "w", encoding="utf-8") as file:
		yaml.safe_dump(content, file)
