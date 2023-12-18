#!/usr/bin/env python3
""""Parsing the instructions from the specified yaml file"""

from typing import Dict, List
import warnings

import yaml

from .instructions_classes import InstructionCollection, ComplexOperand


def parse(path: str):
    with open(path, "r", encoding="utf-8") as f:
        yml: Dict = yaml.load(f, yaml.Loader)

    try:
        yml.pop("metadata")
    except KeyError:
        # raise RuntimeError("No metadata Specified!") from exc
        warnings.warn("No Metadata specified!", RuntimeWarning)

    defaults = {}
    try:  # TODO define what and how defaults are defined and then process them in python
        defaults = yml.pop("defaults")
    except KeyError:
        # raise RuntimeError("No metadata Specified!") from exc
        warnings.warn("No Defaults specified!", RuntimeWarning)

    instructions: List[InstructionCollection] = []
    for group in yml:
        for entry in yml[group]:
            name: str = entry.pop("name")
            op = entry.pop("op")
            operands = {
                name: ComplexOperand(d["width"], d["sign"], False)
                for (name, d) in entry["operands"].items()
            }

            # TODO inserting other default operators, depends on the op!
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

            instructions.append(
                InstructionCollection(name=name, ops=op, operands=operands)
            )

    return instructions


if __name__ == "__main__":
    # for debugging
    parse("./test.yaml")


# TODO:
# - more Tests, with more complex combinations

# Done
# - 16hl is not supported (or reconsider the naming, could be 16 and 16upper as seperate fields)
#   - this behaviour should be moved to the OP, and not be modeled in the operand
