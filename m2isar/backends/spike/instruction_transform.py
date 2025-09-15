# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Recursive tree traversal methods to generate behavior code."""

import logging
from itertools import chain
from string import Template

from ... import M2NameError, M2SyntaxError, M2ValueError, flatten
from ...metamodel import arch, behav
from ...metamodel.code_info import LineInfoPlacement

# from . import replacements
from .instruction_utils import (
    # FN_VAL_REPL,
    # MEM_VAL_REPL,
    CodePartsContainer,
    CodeString,
    # FnID,
    # MemID,
    # StaticType,
    TransformerContext,
    data_type_map,
)

# pylint: disable=unused-argument

logger = logging.getLogger("instr_transform")


def operation(self: behav.Operation, context: TransformerContext):
    """Generate an `Operation` model object. Essentially generate all children,
    concatenate their code, and add exception behavior if needed.
    """

    args: "list[CodeString]" = []
    code_lines = []

    for stmt in self.statements:
        c = stmt.generate(context)

        if isinstance(c, list):
            args.extend(flatten(c))
        else:
            args.append(c)

    for arg in args:
        if arg.is_mem_access:
            raise_fn_call = behav.Conditional(
                [behav.CodeLiteral("cpu->exception")],
                [behav.ProcedureCall(context.mem_raise_fn, [behav.CodeLiteral("cpu->exception")])],
            ).generate(context)

        before_line_infos = []
        after_line_infos = []

        for f_id in arg.function_calls:  # TODO: rework so that cascaded function calls and memory reads work properly
            code_lines.append(
                context.wrap_codestring(
                    f"{data_type_map[f_id.fn_call.data_type]}{f_id.fn_call.actual_size} {FN_VAL_REPL}{f_id.fn_id};",
                )
            )
            code_lines.append(context.wrap_codestring(f"{FN_VAL_REPL}{f_id.fn_id} = {f_id.args};"))
            code_lines.append(
                context.wrap_codestring(
                    'if (cpu->return_pending) goto instr_exit_" + std::to_string(ic.current_address_) + ";',
                )
            )

        for m_id in arg.read_mem_ids:
            code_lines.append(context.wrap_codestring(f"uint{m_id.access_size}_t {MEM_VAL_REPL}{m_id.mem_id};"))

        for m_id in arg.write_mem_ids:
            code_lines.append(context.wrap_codestring(f"uint{m_id.access_size}_t {MEM_VAL_REPL}{m_id.mem_id};"))

        code_lines.append(context.wrap_codestring(f"{arg.code}"))

        # if arg.check_trap:
        # 	code_lines.append(context.wrap_codestring('goto instr_exit_" + std::to_string(ic.current_address_) + ";'))

    container = CodePartsContainer()

    container.initial_required = "\n".join(code_lines)

    # only generate return statements if not in a function

    return container


def block(self: behav.Block, context: TransformerContext):
    stmts = [stmt.generate(context) for stmt in self.statements]

    pre = [CodeString("{ // block", None, None)]
    post = [CodeString("} // block", None, None)]

    return pre + stmts + post


def return_(self: behav.Return, context: TransformerContext):
    if context.instr_size != 0:
        raise M2SyntaxError("Return statements are not allowed in instruction behavior!")

    if self.expr is not None:
        c = self.expr.generate(context)
        c.code = f"return {c.code};"
        c.line_infos.append(self.line_info)
    else:
        c = CodeString("return;", None, None)

    return c


def break_(self: behav.Break, context: TransformerContext):
    return CodeString("break;", None, None)


def scalar_definition(self: behav.ScalarDefinition, context: TransformerContext):
    """Generate a scalar definition. Calculates the actual required data width and generates
    a variable instantiation."""

    actual_size = 1 << (self.scalar.size - 1).bit_length()
    actual_size = max(actual_size, 8)

    c = CodeString(
        f"{data_type_map[self.scalar.data_type]}{actual_size} {self.scalar.name}",
        self.scalar.size,
        self.scalar.data_type == arch.DataType.S,
    )
    # c.scalar = self.scalar
    return c


