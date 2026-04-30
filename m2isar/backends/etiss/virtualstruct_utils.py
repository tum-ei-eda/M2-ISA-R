# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2025
# Chair of Electrical Design Automation
# Technical University of Munich

"""Helper functions for dealing with ETISS VirtualStruct and GDBCore."""

import re
import pathlib
from typing import List, Union
from collections import defaultdict
import xml.etree.ElementTree as ET
from xml.etree import ElementTree, ElementInclude
from ...metamodel.attribute_info import MemoryAttribute

DEFAULT_ALIASES = {"zero": "x0", "ra": "x1", "sp": "x2", "gp": "x3", "tp": "x4", "t0": "x5", "t1": "x6", "t2": "x7", "s0": "x8", "fp": "x8", "s1": "x9", "a0": "x10", "a1": "x11", "a2": "x12", "a3": "x13", "a4": "x14", "a5": "x15", "a6": "x16", "a7": "x17", "s2": "x18", "s3": "x19", "s4": "x20", "s5": "x21", "s6": "x22", "s7": "x23", "s8": "x24", "s9": "x25", "s10": "x26", "s11": "x27", "t3": "x28", "t4": "x29", "t5": "x30", "t6": "x31"}

def list_to_ranges(nums: List[int]) -> List[Union[int, range]]:
    """
    Convert a list of integers into a list of contiguous ranges and single values.
    - Contiguous sequences (len >= 2) -> range(start, stop)
    - Single isolated numbers -> int
    """
    if not nums:
        return []

    nums = list(set(nums))  # deduplicate
    if len(nums) == 1 and nums[0] is None:
        return nums

    # Expand everything into a flat sorted list of ints
    expanded = []
    for item in nums:
        if isinstance(item, range):
            expanded.extend(item)
        else:
            expanded.append(item)
    
    nums = sorted(set(expanded))  # sort & deduplicate
    result = []
    start = prev = nums[0]
    
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        # close current segment
        if prev > start:
            result.append(range(start, prev + 1))
        else:
            result.append(start)
        start = prev = n
    
    # handle last segment
    if prev > start:
        result.append(range(start, prev + 1))
    else:
        result.append(start)
    
    return result


def process_xml_descr(path):
	tree = ElementTree.parse(path)
	root = tree.getroot()
	parent = pathlib.Path(path).parent
	def custom_loader(href, parse, encoding=None):
		if not pathlib.Path(href).is_file():
			href = parent / href
		if parse == "xml":
			with open(href, 'rb') as file:
				data = ElementTree.parse(file).getroot()
		else:
			if not encoding:
				encoding = 'UTF-8'
			with open(href, 'r', encoding=encoding) as file:
				data = file.read()
		return data
	ElementInclude.include(root, loader=custom_loader)
	mapping = {}
	num = -1
	for node in tree.iter():
		if node.tag == "reg":
			num = node.attrib.get("regnum", num + 1)
			if isinstance(num, str):
				num = int(num, 0)
			name = node.attrib["name"]
			sz = int(node.attrib["bitsize"])
			mapping[num] = (name, sz)
	return mapping


def resolve_reg(name, mems, aliases):
	# print("resolve_reg", name, mems, aliases)
	split_name = lambda s: (m.group(1), int(m.group(2))) if (m:=re.fullmatch(r'([a-zA-Z]+)(\d+)', s)) else None
	idx = None
	ret = mems.get(name, mems.get(name.lower(), mems.get(name.upper())))
	if ret is None:
		ret = aliases.get(name, aliases.get(name.lower(), aliases.get(name.upper(), aliases.get(f"{name.upper()}_CSR"))))
	if ret is None:
		splitted = split_name(name)
		if splitted is not None:
			name, idx = splitted
			ret = mems.get(name, mems.get(name.lower(), mems.get(name.upper())))
			if ret is None:
				ret = aliases.get(name, aliases.get(name.lower(), aliases.get(name.upper(), aliases.get(f"{name.upper()}_CSR"))))
	if ret is None:
		new_name = DEFAULT_ALIASES.get(name, DEFAULT_ALIASES.get(name.lower(), DEFAULT_ALIASES.get(name.upper())))
		if new_name is not None:
			return resolve_reg(new_name, mems, aliases)
	return ret, idx


def process_gdb_xml_descr_args(args: List[str], cores: list):
	descr_mapping = {}
	args = [part.strip() for arg in args for part in arg.split(",") if part.strip()]

	for descr in args:
		assert ":" in descr, f"Invalid mapping: {descr}"
		core, xml_path = descr.split(":", 1)
		assert core in cores, f"Unknown core: {core}"
		mapping = process_xml_descr(xml_path)
		descr_mapping[core] = mapping
	return descr_mapping

