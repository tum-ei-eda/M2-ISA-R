# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Clean M2-ISA-R/Seal5 metamodel to .core_desc file."""

import logging
import json
from typing import Optional, Set, Union
from collections import defaultdict

from m2isar.metamodel import arch, behav, type_info
from m2isar.metamodel.type_info import TypeKind, ArrayType, PointerType

logger = logging.getLogger("coredsl2_writer")


class CoreDSL2Writer:
    def __init__(self, visitor, reduced: bool = True, skip_empty: bool = False, drop_first_op: bool = False, allowed_attrs: Optional[Set[str]] = None, legacy: bool = False, emit_operands: bool = False):
        self.legacy = legacy
        self.visitor = visitor
        self.reduced = reduced  # Reduced syntax for cdsl2llvm parser
        self.drop_first_op = drop_first_op
        self.allowed_attrs = allowed_attrs if allowed_attrs is not None else None
        self._emit_operands = emit_operands
        self.defined_by_ext = defaultdict(set)
        self.text = ""
        self.indent_str = "    "
        self.level = 0

    def reset(self):
        self.defined = set()

    @property
    def indent(self):
        return self.indent_str * self.level

    @property
    def isstartofline(self):
        return len(self.text) == 0 or self.text[-1] == "\n"

    @property
    def needsspace(self):
        return len(self.text) != 0 and self.text[-1] not in ["\n", " "]

    @property
    def emit_operands(self):
        return self._emit_operands

    def write(self, text, nl=False):
        # print("text", text, type(text))
        if isinstance(text, int):
            text = str(text)
        assert isinstance(text, str)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if self.isstartofline:
                self.text += self.indent
            self.text += line
            if (i < len(lines) - 1) or nl:
                self.text += "\n"

    def write_line(self, text):
        self.write(text, nl=True)

    def enter_block(self, br=True, nl=True):
        if br:
            if self.needsspace:
                self.write(" ")
            self.write("{", nl=nl)
        self.level += 1

    def leave_block(self, br=True, nl=True):
        assert self.level > 0
        self.level -= 1
        if br:
            self.write("}", nl=nl)

    def write_type(self, ty):
        # print("write_type", ty)
        KIND2STR = {
            TypeKind.VOID: "void",
            TypeKind.INT: "signed",
            TypeKind.UINT: "unsigned",
        }
        # if isinstance(ty, FunctionType):
        assert not isinstance(ty, ArrayType)
        kind_str = KIND2STR.get(ty.kind)
        assert kind_str is not None, f"Missing string for type kind {ty.kind}"
        self.write(kind_str)
        if ty.size is not None:
            self.write("<")
            sz = arch.get_const_or_val(ty.size)
            self.write(f"{sz}")
            self.write(">")
        # if data_type == arch.DataType.U:
        #     self.write("unsigned")
        # elif data_type == arch.DataType.S:
        #     self.write("signed")
        # elif data_type == arch.DataType.NONE:
        #     self.write("void")
        # else:
        #     raise NotImplementedError(f"Unsupported type: {data_type}")
        # if size:
        #     self.write("<")
        #     self.write(size)
        #     self.write(">")

    def write_attribute(self, attr, val=None):
        # print("attr", attr)
        if self.needsspace:
            self.write(" ")
        if val is not None:
            if isinstance(val, list) and len(val) == 0:
                val = None
        # TODO: allow atrbitrary attrs in cdsl2llvm parser, not only for operands
        if self.allowed_attrs is not None:
            allowed_attrs = [attr.lower() for attr in self.allowed_attrs]
            if self.reduced and attr.name.lower() not in allowed_attrs:
                return
        self.write("[[")
        self.write(attr.name.lower())
        if val is not None:
            self.write("=")

            def helper(val):
                if isinstance(val, list):  # TODO: replace with string literal
                    if len(val) == 1:
                        return helper(val[0])
                    return "(" + ",".join([helper(x) for x in val]) + ")"
                if isinstance(val, str):  # TODO: replace with string literal
                    return val  # TODO: operation
                if isinstance(val, int):  # TODO: replace with int literal
                    return str(val)  # TODO: operation
                if isinstance(val, behav.Literal):
                    value = val.value
                    if val.ty.kind == TypeKind.STR:
                        if '"' not in value:
                            value = '"' + value + '"'
                    return str(value)
                if isinstance(val, behav.NamedReference):
                    return val.reference.name
                    # print("val", val)
                    # print("val.reference", val.reference)
                    # print("dir(val)", dir(val))
                    # return helper(arch.get_const_or_val(val))
                raise NotImplementedError(f"Unhandled case: {type(val)}")

            val = helper(val)
            self.write(val)
        self.write("]]")

    def write_attributes(self, attributes):
        for attr, val in attributes.items():
            self.write_attribute(attr, val)

    def write_function(self, function):
        # print("write_function", function)
        if function.static:
            self.write("static ")
        if function.extern:
            self.write("extern ")
        self.write_type(function.ty)
        self.write(" ")
        self.write(function.name)
        self.write("(")
        for i, param in enumerate(function.args.values()):
            self.write_type(param.ty)
            if param.name is not None:
                self.write(" ")
                self.write(param.name)
            if i < len(function.args) - 1:
                self.write(", ")
        self.write(")")
        self.write_attributes(function.attributes)
        # self.enter_block()
        # self.write_behavior(instruction)
        if function.extern:
            self.write_line(";")
        else:
            self.enter_block()
            self.write_behavior2(function.operation)
            self.leave_block()
        # self.leave_block()

    def write_functions(self, functions):
        if self.reduced or not functions:
            return
        self.write("functions")
        # TODO: attributes
        self.enter_block()
        for function in functions.values():
            self.write_function(function)
        self.leave_block()

    def write_encoding_val(self, bitval):
        value = bitval.value
        width = bitval.length
        self.write(width)
        self.write("'b")
        bitstr = bin(value)[2:].zfill(width)
        self.write(bitstr)

    def write_encoding_field(self, bitfield):
        name = bitfield.name
        rng = bitfield.range
        self.write(name)
        self.write(f"[{rng.upper}:{rng.lower}]")


    def write_constraints(self, constraints):
        for constraint in constraints:
            # print("constraint", constraint, type(constraint), dir(constraint))
            for stmt in constraint.stmts:
                self.visitor.generate(stmt, self)
                desc = constraint.description
                if desc:
                    self.write(f";  // {desc}", nl=True)
                else:
                    self.write(";", nl=True)

    # def write_instruction_constraints(self, constraints, operands):
    #     if self.reduced:
    #         return
    #     self.write("constraints: ")
    #     if len(constraints) == 0:
    #         self.write_line("{};")
    #         return
    #     self.enter_block()
    #     op_constraints = sum([op.constraints for op in operands.values()], [])
    #     self.write_constraints(op_constraints)
    #     self.write_constraints(constraints)
    #     self.leave_block()

    def write_operand(self, operand):
        self.write("signed" if operand.signed else "unsigned")
        if operand.size is not None:
            self.write(f"<{operand.size}>")
        self.write(" ")
        self.write(operand.name)
        self.write_attributes(operand.attributes)
        self.write_line(";")

    def write_operands(self, operands):
        self.write("operands: ")
        if not operands:
            self.write_line("{}")
            return
        self.enter_block()
        for operand in operands.values():
            self.write_operand(operand)
        self.leave_block()

    def write_encoding(self, encoding):
        if any(field is None for field in encoding):
            self.write_line("encoding: auto;")
        else:
            self.write("encoding: ")
            for index, field in enumerate(encoding):
                if index:
                    self.write(" :: ")
                if isinstance(field, arch.BitVal):
                    self.write_encoding_val(field)
                elif isinstance(field, arch.BitField):
                    self.write_encoding_field(field)
                else:
                    raise TypeError(f"Unsupported encoding field: {field!r}")
            self.write_line(";")

        
    def write_assembly(self, instruction):
        if self.legacy:
            self.write_line("assembly: " + json.dumps(instruction.assembly or "") + ";")
        else:
            self.write("assembly: ")
            if instruction.mnemonic:
                self.write("{" + json.dumps(instruction.mnemonic) + ", ")
            self.write(json.dumps(instruction.assembly or ""))
            if instruction.mnemonic:
                self.write("}")
            self.write_line(";")


    def write_behavior2(self, op, drop_first: bool = False):
        # TODO: drop explicit PC increments?
        if drop_first:
            if len(op.statements) == 1:
                stmt = op.statements[0]
                assert isinstance(stmt, behav.Block)
                if len(stmt.statements) > 1:
                    stmt.statements = stmt.statements[1:]
            else:
                if len(op.statements) > 1:
                    op.statements = op.statements[1:]
        if self.reduced:
            self.enter_block()
        self.visitor.generate(op, self)
        if self.reduced:
            self.leave_block()
        # self.write(";", nl=True)

    def write_behavior(self, instruction, drop_first=False):
        self.write("behavior:")
        if not self.reduced:
            self.enter_block()
        self.write_behavior2(instruction.operation, drop_first=drop_first)
        if not self.reduced:
            self.leave_block()


    def write_instruction(self, instruction):
        self.write(instruction.name)
        self.write_attributes(instruction.attributes)
        self.enter_block()
        if self.emit_operands or (instruction.operands and (not instruction.has_encoding or not self.legacy)):
            self.write_operands(instruction.operands)
        self.write_encoding(instruction.encoding)
        self.write_assembly(instruction)
        self.write_behavior(instruction, drop_first=self.drop_first_op)
        self.leave_block()


    def write_instructions(self, instructions):
        # Legacy CoreDSL requires at least one instruction inside the block.
        # Aggregate sets can consist entirely of inherited instructions.
        if not instructions and self.legacy:
            self.write("instructions")
            self.enter_block()
            self.leave_block()
            return
        if not instructions:
            return
        self.write("instructions")
        # TODO: attributes?
        self.enter_block()
        for instruction in instructions.values():
            self.write_instruction(instruction)
        self.leave_block()


    def write_set(self, set_def):
        self.write("InstructionSet " + set_def.name)
        if set_def.extension:
            self.write(" extends " + ", ".join(set_def.extension))
        self.enter_block()
        self.write_architectural_state(set_def)
        self.write_functions(set_def.functions)
        self.write_always_blocks(set_def.always_blocks)
        instructions = dict(set_def.instructions)
        instructions.update(set_def.unencoded_instructions)
        self.write_instructions(instructions)
        self.leave_block()
        self.write("\n")


    def write_parameter(self, parameter):
        self.write_type(type_info.PrimitiveType(
            type_info.TypeKind.INT if parameter.signed else type_info.TypeKind.UINT, parameter.size))
        self.write(" " + parameter.name)
        self.write_attributes(parameter.attributes)
        if parameter.value is not None:
            self.write(" = " + str(parameter.value))
        self.write_line(";")


    def write_parameters(self, parameters):
        for parameter in parameters.values():
            self.write_parameter(parameter)

    def write_register_bank(self, register_bank):
        # print("register_bank", register_bank)
        # print("dir(register_bank)", dir(register_bank))
        # print("register_bank.ty", register_bank.ty)
        self.write("register ")
        if isinstance(register_bank.ty, ArrayType):
            self.write_type(register_bank.ty.element_type)
            self.write(f" {register_bank.name}")
            length = arch.get_const_or_val(register_bank.ty.length)
            self.write(f"[{length}]")
        else:
            self.write_type(register_bank.ty)
            self.write(f" {register_bank.name}")
        self.write_attributes(register_bank.attributes)
        initval = register_bank._initval
        if len(initval) > 0:
            # TODO: explicit type casts on RHS?
            if isinstance(register_bank.ty, ArrayType):
                if len(initval) == register_bank.ty.length:
                    self.write(" = ")
                    initval_str = ", ".join(str(initval[key]) for key in sorted(initval))
                    self.write("{" + initval_str + "}")
                    self.write(";", nl=True)
                else:
                    self.write(";", nl=True)
                    for idx, val in initval.items():
                        self.write(register_bank.name)
                        self.write(f"[{idx}]")
                        self.write(" = ")
                        self.write(val)
                        self.write(";", nl=True)
            else:
                self.write(" = ")
                assert len(initval) == 1
                self.write(list(initval.values())[0])
                self.write(";", nl=True)
        else:
            self.write(";", nl=True)

    def write_register_banks(self, register_banks):
        for register_bank in register_banks.values():
            self.write_register_bank(register_bank)

    def write_register_alias(self, register_alias):
        # print("register_alias", register_alias)
        # print("dir(register_alias)", dir(register_alias))
        # print("register_alias.ty", register_alias.ty)
        self.write("register ")
        assert isinstance(register_alias.ty, PointerType)
        self.write_type(register_alias.ty.ty)
        self.write("&")
        self.write(f" {register_alias.name}")
        # print("data_range", register_alias.data_range)
        # print("_initval", register_alias._initval)
        assert len(register_alias._initval) == 0
        # print("length", register_alias.length)
        # print("parent", register_alias.parent)
        # print("range", register_alias.range)
        assert register_alias.parent is not None
        self.write_attributes(register_alias.attributes)
        self.write(" = ")
        self.write(register_alias.parent.name)
        rng = register_alias.range
        lower, upper = rng.lower, rng.upper
        if register_alias.length == 1:
            assert lower == upper
            self.write(f"[{lower}]")
        else:
            assert register_alias.length > 1
            assert lower != upper
            # TODO: check endianess
            self.write(f"[{upper}:{lower}]")
        self.write(";", nl=True)

    def write_register_aliases(self, register_aliases):
        for register_alias in register_aliases.values():
            self.write_register_alias(register_alias)

    def write_memories(self, memories):
        for memory in memories.values():
            self.write_memory(memory)

    def write_memory(self, memory):
        # print("memory", memory)
        # print("dir(memory)", dir(memory))
        # print("memory.ty", memory.ty)
        self.write("extern ")
        if isinstance(memory.ty, ArrayType):
            self.write_type(memory.ty.element_type)
            self.write(f" {memory.name}")
            length = arch.get_const_or_val(memory.ty.length)
            self.write(f"[{length}]")
        else:
            self.write_type(memory.ty)
            self.write(f" {memory.name}")
        self.write_attributes(memory.attributes)
        initval = memory._initval
        if len(initval) > 0:
            # TODO: explicit type casts on RHS?
            if isinstance(memory.ty, ArrayType):
                if len(initval) == memory.ty.length:
                    self.write(" = ")
                    initval_str = ", ".join(str(initval[key]) for key in sorted(initval))
                    self.write("{" + initval_str + "}")
                    self.write(";", nl=True)
                else:
                    self.write(";", nl=True)
                    for idx, val in initval.items():
                        self.write(memory.name)
                        self.write(f"[{idx}]")
                        self.write(" = ")
                        self.write(val)
                        self.write(";", nl=True)
            else:
                self.write(" = ")
                assert len(initval) == 1
                self.write(list(initval.values())[0])
                self.write(";", nl=True)
        else:
            self.write(";", nl=True)

    def write_memory_alias(self, memory_alias):
        # print("memory_alias", memory_alias)
        # print("dir(memory_alias)", dir(memory_alias))
        # print("memory_alias.ty", memory_alias.ty)
        self.write("extern ")
        assert isinstance(memory_alias.ty, PointerType)
        self.write_type(memory_alias.ty.ty)
        self.write("&")
        self.write(f" {memory_alias.name}")
        # print("data_range", memory_alias.data_range)
        # print("_initval", memory_alias._initval)
        assert len(memory_alias._initval) == 0
        # print("length", memory_alias.length)
        # print("parent", memory_alias.parent)
        # print("range", memory_alias.range)
        assert memory_alias.parent is not None
        self.write_attributes(memory_alias.attributes)
        self.write(" = ")
        self.write(memory_alias.parent.name)
        rng = memory_alias.range
        lower, upper = rng.lower, rng.upper
        if memory_alias.length == 1:
            assert lower == upper
            self.write(f"[{lower}]")
        else:
            assert memory_alias.length > 1
            assert lower != upper
            # TODO: check endianess
            self.write(f"[{upper}:{lower}]")
        self.write(";", nl=True)

    def write_memory_aliases(self, memory_aliases):
        for memory_alias in memory_aliases.values():
            self.write_memory_alias(memory_alias)

    def write_architectural_state(self, core_set_def: Union[arch.CoreDef, arch.InstructionSet]):
        # print("set_def", set_def, dir(set_def))
        has_arch = sum([len(core_set_def.parameters), len(core_set_def.register_banks), len(core_set_def.register_aliases), len(core_set_def.memories), len(core_set_def.memory_aliases)]) > 0
        if has_arch:
            self.write("architectural_state")
            self.enter_block()
            self.write_parameters(core_set_def.parameters)
            self.write_register_banks(core_set_def.register_banks)
            self.write_register_aliases(core_set_def.register_aliases)
            self.write_memories(core_set_def.memories)
            self.write_memory_aliases(core_set_def.memory_aliases)
            self.leave_block()

    def write_core(self, core_def):
        # Emit the resolved core just as the upstream writer does, preserving
        # separately stored always behavior until the ETISS writer merges it.
        self.write("Core " + core_def.name)
        self.enter_block()
        self.write_architectural_state(core_def)
        self.write_functions(core_def.functions)
        self.write_always_blocks(core_def.always_blocks)
        instructions = dict(core_def.instructions)
        instructions.update(core_def.unencoded_instructions)
        self.write_instructions(instructions)
        self.leave_block()


    def write_always_blocks(self, blocks):
        if not blocks or self.reduced:
            return
        self.write("always")
        self.enter_block()
        for block in blocks.values():
            self.write(block.name)
            self.write_attributes(block.attributes)
            self.enter_block()
            self.visitor.generate(block.operation, self)
            self.leave_block()
        self.leave_block()