def procedure_call(self: behav.ProcedureCall, context: TransformerContext):
    """Generate a procedure call (Function call without usage of the return value)."""

    fn_args = [arg.generate(context) for arg in self.args]

    # extract function object reference
    ref = self.ref_or_name if isinstance(self.ref_or_name, arch.Function) else None
    name = ref.name if isinstance(self.ref_or_name, arch.Function) else self.ref_or_name

    if ref is not None:
        # if there is a function object, use its information
        fn = ref

        # convert singular static arguments
        if True:
            context.used_arch_data = True

        # generate argument string, add ETISS arch data if required
        arch_args = (
            ["cpu", "system", "plugin_pointers"]
            if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (not fn.static and not fn.extern)
            else []
        )
        arg_str = ", ".join(arch_args + [arg.code for arg in fn_args])

        # check if any argument is a memory access
        mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

        # update affected and dependent registers
        regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
        context.dependent_regs.update(regs_affected)

        # add special behavior if this function is an exception entry point
        exc_code = ""

        if arch.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN in fn.attributes:
            context.generates_exception = True

        if arch.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn.attributes:
            context.generates_exception = True

            if fn.size is not None:
                exc_code = "cpu->exception = "

        c = CodeString(f"{exc_code}{fn.name}({arg_str});", None, None)
        c.mem_ids = mem_ids
        if fn.throws and not True:
            c.check_trap = True

            cond = "if (cpu->return_pending) " if fn.throws == arch.FunctionThrows.MAYBE else ""
            c2 = CodeString(cond + 'goto instr_exit_" + std::to_string(ic.current_address_) + ";', None, None)

            pre = [
                CodeString("{ // procedure", None, None),
                CodeString("{ // procedure", None, None),
            ]
            post = [
                CodeString("} // procedure", None, None),
                CodeString("} // procedure", None, None),
            ]

            return pre + [c, c2] + post

        return c

    raise M2NameError(f"Function {name} not recognized!")


def function_call(self: behav.FunctionCall, context: TransformerContext):
    """Generate a regular function call (with further use of return value)."""

    fn_args = [arg.generate(context) for arg in self.args]

    # extract function object reference
    ref = self.ref_or_name if isinstance(self.ref_or_name, arch.Function) else None
    name = ref.name if isinstance(self.ref_or_name, arch.Function) else self.ref_or_name

    if ref is not None:
        # if there is a function object, use its information

        fn = ref

        # convert singular static arguments
        if True:
            context.used_arch_data = True

        # generate argument string, add ETISS arch data if required
        arch_args = (
            ["cpu", "system", "plugin_pointers"]
            if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (True and not fn.extern)
            else []
        )
        arg_str = ", ".join(arch_args + [arg.code for arg in fn_args])

        # keep track of signedness of function return value
        signed = fn.data_type == arch.DataType.S
        # keep track of affected registers
        regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))

        # goto_code = ""

        # if fn.throws and not context.ignore_static:
        # 	goto_code = '; goto instr_exit_" + std::to_string(ic.current_address_) + "'

        c = CodeString(
            f"{fn.name}({arg_str})",
            fn.size,
            signed,
            regs_affected=regs_affected,
        )
        c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

        if fn.throws and not True:
            fn_id = FnID(fn, context.fn_var_count, c)
            repl_c = CodeString(f"{FN_VAL_REPL}{context.fn_var_count}", fn.size, signed, regs_affected=regs_affected)
            repl_c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))
            repl_c.function_calls.append(fn_id)
            context.fn_var_count += 1
            return repl_c

        return c

    raise M2NameError(f"Function {name} not recognized!")


