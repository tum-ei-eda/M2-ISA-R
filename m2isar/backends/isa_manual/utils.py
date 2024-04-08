# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Utility stuff for M2-ISA-R isa manual backend"""
from ...metamodel import arch


def generate_encoding(encoding):
    out = """
{reg: [
"""
    pos = 0
    for enc in reversed(encoding):
        if isinstance(enc, arch.BitVal):
            bits = enc.length
            name = hex(enc.value)
            attr = ""
            type_ = 1
        elif isinstance(enc, arch.BitField):
            bits = enc.range.length
            hi = enc.range.upper
            lo = enc.range.lower
            name = enc.name
            attr = ""
            if name.lower()[:2] == "rd":
                type_ = 2
            elif name.lower()[:2] == "rs":
                type_ = 4
            else:
                type_ = 3
            if hi == lo:
                name = f"{name}[{hi}]"
            else:
                name = f"{name}[{hi}:{lo}]"
            name = f"'{name}'"
        out += f"{{bits: {bits}, name: {name}, attr: '{attr}', type: {type_}}},\n"
    out += """
]}
"""
    return out
