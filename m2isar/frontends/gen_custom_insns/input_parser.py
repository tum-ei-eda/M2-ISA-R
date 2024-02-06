"""Parsing the instructions from the specified yaml file"""

import logging
import pathlib
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml

from .instructions_classes import ComplexOperand, InstructionCollection


@dataclass
class Metadata:
	"""Metadata that gets specified in the yaml file"""

	ext_name: str
	prefix: Optional[str]
	version: Optional[str]
	used_extensions: str
	extends: Optional[str]
	core_name: Optional[str]
	"""Only needed if '-c' is used"""
	core_template: Optional[str]
	xlen: int = 32


logger = logging.getLogger("Instruction Gen")


def parse(path: pathlib.Path):
	"""Parses the yaml file and returns a list of Instructions for further processing as well as metadata about the instructions"""
	with open(path, "r", encoding="utf-8") as f:
		yml: Dict = yaml.safe_load(f)

	try:
		metadata_input: Dict[str, str] = yml.pop("metadata")
	except KeyError as exc:
		raise RuntimeError("No metadata Specified!") from exc

	xlen: int = metadata_input.get("XLEN", 32)  # type: ignore
	if xlen not in (32, 64):
		raise ValueError("XLEN can only be set to 32 or 64! Default=32")

	metadata = Metadata(
		ext_name=metadata_input.pop("name"),
		prefix=metadata_input.get("prefix"),
		version=metadata_input.get("version"),
		used_extensions=metadata_input.get("extensions", "i").lower(),
		extends=metadata_input.get("extends"),
		core_name=metadata_input.get("core_name"),
		core_template=metadata_input.get("core_template"),
		xlen=xlen,
	)

	defaults = {}
	try:
		defaults = yml.pop("defaults")
	except KeyError:
		logger.warning("No Defaults specified!")

	instructions_sets: Dict[str, List[InstructionCollection]] = {}
	for set_name in yml:
		instructions_sets[set_name] = []
		for inst in yml[set_name]:
			name: str = inst.pop("name")
			ops = inst.pop("op")
			operands = {
				name: ComplexOperand(
					operand["width"], operand["sign"], operand.get("immediate", False)
				)
				for (name, operand) in inst["operands"].items()
			}

			# TODO inserting other default operators, depends on the op!
			# This would need to be done during op parsing
			# as its the only place where i have info about the used operands
			if "rd" not in operands:
				try:
					operands["rd"] = ComplexOperand(
						defaults["operands"]["rd"]["width"],
						defaults["operands"]["rd"]["sign"],
						False,
					)
				except KeyError as e:
					raise KeyError(
						"Operand 'rd' not specified and no default available!"
					) from e

			instructions_sets[set_name].append(InstructionCollection(name, ops, operands))

	return (metadata, instructions_sets)