def conditional(self: behav.Conditional, context: TransformerContext):
    """Generate a conditional ('if' with optional 'else if' and 'else' blocks)"""

    # generate conditions and statement blocks
    conds: "list[CodeString]" = [x.generate(context) for x in self.conds]
    stmts: "list[list[CodeString]]" = []  # = [[y.generate(context) for y in x] for x in self.stmts]

    for cond in conds[1:]:
        conds[0].mem_ids.extend(cond.mem_ids)
        cond.mem_ids.clear()

    for stmt in self.stmts:
        ret = stmt.generate(context)

        if isinstance(ret, list):
            stmts.append(ret)
        else:
            stmts.append([ret])

    # for stmt_block in self.stmts:
    # 	block_statements = []
    # 	for stmt in stmt_block:
    # 		if isinstance(stmt, list):
    # 			for stmt2 in stmt:
    # 				block_statements.append(stmt2.generate(context))
    # 		else:
    # 			block_statements.append(stmt.generate(context))

    # 	stmts.append(block_statements)

    # check if all conditions are static

    outputs: "list[CodeString]" = []

    for cond in conds:
        for m_id in cond.mem_ids:
            m_id.write = False

    # generate initial if
    # c = conds[0]
    conds[0].code = f"if ({conds[0].code}) {{ // conditional"
    conds[0].line_infos.append(self.line_info)
    outputs.append(conds[0])
    if True:
        context.dependent_regs.update(conds[0].regs_affected)

    # generate first statement block
    outputs.extend(flatten(stmts[0]))

    # generate closing brace
    outputs.append(CodeString("} // conditional", None, None))

    for elif_cond, elif_stmts in zip(conds[1:], stmts[1:]):
        elif_cond.code = f" else if ({elif_cond.code}) {{ // conditional"
        outputs.append(elif_cond)
        if True:
            context.dependent_regs.update(elif_cond.regs_affected)

        outputs.extend(flatten(elif_stmts))

        outputs.append(CodeString("} // conditional", None, None))

    if len(conds) < len(stmts):
        outputs.append(CodeString("else { // conditional", None, None))

        outputs.extend(flatten(stmts[-1]))

        outputs.append(CodeString("} // conditional", None, None))

    return outputs


def loop(self: behav.Loop, context: TransformerContext):
    """Generate 'while' and 'do .. while' loops."""

    # generate the loop condition and body
    cond: CodeString = self.cond.generate(context)
    stmts: "list[CodeString]" = []  # [stmt.generate(context) for stmt in self.stmts]

    for stmt in self.stmts:
        if isinstance(stmt, list):
            for stmt2 in stmt:
                stmts.append(stmt2.generate(context))
        else:
            stmts.append(stmt.generate(context))

    if True:
        context.dependent_regs.update(cond.regs_affected)

    outputs: "list[CodeString]" = []

    if self.post_test:
        start_c = CodeString("do", None, None)
        end_c = cond
        end_c.code = f"while ({end_c.code})"
    else:
        start_c = cond
        start_c.code = f"while ({start_c.code})"
        end_c = CodeString("", None, None)

    outputs.append(start_c)

    outputs.extend(flatten(stmts))

    outputs.append(end_c)

    return outputs


def ternary(self: behav.Ternary, context: TransformerContext):
    """Generate a ternary expression."""

    # generate condition and 'then' and 'else' statements
    cond = self.cond.generate(context)
    then_expr = self.then_expr.generate(context)
    else_expr = self.else_expr.generate(context)

    c = CodeString(
        f"({cond}) ? ({then_expr}) : ({else_expr})",
        then_expr.size if then_expr.size > else_expr.size else else_expr.size,
        then_expr.signed or else_expr.signed,
        regs_affected=set.union(cond.regs_affected, then_expr.regs_affected, else_expr.regs_affected),
    )
    c.mem_ids = cond.mem_ids + then_expr.mem_ids + else_expr.mem_ids

    return c


