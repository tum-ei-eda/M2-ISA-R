# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Visitor for traversing the behavior in the metamodel and generating the CoreDSL2 syntax."""

from m2isar.metamodel import arch, behav

# pylint: disable=unused-argument


def operation(self: behav.Operation, writer):
    if len(self.statements) > 1:
        writer.enter_block()
    for stmt in self.statements:
        stmt.generate(writer)
        if not isinstance(stmt, (behav.Conditional, behav.Operation)):
            writer.write_line(";")
    if len(self.statements) > 1:
        writer.leave_block()


def binary_operation(self: behav.BinaryOperation, writer):
    self.left = self.left.generate(writer)
    writer.write(f" {self.op.value} ")
    self.right = self.right.generate(writer)


def slice_operation(self: behav.SliceOperation, writer):
    self.expr = self.expr.generate(writer)
    writer.write("[")
    self.left = self.left.generate(writer)
    writer.write(":")
    self.right = self.right.generate(writer)
    writer.write("]")


def concat_operation(self: behav.ConcatOperation, writer):
    self.left = self.left.generate(writer)
    writer.write(" :: ")
    self.right = self.right.generate(writer)


def number_literal(self: behav.IntLiteral, writer):
    writer.write(self.value)


def int_literal(self: behav.IntLiteral, writer):
    writer.write(self.value)


def scalar_definition(self: behav.ScalarDefinition, writer):
    writer.write_type(self.scalar.data_type, self.scalar.size)
    writer.write(" ")
    writer.write(self.scalar.name)
    if self.scalar.value:
        writer.write(" = ")
        writer.write(self.scalar.value)


def break_(self: behav.Break, writer):
    writer.write_line("break;")


def assignment(self: behav.Assignment, writer):
    self.target.generate(writer)
    writer.write(" = ")
    self.expr.generate(writer)


def conditional(self: behav.Conditional, writer):
    for i, stmt in enumerate(self.stmts):
        if i == 0:
            writer.write("if (")
            self.conds[i].generate(writer)
            writer.write(")")
        elif 0 < i < len(self.conds):
            writer.write("else if(")
            self.conds[i].generate(writer)
            writer.write(")")
        else:
            writer.write("else")
        writer.enter_block()
        stmt.generate(writer)
        if not isinstance(stmt, (behav.Conditional, behav.Operation)):
            writer.write_line(";")
        nl = len(self.stmts) > i
        writer.leave_block(nl=nl)


def loop(self: behav.Loop, writer):
    writer.write("while (")
    self.cond.generate(writer)
    writer.write(")")
    writer.enter_block()
    for stmt in self.stmts:
        stmt.generate(writer)
    writer.leave_block()


def ternary(self: behav.Ternary, writer):
    self.cond.generate(writer)
    writer.write(" ? ")
    self.then_expr.generate(writer)
    writer.write(" : ")
    self.else_expr.generate(writer)


def return_(self: behav.Return, writer):
    writer.write("return")
    if self.expr is not None:
        writer.write(" ")
        self.expr = self.expr.generate(writer)


def unary_operation(self: behav.UnaryOperation, writer):
    writer.write(self.op.value)
    self.right.generate(writer)


def named_reference(self: behav.NamedReference, writer):
    writer.write(self.reference.name)
    if isinstance(self.reference, (arch.Constant, arch.Memory, arch.Scalar)):
        # writer.track(self.reference.name)
        pass
    # if isinstance(self.reference, arch.Constant):
    # 	return behav.IntLiteral(self.reference.value, self.reference.size, self.reference.signed)

    # if isinstance(self.reference, arch.Scalar) and self.reference.value is not None:
    # 		return behav.IntLiteral(self.reference.value, self.reference.size, self.reference.data_type == arch.DataType.S)


def indexed_reference(self: behav.IndexedReference, writer):
    writer.write(self.reference.name)
    writer.write("[")
    self.index.generate(writer)
    writer.write("]")


def type_conv(self: behav.TypeConv, writer):
    writer.write("(")
    writer.write_type(self.data_type, self.size)
    writer.write(")")
    writer.write("(")
    self.expr.generate(writer)
    writer.write(")")

def callable_(self: behav.Callable, writer):
    ref = self.ref_or_name
    if isinstance(ref, arch.Function):
        writer.write(ref.name)
    else:
        raise NotImplementedError
    writer.write("(")
    for i, stmt in enumerate(self.args):
        stmt.generate(writer)
        if i < len(self.args) - 1:
            writer.write(", ")
    writer.write(")")


def group(self: behav.Group, writer):
    writer.write("(")
    self.expr.generate(writer)
    writer.write(")")
