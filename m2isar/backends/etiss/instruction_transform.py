# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

"""Recursive tree traversal methods to generate behavior code."""

import logging
from math import log2
from itertools import chain
from string import Template
from functools import singledispatchmethod

from ... import M2NameError, M2SyntaxError, M2ValueError, flatten
from ...metamodel import arch, behav, type_info, attribute_info
from ...metamodel.code_info import LineInfoPlacement
from ...metamodel.utils.ExprVisitor import ExprVisitor
from . import CodeInfoTracker, replacements
from .instruction_utils import (FN_VAL_REPL, MEM_VAL_REPL, CodePartsContainer,
                                CodeString, FnID, MemID, TransformerContext,
								data_type_map, actual_size)

# pylint: disable=unused-argument

logger = logging.getLogger("instr_transform")


class InstructionTransformVisitor(ExprVisitor):
	"""Visitor to transform M2-ISA-R model expressions to C code strings for ETISS."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context: TransformerContext):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}")

	@generate.register
	def _(self, expr: behav.Operation, context: TransformerContext):
		"""Generate an `Operation` model object. Essentially generate all children,
		concatenate their code, and add exception behavior if needed.
		"""

		args: "list[CodeString]" = []
		code_lines = []

		for stmt in expr.statements:
			c = self.generate(stmt, context)

			if isinstance(c, list):
				args.extend(flatten(c))
			else:
				args.append(c)

		if expr.line_info is not None and context.generate_coverage:
			CodeInfoTracker.insert(context.arch_name, expr.line_info)
			code_lines.append(context.wrap_codestring(f"etiss_coverage_count(1, {expr.line_info.id});"))

		for arg in args:
			if arg.is_mem_access:
				raise_fn_call = self.generate(behav.Conditional(
					[behav.CodeLiteral('cpu->exception')],
					[behav.ProcedureCall(
						context.mem_raise_fn,
						[behav.CodeLiteral("cpu->exception")]
					)]
				), context)

				raise_fn_str = [context.wrap_codestring(c.code, c.static) for c in raise_fn_call]

			before_line_infos = []
			after_line_infos = []

			if context.generate_coverage:
				for l in flatten(arg.line_infos):
					if l is not None:
						CodeInfoTracker.insert(context.arch_name, l)

						if l.placement == LineInfoPlacement.BEFORE:
							before_line_infos.append(str(l.id))

						elif l.placement == LineInfoPlacement.AFTER:
							after_line_infos.append(str(l.id))

			if len(before_line_infos) > 0:
				code_lines.append(context.wrap_codestring(f"etiss_coverage_count({len(before_line_infos)}, {', '.join(before_line_infos)});"))

			for f_id in arg.function_calls:
				code_lines.append(context.wrap_codestring(f'{data_type_map[f_id.fn_call.data_type]}{actual_size(f_id.fn_call.size)} {FN_VAL_REPL}{f_id.fn_id};', arg.static))
				code_lines.append(context.wrap_codestring(f'{FN_VAL_REPL}{f_id.fn_id} = {f_id.args};', arg.static))
				code_lines.append(context.wrap_codestring('if (cpu->return_pending) goto instr_exit_" + std::to_string(ic.current_address_) + ";', arg.static))

			for m_id in arg.read_mem_ids:
				code_lines.append(context.wrap_codestring(f'etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};'))
				code_lines.append(context.wrap_codestring(f'cpu->exception |= (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});'))
				code_lines.extend(raise_fn_str)

			for m_id in arg.write_mem_ids:
				code_lines.append(context.wrap_codestring(f'etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};'))

			code_lines.append(context.wrap_codestring(f'{arg.code}', arg.static))

			if len(after_line_infos) > 0:
				code_lines.append(context.wrap_codestring(f"etiss_coverage_count({len(after_line_infos)}, {', '.join(after_line_infos)});"))

			for m_id in arg.write_mem_ids:
				code_lines.append(context.wrap_codestring(f'cpu->exception |= (*(system->dwrite))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});'))
				code_lines.extend(raise_fn_str)

		container = CodePartsContainer()
		container.initial_required = '\n'.join(code_lines)

		# only generate return statements if not in a function
		if not context.ignore_static:
			container.initial_required += '\ncp.code() += "instr_exit_" + std::to_string(ic.current_address_) + ":\\n";'
			container.initial_required += '\ncp.code() += "cpu->instructionPointer = cpu->nextPc;\\n";'
			return_conditions = []
			return_needed = any((
				context.generates_exception,
				attribute_info.InstrAttribute.NO_CONT in context.attributes,
				attribute_info.InstrAttribute.COND in context.attributes,
				attribute_info.InstrAttribute.FLUSH in context.attributes
			))

			if context.generates_exception:
				return_conditions.append("cpu->return_pending")
				return_conditions.append("cpu->exception")

			if attribute_info.InstrAttribute.NO_CONT in context.attributes and attribute_info.InstrAttribute.COND in context.attributes:
				return_conditions.append(f'cpu->nextPc != " + std::to_string(ic.current_address_ + {int(context.instr_size / 8)}) + "ULL')

			elif attribute_info.InstrAttribute.NO_CONT in context.attributes:
				return_conditions.clear()

			if attribute_info.InstrAttribute.FLUSH in context.attributes:
				container.initial_required = 'cp.code() += "cpu->exception = ETISS_RETURNCODE_RELOADBLOCKS;\\n";\n' + container.initial_required
				return_conditions.clear()

			if return_needed:
				cond_str = ("if (" + " || ".join(return_conditions) + ") ") if return_conditions else ""
				container.appended_returning_required = f'cp.code() += "{cond_str}return cpu->exception;\\n";'

		elif attribute_info.FunctionAttribute.ETISS_TRAP_ENTRY_FN in context.attributes:
			container.initial_required = "cpu->return_pending = 1;\ncpu->exception = 0;\n" + container.initial_required

		return container

	@generate.register
	def _(self, expr: behav.Block, context: TransformerContext):
		stmts = [self.generate(stmt, context) for stmt in expr.statements]

		pre = [CodeString("{ // block", attribute_info.StaticAttribute.READ, None, None, line_infos=expr.line_info)]
		post = [CodeString("} // block", attribute_info.StaticAttribute.READ, None, None)]

		if not context.ignore_static:
			pre.append(CodeString("{ // block", attribute_info.StaticAttribute.NONE, None, None))
			post.insert(0, CodeString("} // block", attribute_info.StaticAttribute.NONE, None, None))

		return pre + stmts + post

	@generate.register
	def _(self, expr: behav.Return, context: TransformerContext):
		if context.instr_size != 0:
			raise M2SyntaxError('Return statements are not allowed in instruction behavior!')

		if expr.expr is not None:
			c = self.generate(expr.expr, context)
			c.code = f'return {c.code};'
			c.line_infos.append(expr.line_info)
		else:
			c = CodeString("return;", attribute_info.StaticAttribute.RW, None, None, line_infos=expr.line_info)

		return c

	@generate.register
	def _(self, expr: behav.Break, context: TransformerContext):
		return CodeString("break;", attribute_info.StaticAttribute.RW, None, None, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.ScalarDefinition, context: TransformerContext):
		"""Generate a scalar definition. Calculates the actual required data width and generates
		a variable instantiation."""
		if context.static_scalars:
			if context.ignore_static:
				static = attribute_info.StaticAttribute.RW
			else:
				static = expr.scalar.static
		else:
			static = attribute_info.StaticAttribute.NONE

		actual_size = 1 << (expr.scalar.ty.size - 1).bit_length()
		actual_size = max(actual_size, 8)

		return CodeString(
			f'{data_type_map[expr.scalar.ty.kind]}{actual_size} {expr.scalar.name}',
			static,
			expr.scalar.ty.size,
			expr.scalar.ty.kind == type_info.TypeKind.TYPE_INT,
			line_infos=expr.line_info,
		)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context: TransformerContext):
		"""Generate a procedure call (Function call without usage of the return value)."""
		fn_args = [self.generate(arg, context) for arg in expr.args]

		# extract function object reference
		ref = expr.ref_or_name if isinstance(expr.ref_or_name, arch.Function) else None
		name = ref.name if isinstance(expr.ref_or_name, arch.Function) else expr.ref_or_name

		if ref is not None:
			# if there is a function object, use its information
			fn = ref


			# determine if procedure call is entirely static
			static = attribute_info.StaticAttribute.READ if fn.static and all(arg.static != attribute_info.StaticAttribute.NONE for arg in fn_args) else attribute_info.StaticAttribute.NONE

			# convert singular static arguments
			if not static:
				context.used_arch_data = True
				for arg in fn_args:
					if arg.static and not arg.is_literal:
						arg.code = context.make_static(arg.code, arg.signed)

			# generate argument string, add ETISS arch data if required
			arch_args = ['cpu', 'system', 'plugin_pointers'] if attribute_info.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (not fn.static and not fn.extern) else []
			arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

			# check if any argument is a memory access
			mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

			# update affected and dependent registers
			regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
			context.dependent_regs.update(regs_affected)

			# add special behavior if this function is an exception entry point
			exc_code = ""

			if attribute_info.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN in fn.attributes:
				context.generates_exception = True

			if attribute_info.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn.attributes:
				context.generates_exception = True

				if fn.ty.size is not None:
					exc_code = "cpu->exception = "

			c = CodeString(f'{exc_code}{fn.name}({arg_str});', static, None, None, line_infos=[expr.line_info] + [x.line_infos for x in fn_args])
			c.mem_ids = mem_ids
			if fn.throws and not context.ignore_static:
				c.check_trap = True

				cond = "if (cpu->return_pending) " if fn.throws == attribute_info.FunctionThrows.MAYBE else ""
				c2 = CodeString(cond + 'goto instr_exit_" + std::to_string(ic.current_address_) + ";', static, None, None)

				pre = [CodeString("{ // procedure", attribute_info.StaticAttribute.READ, None, None), CodeString("{ // procedure", attribute_info.StaticAttribute.NONE, None, None)]
				post = [CodeString("} // procedure", attribute_info.StaticAttribute.NONE, None, None), CodeString("} // procedure", attribute_info.StaticAttribute.READ, None, None)]

				return pre + [c, c2] + post

			return c

		raise M2NameError(f'Function {name} not recognized!')

	@generate.register
	def _(self, expr: behav.FunctionCall, context: TransformerContext):
		"""Generate a regular function call (with further use of return value)."""
		fn_args = [self.generate(arg, context) for arg in expr.args]

		# extract function object reference
		ref = expr.ref_or_name if isinstance(expr.ref_or_name, arch.Function) else None
		name = ref.name if isinstance(expr.ref_or_name, arch.Function) else expr.ref_or_name

		if ref is not None:
			# if there is a function object, use its information

			fn = ref

			# determine if function call is entirely static
			static = attribute_info.StaticAttribute.READ if fn.static and all(arg.static != attribute_info.StaticAttribute.NONE for arg in fn_args) else attribute_info.StaticAttribute.NONE

			# convert singular static arguments
			if not static:
				context.used_arch_data = True
				for arg in fn_args:
					if arg.static and not arg.is_literal:
						arg.code = context.make_static(arg.code, arg.signed)

			# generate argument string, add ETISS arch data if required
			arch_args = ['cpu', 'system', 'plugin_pointers'] if attribute_info.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (not fn.static and not fn.extern) else []
			arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

			# keep track of signedness of function return value
			signed = fn.ty.kind == type_info.TypeKind.TYPE_INT
			# keep track of affected registers
			regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))

			c = CodeString(f'{fn.name}({arg_str})', static, fn.ty.size, signed, regs_affected, [expr.line_info] + [x.line_infos for x in fn_args])
			c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

			if fn.throws and not context.ignore_static:
				fn_id = FnID(fn, context.fn_var_count, c)
				repl_c = CodeString(f'{FN_VAL_REPL}{context.fn_var_count}', static, fn.ty.size, signed, regs_affected)
				repl_c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))
				repl_c.function_calls.append(fn_id)
				context.fn_var_count += 1
				return repl_c

			return c

		raise M2NameError(f'Function {name} not recognized!')

	@generate.register
	def _(self, expr: behav.Callable, context: TransformerContext):
		# Callable is the base class; dispatch to specific subclass handler
		if isinstance(expr, behav.FunctionCall):
			return self.generate(expr, context)
		elif isinstance(expr, behav.ProcedureCall):
			return self.generate(expr, context)
		raise M2SyntaxError(f"Unsupported callable node type {type(expr).__name__}")

	@generate.register
	def _(self, expr: behav.Assignment, context: TransformerContext):
		"""Generate an assignment expression"""

		# generate target and value expressions
		target: CodeString = self.generate(expr.target, context)
		expr_str: CodeString = self.generate(expr.expr, context)

		# check staticness
		static = bool(target.static & attribute_info.StaticAttribute.WRITE) and bool(expr_str.static)

		if not expr_str.static and bool(target.static & attribute_info.StaticAttribute.WRITE) and not context.ignore_static:
			raise M2ValueError('Static target cannot be assigned to non-static expression!')

		# convert assignment value staticness
		if expr_str.static and not expr_str.is_literal:
			if bool(target.static & attribute_info.StaticAttribute.WRITE):
				if context.ignore_static:
					expr_str.code = Template(f'{expr_str.code}').safe_substitute(**replacements.rename_dynamic)
				else:
					expr_str.code = Template(f'{expr_str.code}').safe_substitute(**replacements.rename_static)
			else:
				expr_str.code = context.make_static(expr_str.code, expr_str.signed)

		# convert target staticness
		if bool(target.static & attribute_info.StaticAttribute.READ):
			target.code = Template(target.code).safe_substitute(replacements.rename_write)

		# keep track of affected and dependent registers
		context.affected_regs.update(target.regs_affected)
		context.dependent_regs.update(expr_str.regs_affected)

		if not target.is_mem_access and not expr_str.is_mem_access:
			if actual_size(target.size) > target.size:
				if target.signed:
					shift = actual_size(target.size) - target.size
					expr_str.code = f'(((etiss_int{actual_size(target.size)})({expr_str.code})) << {shift}) >> {shift}'
				else:
					mask = (1 << target.size) - 1
					mask_bits = log2(mask)
					if mask_bits > 64:
						mask64 = (1 << 64) - 1
						low = mask & mask64
						high = mask >> 64
						mask_code = f"(((etiss_int128){hex(high)}ULL << 64) | {hex(low)}ULL)"
					else:
						mask_code = f"{hex(mask)}ULL"
					expr_str.code = f'({expr_str.code}) & {mask_code}'
		else:
			context.generates_exception = True

			for m_id in expr_str.mem_ids:
				m_id.write = False


			if target.is_mem_access:
				if len(target.mem_ids) != 1:
					raise M2SyntaxError('Only one memory access is allowed as assignment target!')

				target.mem_ids[0].write = True


		c = CodeString(f"{target.code} = {expr_str.code};", static, None, None, line_infos=[expr.line_info] + target.line_infos + expr_str.line_infos)

		c.function_calls.extend(target.function_calls)
		c.function_calls.extend(expr_str.function_calls)

		c.mem_ids.extend(target.mem_ids)
		c.mem_ids.extend(expr_str.mem_ids)

		return c

	@generate.register
	def _(self, expr: behav.BinaryOperation, context: TransformerContext):
		"""Generate a binary expression"""

		# generate LHS and RHS of the expression
		left = self.generate(expr.left, context)
		op = expr.op
		right = self.generate(expr.right, context)

		# convert staticness if needed
		if not left.static and right.static and not right.is_literal:
			right.code = context.make_static(right.code, right.signed)
		if not right.static and left.static and not left.is_literal:
			left.code = context.make_static(left.code, left.signed)

		c = CodeString(
			f'{left.code} {op.value} {right.code}',
			left.static and right.static,
			arch.get_const_or_val(left.size) if arch.get_const_or_val(left.size) > arch.get_const_or_val(right.size) else arch.get_const_or_val(right.size),
			left.signed or right.signed,
			set.union(left.regs_affected, right.regs_affected),
			[expr.line_info] + left.line_infos + right.line_infos,
		)
		# keep track of any memory accesses
		c.mem_ids = left.mem_ids + right.mem_ids
		return c

	@generate.register
	def _(self, expr: behav.UnaryOperation, context: TransformerContext):
		op = expr.op
		right = self.generate(expr.right, context)

		c = CodeString(f'{op.value}({right.code})', right.static, right.size, right.signed, right.regs_affected, [expr.line_info] + right.line_infos)
		c.mem_ids = right.mem_ids
		return c

	@generate.register
	def _(self, expr: behav.Conditional, context: TransformerContext):
		"""Generate a conditional ('if' with optional 'else if' and 'else' blocks)"""

		# generate conditions and statement blocks
		conds: "list[CodeString]" = [self.generate(x, context) for x in expr.conds]
		stmts: "list[list[CodeString]]" = []

		for cond in conds[1:]:
			conds[0].mem_ids.extend(cond.mem_ids)
			cond.mem_ids.clear()

		for stmt in expr.stmts:
			if isinstance(stmt, list):
				ret = []
				for stmt_ in stmt:
					ret_ = self.generate(stmt_, context)
					ret.append(ret_)
			else:
				ret = self.generate(stmt, context)

			if isinstance(ret, list):
				stmts.append(ret)
			else:
				stmts.append([ret])

		# check if all conditions are static
		static = all(x.static for x in conds)
		outputs: "list[CodeString]" = []

		for cond in conds:
			for m_id in cond.mem_ids:
				m_id.write = False

			if cond.static and not static:
				cond.code = context.make_static(cond.code)
				cond.static = False

		conds[0].code = f'if ({conds[0].code}) {{ // conditional'
		conds[0].line_infos.append(expr.line_info)
		outputs.append(conds[0])
		if not static:
			context.dependent_regs.update(conds[0].regs_affected)

		# generate first statement block
		outputs.extend(flatten(stmts[0]))

		# generate closing brace
		outputs.append(CodeString("} // conditional", static, None, None))

		for elif_cond, elif_stmts in zip(conds[1:], stmts[1:]):
			elif_cond.code = f' else if ({elif_cond.code}) {{ // conditional'
			outputs.append(elif_cond)
			if not static:
				context.dependent_regs.update(elif_cond.regs_affected)

			outputs.extend(flatten(elif_stmts))
			outputs.append(CodeString("} // conditional", static, None, None))

		if len(conds) < len(stmts):
			outputs.append(CodeString("else { // conditional", static, None, None))
			outputs.extend(flatten(stmts[-1]))
			outputs.append(CodeString("} // conditional", static, None, None))

		return outputs

	@generate.register
	def _(self, expr: behav.Loop, context: TransformerContext):
		"""Generate 'while' and 'do .. while' loops."""

		cond: CodeString = self.generate(expr.cond, context)
		stmts: "list[CodeString]" = []

		for stmt in expr.stmts:
			if isinstance(stmt, list):
				for stmt2 in stmt:
					stmts.append(self.generate(stmt2, context))
			else:
				stmts.append(self.generate(stmt, context))

		if not cond.static:
			context.dependent_regs.update(cond.regs_affected)

		outputs: "list[CodeString]" = []

		if expr.post_test:
			start_c = CodeString("do", cond.static, None, None)
			end_c = cond
			end_c.code = f'while ({end_c.code})'
		else:
			start_c = cond
			start_c.code = f'while ({start_c.code})'
			end_c = CodeString("", cond.static, None, None)

		outputs.append(start_c)
		outputs.extend(flatten(stmts))
		outputs.append(end_c)

		return outputs

	@generate.register
	def _(self, expr: behav.Ternary, context: TransformerContext):
		"""Generate a ternary expression."""

		# generate condition and 'then' and 'else' statements
		cond = self.generate(expr.cond, context)
		then_expr = self.generate(expr.then_expr, context)
		else_expr = self.generate(expr.else_expr, context)

		static = attribute_info.StaticAttribute.NONE not in [x.static for x in (cond, then_expr, else_expr)]

		# convert singular static sub-components
		if not static:
			if cond.static and not cond.is_literal:
				cond.code = context.make_static(cond.code, cond.signed)
			if then_expr.static and not then_expr.is_literal:
				then_expr.code = context.make_static(then_expr.code, then_expr.signed)
			if else_expr.static and not else_expr.is_literal:
				else_expr.code = context.make_static(else_expr.code, else_expr.signed)

		c = CodeString(
			f'({cond}) ? ({then_expr}) : ({else_expr})',
			static,
			then_expr.size if then_expr.size > else_expr.size else else_expr.size,
			then_expr.signed or else_expr.signed,
			set.union(cond.regs_affected, then_expr.regs_affected, else_expr.regs_affected),
			[expr.line_info] + cond.line_infos + then_expr.line_infos + else_expr.line_infos,
		)
		c.mem_ids = cond.mem_ids + then_expr.mem_ids + else_expr.mem_ids

		return c

	@generate.register
	def _(self, expr: behav.TypeConv, context: TransformerContext):
		"""Generate a type cast expression"""

		# generate the expression to be type-casted
		expr_str = self.generate(expr.expr, context)

		# if only width should be changed assume data type remains unchanged
		if expr.data_type is None:
			expr.data_type = type_info.TypeKind.TYPE_INT if expr_str.signed else type_info.TypeKind.TYPE_UINT

		# if only data type should be changed assume width remains unchanged
		if expr.size is None:
			expr._size = expr_str.size


		code_str = expr_str.code

		# sign extension for non-2^N datatypes
		if expr.data_type == type_info.TypeKind.TYPE_INT and actual_size(expr_str.size) != expr_str.size:
			target_size = actual_size(expr.size)

			if isinstance(expr.size, int):
				code_str = f'((etiss_int{target_size})(((etiss_int{target_size}){expr_str.code}) << ({target_size - expr.size})) >> ({target_size - expr.size}))'
			else:
				code_str = f'((etiss_int{target_size})(({expr_str.code}) << ({target_size} - {expr.size})) >> ({target_size} - {expr.size}))'
		# normal type conversion
		# TODO: check if behavior adheres to CoreDSL 2 spec
		else:
			code_str = f'({data_type_map[expr.data_type]}{actual_size(expr.size)})({code_str})'

		c = CodeString(code_str, expr_str.static, expr.size, expr.data_type == type_info.TypeKind.TYPE_INT, expr_str.regs_affected, line_infos=[expr.line_info] + expr_str.line_infos)
		c.mem_ids = expr_str.mem_ids

		return c

	@generate.register
	def _(self, expr: behav.NamedReference, context: TransformerContext):
		"""Generate a named reference"""

		# extract referred object
		referred_var = expr.reference

		static = attribute_info.StaticAttribute.NONE

		name = referred_var.name

		# check if static name replacement is needed
		if name in replacements.rename_static:
			name = f'${{{name}}}'
			static = attribute_info.StaticAttribute.READ

		# check which type of reference has to be generated
		if isinstance(referred_var, arch.Memory):
			# architecture constant
			if not static:
				ref = "*" if len(referred_var.children) > 0 else ""
				name = f"{ref}{replacements.default_prefix}{name}"
			signed = False
			size = referred_var.ty.size
			context.used_arch_data = True

		elif isinstance(referred_var, arch.BitFieldDescr):
			# function argument
			signed = referred_var.ty.kind == type_info.TypeKind.TYPE_INT
			size = referred_var.ty.size
			static = attribute_info.StaticAttribute.READ

		elif isinstance(referred_var, arch.Scalar):
			assert isinstance(referred_var.ty, type_info.PrimitiveType)
			signed = referred_var.ty.kind == type_info.TypeKind.TYPE_INT
			size = referred_var.ty.size
			if context.static_scalars:
				static = referred_var.static

		elif isinstance(referred_var, arch.Constant):
			signed = referred_var.value < 0
			size = context.native_size
			static = attribute_info.StaticAttribute.READ
			name = f'{referred_var.value}'

		elif isinstance(referred_var, arch.FnParam):
			signed = referred_var.ty.kind ==  type_info.TypeKind.TYPE_INT
			size = referred_var.ty.size
			static = attribute_info.StaticAttribute.RW

		elif isinstance(referred_var, arch.Intrinsic):
			if context.ignore_static:
				raise TypeError("intrinsic not allowed in function")

			signed = referred_var.ty.kind == type_info.TypeKind.TYPE_INT
			size = referred_var.ty.size
			static = attribute_info.StaticAttribute.READ

			if referred_var == context.intrinsics["__encoding_size"]:
				name = str(context.instr_size // 8)

		else:
			raise TypeError("wrong type")

		if context.ignore_static:
			static = attribute_info.StaticAttribute.RW

		return CodeString(name, static, size, signed, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.IndexedReference, context: TransformerContext):
		"""Generate an indexed reference expression (for register banks or memory)."""

		name = expr.reference.name

		# generate index expression
		index = self.generate(expr.index, context)

		referred_mem = expr.reference

		if isinstance(referred_mem, arch.Memory):
			context.used_arch_data = True

		size = referred_mem.ty.size

		# convert static index expression
		index_code = index.code
		if index.static and not context.ignore_static and not index.is_literal:
			index.code = context.make_static(index.code, index.signed)

		if context.ignore_static:
			static = attribute_info.StaticAttribute.RW
		else:
			static = attribute_info.StaticAttribute.NONE

		if attribute_info.MemoryAttribute.IS_MAIN_MEM in referred_mem.attributes:
			# generate memory access if main memory is accessed
			size = expr.ty.size
			c = CodeString(f'{MEM_VAL_REPL}{context.mem_var_count}', static, size, False, line_infos=[expr.line_info] + index.line_infos)
			if (expr.right != None):
				# Use a simple base address on one site atleast for ranged_mem access.
				# Index Codestring is forwarded into MemID class.
				right = self.generate(expr.right, context)
				if(type(expr.index) == behav.NamedReference):
					c.mem_ids.append(MemID(referred_mem, context.mem_var_count, index, size))
				elif(type(expr.right) == behav.NamedReference):
					c.mem_ids.append(MemID(referred_mem, context.mem_var_count, right, size))
				else:
					raise(f"IndexedExpr ist needs to be static on one side: But Type is Left: {type(expr.index)} and Right: {type(expr.index)}")
			else:
				c.mem_ids.append(MemID(referred_mem, context.mem_var_count, index, size))
			context.mem_var_count += 1
			return c

		# generate normal indexed access if not
		code_str = f'{replacements.prefixes.get(name, replacements.default_prefix)}{name}[{index.code}]'
		if len(referred_mem.children) > 0:
			code_str = '*' + code_str
		c = CodeString(code_str, static, size, False, line_infos=[expr.line_info] + index.line_infos)
		if attribute_info.MemoryAttribute.IS_MAIN_REG in referred_mem.attributes:
			c.regs_affected.add(index_code)
		return c

	@generate.register
	def _(self, expr: behav.SliceOperation, context: TransformerContext):
		"""Generate a slice expression"""

		# generate expression to be sliced and lower and upper slice bound
		expr_str = self.generate(expr.expr, context)
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		static = attribute_info.StaticAttribute.NONE not in [x.static for x in (expr_str, left, right)]

		if not static:
			if expr_str.static and not expr_str.is_literal:
				expr_str.code = context.make_static(expr_str.code, expr_str.signed)
			if left.static and not left.is_literal:
				left.code = context.make_static(left.code, left.signed)
			if right.static and not right.is_literal:
				right.code = context.make_static(right.code, right.signed)

		# slice with fixed integers if slice bounds are integers
		try:
			new_size = int(left.code.replace("U", "").replace("L", "")) - int(right.code.replace("U", "").replace("L", "")) + 1
			mask = (1 << (int(left.code.replace("U", "").replace("L", "")) - int(right.code.replace("U", "").replace("L", "")) + 1)) - 1
			mask_bits = log2(mask)
			if mask_bits > 64:
				mask64 = (1 << 64) - 1
				low = mask & mask64
				high = mask >> 64
				mask_code = f"((((etiss_int128)){hex(high)}ULL << 64) | {hex(low)}ULL)"
			else:
				mask_code = f"{hex(mask)}ULL"
			mask = f"{mask_code}"
			simple_mask = True

		# slice with actual lower and upper bound code if not possible to slice with integers
		except ValueError:
			new_size = expr_str.size
			mask = f"((1 << (({left.code}) - ({right.code}) + 1)) - 1)"
			simple_mask = False

		if simple_mask and (int(right.code.replace("U", "").replace("L", "")) == 0):
			# no need to shift zeros steps
			code = f"(({expr_str.code}) & {mask})"
		else:
			code = f"((({expr_str.code}) >> ({right.code})) & {mask})"
		c = CodeString(code, static, new_size, expr_str.signed,
			set.union(expr_str.regs_affected, left.regs_affected, right.regs_affected), [expr.line_info] + expr_str.line_infos + left.line_infos + right.line_infos)
		c.mem_ids = expr_str.mem_ids + left.mem_ids + right.mem_ids
		return c

	@generate.register
	def _(self, expr: behav.ConcatOperation, context: TransformerContext):
		"""Generate a concatenation expression"""

		# generate LHS and RHS operands
		left: CodeString = self.generate(expr.left, context)
		right: CodeString = self.generate(expr.right, context)

		if not left.static and right.static and not right.is_literal:
			right.code = context.make_static(right.code, right.signed)
		if not right.static and left.static and not left.is_literal:
			left.code = context.make_static(left.code, left.signed)

		new_size = left.size + right.size
		c = CodeString(f"((({left.code}) << {right.size}) | ({right.code}))", left.static and right.static, new_size, left.signed or right.signed,
			set.union(left.regs_affected, right.regs_affected), [expr.line_info] + left.line_infos + right.line_infos)
		c.mem_ids = left.mem_ids + right.mem_ids
		return c

	@generate.register
	def _(self, expr: behav.Literal, context: TransformerContext):
		if expr.ty.kind is type_info.TypeKind.TYPE_STR:
			return CodeString(f'"{expr.value}"', attribute_info.StaticAttribute.READ, None, False, line_infos=expr.line_info)

		# old number NumberLiteral
		elif expr.ty.kind == type_info.TypeKind.TYPE_NONE:
			lit = int(expr.value)
			size = min(lit.bit_length(), 64)
			sign = lit < 0


			# TODO: Look in diff. U is sometimes there for negative  vals!!!
			twocomp_lit = (lit + (1 << 64)) % (1 << 64)
			postfix = "U" if not sign else ""
			postfix += "LL"
			return CodeString(str(twocomp_lit) + postfix, True, size, sign, line_infos=expr.line_info)
		# IntLiteral
		else:
			assert(expr.ty.kind in [type_info.TypeKind.TYPE_INT, type_info.TypeKind.TYPE_UINT])
			lit = int(expr.value)
			if expr.ty.size is None:
				size = lit.bit_length()
			size = min(expr.ty.size, 128)

			if expr.value < 0 or expr.ty.kind == type_info.TypeKind.TYPE_INT:
			# 	raise M2ValueError('Negative literal value cannot be represented as unsigned integer!')
				sign = True
			else:
				sign = False


			minus = ""
			if lit > 0 and sign and (lit >> (size - 1)) & 1:
				minus = "-"
				sign = True

			_ = (lit + (1 << size)) % (1 << size)

			postfix = "U" if not sign else ""
			postfix += "LL"

			ret = CodeString(minus + str(lit) + postfix, True, size, sign, line_infos=expr.line_info)
			ret.is_literal = True
			return ret

	@generate.register
	def _(self, expr: behav.CodeLiteral, context: TransformerContext):
		return CodeString(expr.val, False, context.native_size, False, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.Operator, context: TransformerContext):
		return expr.value

	@generate.register
	def _(self, expr: behav.Group, context: TransformerContext):
		"""Generate a group of expressions."""

		expr_str = self.generate(expr.expr, context)
		if isinstance(expr_str, CodeString):
			expr_str.code = f'({expr_str.code})'
			expr_str.line_infos.append(expr.line_info)
		else:
			expr_str = f'({expr_str})'
		return expr_str
