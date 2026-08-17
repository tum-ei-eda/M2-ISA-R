# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Clean M2-ISA-R/Seal5 metamodel to .core_desc file."""

import logging
from typing import Optional, Set, Union
from collections import defaultdict

from m2isar.metamodel import arch, behav
from m2isar.metamodel.type_info import TypeKind, ArrayType, PointerType

logger = logging.getLogger("coredsl2_writer")


class CoreDSL2Writer:
    def __init__(self, visitor, reduced: bool = True, skip_empty: bool = False, drop_first_op: bool = False, allowed_attrs: Optional[Set[str]] = None):
        self.visitor = visitor
        self.reduced = reduced  # Reduced syntax for cdsl2llvm parser
        self.drop_first_op = drop_first_op
        self.allowed_attrs = allowed_attrs if allowed_attrs is not None else None
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
        if self.reduced and val is not None:
            return
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
        if self.reduced:
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

    # def write_operand(self, operand):
    #     self.write_type(operand.ty)
    #     self.write(" ")
    #     self.write(operand.name)
    #     self.write_attributes(operand.attributes)
    #     self.write_line(";")

    # def write_operands(self, operands):
    #     self.write("operands: ")
    #     if len(operands) == 0:
    #         self.write_line("{}")
    #         return
    #     self.enter_block()
    #     # print("operands", operands)
    #     for _, op in enumerate(operands.values()):
    #         self.write_operand(op)
    #     # for i, op in enumerate(operands.values()):
    #     #     self.write_constraints(op.constraints)
    #     self.leave_block()

    def write_encoding(self, encoding):
        self.write("encoding: ")
        # print("encoding", encoding, dir(encoding))
        for i, elem in enumerate(encoding):
            if isinstance(elem, arch.BitVal):
                self.write_encoding_val(elem)
            elif isinstance(elem, arch.BitField):
                self.write_encoding_field(elem)
            else:
                assert False
            if i < len(encoding) - 1:
                self.write(" :: ")
        self.write(";", nl=True)

    def write_assembly(self, instruction):
        self.write("assembly: ")
        mnemonic = instruction.mnemonic
        assembly = instruction.assembly
        if mnemonic and not self.reduced:
            self.write("{")
            self.write(f'"{mnemonic}"')
            self.write(", ")
        if assembly is None:
            assembly = ""
        self.write(f'"{assembly}"')
        if mnemonic and not self.reduced:
            self.write("}")
        self.write(";", nl=True)

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

    def write_behavior(self, instruction, drop_first: bool = False):
        self.write("behavior: ")
        self.write_behavior2(instruction.operation, drop_first=drop_first)

    def write_instruction(self, instruction):
        print("write_instruction", instruction)
        self.write(instruction.name)
        self.write_attributes(instruction.attributes)
        self.enter_block()
        # self.write_operands(instruction.operands)  # seal5 only
        # self.write_instruction_constraints(instruction.constraints, instruction.operands)  # seal5 only
        self.write_encoding(instruction.encoding)
        self.write_assembly(instruction)
        self.write_behavior(instruction, drop_first=self.drop_first_op)
        self.leave_block()

    def write_instructions(self, instructions):
        print("write_instructions", instructions)
        self.write("instructions")
        # TODO: attributes?
        self.enter_block()
        for instruction in instructions.values():
            self.write_instruction(instruction)
        self.leave_block()

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

    def write_set(self, set_def):
        print("write_set", set_def)
        self.write("InstructionSet ")
        self.write(set_def.name)
        # TODO: attributes
        # TODO: extends
        if set_def.extension:
            self.write(" extends ")
            self.write(", ".join(set_def.extension))
        self.enter_block()
        self.write_architectural_state(set_def)
        # TODO: reuse for core (write_arch_state)
        self.write_functions(set_def.functions)
        self.write_instructions(set_def.instructions)
        self.leave_block()

    def write_parameter(self, parameter):
        # print("parameter", parameter)
        # print("dir(parameter)", dir(parameter))
        if parameter.signed:
            self.write("signed")
        else:
            self.write("unsigned")
        if parameter.size is not None:
            self.write(f"<{parameter.size}>")
        self.write(f" {parameter.name}")
        self.write(" = ")
        self.write(parameter.value)
        self.write(";", nl=True)

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
        # print("write_core", core_def)
        # print("dir(core_def)", dir(core_def))
        # print("core_def.functions_by_ext", core_def.functions_by_ext)
        # print("core_def.instructions_by_ext", core_def.instructions_by_ext)
        gen_sets = False
        if gen_sets:
            set_names = list(set(core_def.functions_by_ext.keys()) | set(core_def.instructions_by_ext.keys()) | set(core_def.contributing_types))
            # print("set_names", set_names)
            for set_name in set_names:
                set_funcs = core_def.functions_by_ext.get(set_name, {})
                set_instrs = core_def.instructions_by_ext.get(set_name, {})
                extension = []
                parameters = {}
                memories = {}
                memory_aliases = {}
                register_banks = {}
                register_aliases = {}
                temp_set = arch.InstructionSet(set_name, extension, parameters, memories, memory_aliases, register_banks, register_aliases, set_funcs, set_instrs)
                self.write_set(temp_set)
        else:
            set_names = []
        # input("***")
        # print("core_def.memories", core_def.memories)
        # print("core_def.memory_aliases", core_def.memory_aliases)
        # print("core_def.parameters", core_def.parameters)
        # print("core_def.register_aliases", core_def.register_aliases)
        # print("core_def.register_banks", core_def.register_banks)
        if len(set_names) > 0:
            provides_str = ", ".join(core_def.contributing_types)
            self.write(f"Core {core_def.name} provides {provides_str}")
        else:
            self.write(f"Core {core_def.name}")
        self.enter_block()
        self.write_architectural_state(core_def)
        if not gen_sets:
            self.write_functions(core_def.functions)
            self.write_instructions(core_def.instructions)
        self.leave_block()