def get_gdb_mapping(mapping: dict, memories: dict, memory_aliases: dict):
	HARCODED_NAMES = {"PC": "instructionPointer"}
	gdb_mapping = None
	if mapping is not None:
		gdb_mapping = {}
		for regnum, data in mapping.items():
			name, sz = data
			resolved = resolve_reg(name, memories, memory_aliases)
			assert resolved is not None, f"Register lookup failed: {name}"
			if resolved is not None:
				mem, idx = resolved
				assert mem is not None, f"Register lookup failed: {name}"
				if mem.parent is not None:  # alias
					rng = mem.range
					assert rng.length == 1, "Aliased ranges are not allowed"
					assert idx is None
					idx = rng.lower
					mem = mem.parent
				# assert mem.size == sz, f"Expected size missmatch: {mem.size} vs. {sz}"
				# TODO: handle fcsr size
				assert mem.size >= sz or name in [f"v{i}" for i in range(32)], f"Expected size missmatch: {mem.size} vs. {sz} [{name}]"
				name2 = mem.name
				name2 = HARCODED_NAMES.get(name2, name2)
				if idx is not None:
					name2 += str(idx)
				gdb_mapping[regnum] = (name, name2)
	return gdb_mapping


def get_virtualstruct_regs(mapping: dict, memories: dict, memory_aliases: dict):
	main_reg = None
	float_reg = None
	vector_reg = None
	csr_reg = None
	pc_reg = None
	for mem in memories.values():
		if mem.is_pc:
			pc_reg = mem
		elif MemoryAttribute.IS_MAIN_REG in mem.attributes or mem.name == "X":
			main_reg = mem
		elif MemoryAttribute.IS_FLOAT_REG in mem.attributes or mem.name == "F":
			float_reg = mem
		elif MemoryAttribute.IS_VECTOR_REG in mem.attributes or mem.name == "F":
			vector_reg = mem
		elif MemoryAttribute.IS_CSR_REG in mem.attributes or mem.name == "CSR":
			csr_reg = mem
	aliased_csrs = set()
	if csr_reg is not None:
		for mem in memory_aliases.values():
			if mem.parent == csr_reg:
				if mem.range.length == 1:
					idx = mem.range.lower
					aliased_csrs.add(idx)
	assert main_reg is not None, "Unable to identify main_reg"
	assert pc_reg is not None, "Unable to identify pc_reg"
	VIRTUALSTRUCT_CLASSES = {
		main_reg.name: "RegField",
		**({float_reg.name: "FloatRegField"} if float_reg is not None else {}),
		**({vector_reg.name: "VectorRegField"} if vector_reg is not None else {}),
		**({csr_reg.name: "CSRField"} if csr_reg is not None else {}),
		**({pc_reg.name: "pcField"} if pc_reg is not None else {}),
	}
	aliased_csrs_only = True
	DEFAULT_VIRTUALSTRUCT_REGS = {
		"RegField": [range(0, main_reg.range.length)],
		**({"FloatRegField": [range(0, float_reg.range.length)]} if float_reg is not None else {}),
		# **({"VectorRegField": [range(0, vector_reg.range.length)]} if vector_reg is not None else {}),
		**({"VectorRegField": [range(0, 32)]} if vector_reg is not None else {}),
		**({"CSRField": list(sorted(aliased_csrs)) if aliased_csrs_only else [range(0, csr_reg.range.length)]} if csr_reg is not None else {}),
		"pcField": [None]
	}
	virtualstruct_regs = defaultdict(list)
	virtualstruct_regs.update(DEFAULT_VIRTUALSTRUCT_REGS)
	if mapping is not None:
		for regnum, data in mapping.items():
			name, sz = data
			resolved = resolve_reg(name, memories, memory_aliases)
			assert resolved is not None, f"Register lookup failed: {name}"
			if resolved is not None:
				mem, idx = resolved
				assert mem is not None, f"Register lookup failed: {name}"
				if mem.parent is not None:  # alias
					rng = mem.range
					assert rng.length == 1, "Aliased ranges are not allowed"
					assert idx is None
					idx = rng.lower
					mem = mem.parent
				# assert mem.size == sz, f"Expected size missmatch: {mem.size} vs. {sz}"
				# TODO: handle fcsr size
				assert mem.size >= sz or name in [f"v{i}" for i in range(32)], f"Expected size missmatch: {mem.size} vs. {sz} [{name}]"
				name = mem.name
				virtualstruct_class = VIRTUALSTRUCT_CLASSES.get(name)
				assert virtualstruct_class is not None, f"Unable to find VirtualStruct class for reg: {name}"
				virtualstruct_regs[virtualstruct_class].append(idx)
	if virtualstruct_regs is not None:
		virtualstruct_regs = {key: list_to_ranges(val) for key, val in virtualstruct_regs.items()}
	return virtualstruct_regs
