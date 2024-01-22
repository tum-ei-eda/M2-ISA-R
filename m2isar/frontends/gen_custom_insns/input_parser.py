"""Parsing the instructions from the specified yaml file"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import warnings

import yaml

from .instructions_classes import InstructionCollection, ComplexOperand


@dataclass
class Metadata:
	"""Metadata that gets specified in the yaml file"""

	ext_name: str
	prefix: Optional[str]
	extensions: Optional[str]
	xlen: int


def parse(path: str):
	"""Parses the yaml file and returns a list of Instructions for further processing as well as metadata about the instructions"""
	with open(path, "r", encoding="utf-8") as f:
		yml: Dict = yaml.load(f, yaml.Loader)

	try:
		metadata_input: Dict[str, str] = yml.pop("metadata")
	except KeyError as exc:
		raise RuntimeError("No metadata Specified!") from exc
	metadata = Metadata(
		ext_name=metadata_input.get("name", ""),
		prefix=metadata_input.get("prefix", None),
		extensions=metadata_input.get("extension", None),
		xlen=int(metadata_input.get("XLEN", 32)),
	)

	defaults = {}
	try:
		defaults = yml.pop("defaults")
	except KeyError:
		warnings.warn("No Defaults specified!", RuntimeWarning)

	instructions: List[InstructionCollection] = []
	for group in yml:
		for entry in yml[group]:
			name: str = entry.pop("name")
			ops = entry.pop("op")
			operands = {
				name: ComplexOperand(d["width"], d["sign"], False)
				for (name, d) in entry["operands"].items()
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

			instructions.append(InstructionCollection(name, ops, operands))

	return (metadata, instructions)