def assignment(self: behav.Assignment, context: TransformerContext):
    """Generate an assignment expression"""

    # generate target and value expressions
    target: CodeString = self.target.generate(context)
    expr: CodeString = self.expr.generate(context)

    # keep track of affected and dependent registers
    context.affected_regs.update(target.regs_affected)
    context.dependent_regs.update(expr.regs_affected)

    if not target.is_mem_access and not expr.is_mem_access:
        if target.actual_size > target.size:
            expr.code = f"({expr.code}) & {hex((1 << target.size) - 1)}"

    else:
        context.generates_exception = True

        for m_id in expr.mem_ids:
            m_id.write = False

            if not expr.mem_corrected:
                logger.debug("assuming mem read size at %d", target.size)
                m_id.access_size = target.size

        if target.is_mem_access:
            if len(target.mem_ids) != 1:
                raise M2SyntaxError("Only one memory access is allowed as assignment target!")

            target.mem_ids[0].write = True

            if not target.mem_corrected:
                logger.debug("assuming mem write size at %d", expr.size)
                target.mem_ids[0].access_size = expr.size

    if target.code == "RD":
        c = CodeString(
            f"WRITE_RD({expr.code});",
            None,
            None,
        )
    else:
        c = CodeString(
            f"{target.code} = {expr.code};",
            None,
            None,
        )

    c.function_calls.extend(target.function_calls)
    c.function_calls.extend(expr.function_calls)

    c.mem_ids.extend(target.mem_ids)
    c.mem_ids.extend(expr.mem_ids)

    return c


def binary_operation(self: behav.BinaryOperation, context: TransformerContext):
    """Generate a binary expression"""

    # generate LHS and RHS of the expression
    left = self.left.generate(context)
    op = self.op
    right = self.right.generate(context)

    c = CodeString(
        f"{left.code} {op.value} {right.code}",
        left.size if left.size > right.size else right.size,
        left.signed or right.signed,
        regs_affected=set.union(left.regs_affected, right.regs_affected),
    )
    # keep track of any memory accesses
    c.mem_ids = left.mem_ids + right.mem_ids
    return c


def unary_operation(self: behav.UnaryOperation, context: TransformerContext):
    op = self.op
    right = self.right.generate(context)

    c = CodeString(
        f"{op.value}({right.code})",
        right.size,
        right.signed,
        regs_affected=right.regs_affected,
    )
    c.mem_ids = right.mem_ids
    return c


def slice_operation(self: behav.SliceOperation, context: TransformerContext):
    """Generate a slice expression"""

    # generate expression to be sliced and lower and upper slice bound
    expr = self.expr.generate(context)
    left = self.left.generate(context)
    right = self.right.generate(context)

    # slice with fixed integers if slice bounds are integers
    try:
        new_size = (
            int(left.code.replace("U", "").replace("L", "")) - int(right.code.replace("U", "").replace("L", "")) + 1
        )
        mask = (
            1
            << (
                int(left.code.replace("U", "").replace("L", "")) - int(right.code.replace("U", "").replace("L", "")) + 1
            )
        ) - 1
        mask = f"{mask}ULL"

    # slice with actual lower and upper bound code if not possible to slice with integers
    except ValueError:
        new_size = expr.size
        mask = f"((1 << (({left.code}) - ({right.code}) + 1)) - 1)"

    c = CodeString(
        f"((({expr.code}) >> ({right.code})) & {mask})",
        new_size,
        expr.signed,
        regs_affected=set.union(expr.regs_affected, left.regs_affected, right.regs_affected),
    )
    c.mem_ids = expr.mem_ids + left.mem_ids + right.mem_ids
    return c


def concat_operation(self: behav.ConcatOperation, context: TransformerContext):
    """Generate a concatenation expression"""

    # generate LHS and RHS operands
    left: CodeString = self.left.generate(context)
    right: CodeString = self.right.generate(context)

    new_size = left.size + right.size
    c = CodeString(
        f"((({left.code}) << {right.size}) | ({right.code}))",
        new_size,
        left.signed or right.signed,
        regs_affected=set.union(left.regs_affected, right.regs_affected),
    )
    c.mem_ids = left.mem_ids + right.mem_ids
    return c


def named_reference(self: behav.NamedReference, context: TransformerContext):
    """Generate a named reference"""

    # extract referred object
    referred_var = self.reference

    name = referred_var.name

    # check which type of reference has to be generated
    if isinstance(referred_var, arch.Memory):
        # architecture memory object (register, memory interface)
        if True:
            ref = "*" if len(referred_var.children) > 0 else ""
            # name = f"{ref}{replacements.default_prefix}{name}"
            name = f"{ref}{name}"
        signed = False
        size = referred_var.size
        context.used_arch_data = True

    elif isinstance(referred_var, arch.BitFieldDescr):
        # instruction encoding operand
        signed = referred_var.data_type == arch.DataType.S
        size = referred_var.size

    elif isinstance(referred_var, arch.Scalar):
        # scalar
        signed = referred_var.data_type == arch.DataType.S
        size = referred_var.size

    elif isinstance(referred_var, arch.Constant):
        # architecture constant
        signed = referred_var.value < 0
        size = context.native_size
        name = f"{referred_var.value}"

    elif isinstance(referred_var, arch.FnParam):
        # function argument
        signed = referred_var.data_type == arch.DataType.S
        size = referred_var.size

    elif isinstance(referred_var, arch.Intrinsic):
        if True:
            raise TypeError("intrinsic not allowed in function")

        signed = referred_var.data_type == arch.DataType.S
        size = referred_var.size

        if referred_var == context.intrinsics["__encoding_size"]:
            name = str(context.instr_size // 8)

    else:
        # should not happen
        raise TypeError("wrong type")

    c = CodeString(name, size, signed)
    # c.scalar = scalar
    return c


def indexed_reference(self: behav.IndexedReference, context: TransformerContext):
    """Generate an indexed reference expression (for register banks or memory)."""

    name = self.reference.name

    # generate index expression
    index = self.index.generate(context)

    referred_mem = self.reference

    if isinstance(referred_mem, arch.Memory):
        context.used_arch_data = True

    size = referred_mem.size

    index_code = index.code

    if arch.MemoryAttribute.IS_MAIN_REG in referred_mem.attributes:
        # TODO: handle compressed regs
        assert name == "X"
        lookup_gpr = {
            "rd": "RD",
            "rs1": "RS1",
            "rs2": "RS2",
            "rs3": "RS3",
        }
        found = lookup_gpr.get(index_code)
        print("found", found)
        assert found is not None, f"Macro lookup failed for gpr index: '{index_code}'"
        code_str = found
        return CodeString(code_str, size, False)
    elif name == "F":
        lookup_fpr = {
            # "rd": "RD",
            ("rs1", 16): "FRS1_H",
            ("rs1", 32): "FRS1_F",
            ("rs1", 64): "FRS1_D",
            ("rs2", 16): "FRS2_H",
            ("rs2", 32): "FRS2_F",
            ("rs2", 64): "FRS2_D",
            ("rs3", 16): "FRS3_H",
            ("rs3", 32): "FRS3_F",
            ("rs3", 64): "FRS3_D",
        }
        found = lookup_fpr.get((index_code, size))
        print("found", found)
        assert found is not None, f"Macro lookup failed for fpr index: '{index_code}'"
        code_str = found
        return CodeString(code_str, size, False)
    elif arch.MemoryAttribute.IS_MAIN_MEM in referred_mem.attributes:
        raise NotImplementedError
        # generate memory access if main memory is accessed
        c = CodeString(
            f"{MEM_VAL_REPL}{context.mem_var_count}",
            size,
            False,
        )
        c.mem_ids.append(MemID(referred_mem, context.mem_var_count, index, size))
        context.mem_var_count += 1
        return c

    # generate normal indexed access if not
    # code_str = f'{replacements.prefixes.get(name, replacements.default_prefix)}{name}[{index.code}]'
    code_str = f"{name}[{index.code}]"
    if size != referred_mem.size:
        code_str = f"(uint{size}_t)" + code_str
    c = CodeString(code_str, size, False)
    if arch.MemoryAttribute.IS_MAIN_REG in referred_mem.attributes:
        c.regs_affected.add(index_code)
    return c


def type_conv(self: behav.TypeConv, context: TransformerContext):
    """Generate a type cast expression"""

    # generate the expression to be type-casted
    expr = self.expr.generate(context)

    # if only width should be changed assume data type remains unchanged
    if self.data_type is None:
        self.data_type = arch.DataType.S if expr.signed else arch.DataType.U

    # if only data type should be changed assume width remains unchanged
    if self.size is None:
        self.size = expr.size
        self.actual_size = expr.actual_size

    # save access size for memory access
    if expr.is_mem_access:
        if not expr.mem_corrected and expr.mem_ids[-1].access_size != self.size:
            expr.mem_ids[-1].access_size = self.size
            expr.size = self.size
            expr.mem_corrected = True
        elif expr.mem_ids[-1].access_size == self.size:
            expr.mem_corrected = True

    code_str = expr.code

    # sign extension for non-2^N datatypes
    if self.data_type == arch.DataType.S and expr.actual_size != expr.size:
        target_size = self.actual_size

        if isinstance(self.size, int):
            code_str = f"((int{target_size}_t)(((int{target_size}_t){expr.code}) << ({target_size - expr.size})) >> ({target_size - expr.size}))"
        else:
            code_str = f"((int{target_size}_t)(({expr.code}) << ({target_size} - {expr.size})) >> ({target_size} - {expr.size}))"

    # normal type conversion
    # TODO: check if behavior adheres to CoreDSL 2 spec
    else:
        code_str = f"({data_type_map[self.data_type]}{self.actual_size})({code_str})"

    c = CodeString(
        code_str,
        self.size,
        self.data_type == arch.DataType.S,
        regs_affected=expr.regs_affected,
        line_infos=[self.line_info] + expr.line_infos,
    )
    c.mem_ids = expr.mem_ids
    c.mem_corrected = expr.mem_corrected

    return c


def int_literal(self: behav.IntLiteral, context: TransformerContext):
    """Generate an integer literal."""

    lit = int(self.value)
    size = min(self.bit_size, 128)
    sign = self.signed

    minus = ""
    if lit > 0 and sign and (lit >> (size - 1)) & 1:
        minus = "-"

    twocomp_lit = (lit + (1 << size)) % (1 << size)

    # add c postfix for large numbers
    postfix = "U" if not sign else ""
    postfix += "LL"
    # postfix = "ULL"
    # if size > 32:
    # 	postfix += "L"
    # if size > 64:
    # 	postfix += "L"

    ret = CodeString(minus + str(lit) + postfix, True, size, sign, line_infos=self.line_info)
    ret.is_literal = True
    return ret


def number_literal(self: behav.NumberLiteral, context: TransformerContext):
    """Generate generic number literal. Currently unused."""

    lit = int(self.value)
    size = min(lit.bit_length(), 64)
    sign = lit < 0

    twocomp_lit = (lit + (1 << 64)) % (1 << 64)

    postfix = "U" if not sign else ""
    postfix += "LL"
    # postfix = "ULL"
    # if size > 32:
    # 	postfix += "L"
    # if size > 64:
    # 	postfix += "L"

    return CodeString(str(twocomp_lit) + postfix, True, size, sign, line_infos=self.line_info)


def group(self: behav.Group, context: TransformerContext):
    """Generate a group of expressions."""

    expr = self.expr.generate(context)
    if isinstance(expr, CodeString):
        expr.code = f"({expr.code})"
        expr.line_infos.append(self.line_info)
    else:
        expr = f"({expr})"
    return expr


def operator(self: behav.Operator, context: TransformerContext):
    return self.op


def code_literal(self: behav.CodeLiteral, context: TransformerContext):
    return CodeString(self.val, False, context.native_size, False, line_infos=self.line_info)
