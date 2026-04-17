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
from ...metamodel import arch, behav
from ...metamodel.code_info import LineInfoPlacement
from ...metamodel.utils.ExprVisitor import ExprVisitor
from . import CodeInfoTracker, replacements
from .instruction_utils import (FN_VAL_REPL, MEM_VAL_REPL, CodePartsContainer,
                                CodeString, FnID, MemID, StaticType,
                                TransformerContext, data_type_map)

# pylint: disable=unused-argument

logger = logging.getLogger("instr_transform")


class InstructionTransformVisitor(ExprVisitor):
	"""Visitor to transform M2-ISA-R model expressions to C code strings for ETISS."""

	@singledispatchmethod
	def generate(self, expr: behav.BaseNode, context: TransformerContext):
		raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}")

	@generate.register
	def _(self, expr: behav.Operation, context: TransformerContext):
		"""Generate an `Operation` model object."""

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
				code_lines.append(context.wrap_codestring(f'{data_type_map[f_id.fn_call.data_type]}{f_id.fn_call.actual_size} {FN_VAL_REPL}{f_id.fn_id};', arg.static))
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

		if not context.ignore_static:
			container.initial_required += '\ncp.code() += "instr_exit_" + std::to_string(ic.current_address_) + ":\\n";'
			container.initial_required += '\ncp.code() += "cpu->instructionPointer = cpu->nextPc;\\n";'
			return_conditions = []
			return_needed = any((
				context.generates_exception,
				arch.InstrAttribute.NO_CONT in context.attributes,
				arch.InstrAttribute.COND in context.attributes,
				arch.InstrAttribute.FLUSH in context.attributes
			))

			if context.generates_exception:
				return_conditions.append("cpu->return_pending")
				return_conditions.append("cpu->exception")

			if arch.InstrAttribute.NO_CONT in context.attributes and arch.InstrAttribute.COND in context.attributes:
				return_conditions.append(f'cpu->nextPc != " + std::to_string(ic.current_address_ + {int(context.instr_size / 8)}) + "ULL')

			elif arch.InstrAttribute.NO_CONT in context.attributes:
				return_conditions.clear()

			if arch.InstrAttribute.FLUSH in context.attributes:
				container.initial_required = 'cp.code() += "cpu->exception = ETISS_RETURNCODE_RELOADBLOCKS;\\n";\n' + container.initial_required
				return_conditions.clear()

			if return_needed:
				cond_str = ("if (" + " || ".join(return_conditions) + ") ") if return_conditions else ""
				container.appended_returning_required = f'cp.code() += "{cond_str}return cpu->exception;\\n";'

		elif arch.FunctionAttribute.ETISS_TRAP_ENTRY_FN in context.attributes:
			container.initial_required = "cpu->return_pending = 1;\ncpu->exception = 0;\n" + container.initial_required

		return container

	@generate.register
	def _(self, expr: behav.Block, context: TransformerContext):
		stmts = [self.generate(stmt, context) for stmt in expr.statements]

		pre = [CodeString("{ // block", StaticType.READ, None, None, line_infos=expr.line_info)]
		post = [CodeString("} // block", StaticType.READ, None, None)]

		if not context.ignore_static:
			pre.append(CodeString("{ // block", StaticType.NONE, None, None))
			post.insert(0, CodeString("} // block", StaticType.NONE, None, None))

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
			c = CodeString("return;", StaticType.RW, None, None, line_infos=expr.line_info)

		return c

	@generate.register
	def _(self, expr: behav.Break, context: TransformerContext):
		return CodeString("break;", StaticType.RW, None, None, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.ScalarDefinition, context: TransformerContext):
		if context.static_scalars:
			if context.ignore_static:
				static = StaticType.RW
			else:
				static = expr.scalar.static
		else:
			static = StaticType.NONE

		actual_size = 1 << (expr.scalar.size - 1).bit_length()
		actual_size = max(actual_size, 8)

		return CodeString(
			f'{data_type_map[expr.scalar.data_type]}{actual_size} {expr.scalar.name}',
			static,
			expr.scalar.size,
			expr.scalar.data_type == arch.DataType.S,
			line_infos=expr.line_info,
		)

	@generate.register
	def _(self, expr: behav.ProcedureCall, context: TransformerContext):
		fn_args = [self.generate(arg, context) for arg in expr.args]

		ref = expr.ref_or_name if isinstance(expr.ref_or_name, arch.Function) else None
		name = ref.name if isinstance(expr.ref_or_name, arch.Function) else expr.ref_or_name

		if ref is not None:
			fn = ref
			static = StaticType.READ if fn.static and all(arg.static != StaticType.NONE for arg in fn_args) else StaticType.NONE

			if not static:
				context.used_arch_data = True
				for arg in fn_args:
					if arg.static and not arg.is_literal:
						arg.code = context.make_static(arg.code, arg.signed)

			arch_args = ['cpu', 'system', 'plugin_pointers'] if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (not fn.static and not fn.extern) else []
			arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

			mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

			regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
			context.dependent_regs.update(regs_affected)

			exc_code = ""

			if arch.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN in fn.attributes:
				context.generates_exception = True

			if arch.FunctionAttribute.ETISS_TRAP_ENTRY_FN in fn.attributes:
				context.generates_exception = True

				if fn.size is not None:
					exc_code = "cpu->exception = "

			c = CodeString(f'{exc_code}{fn.name}({arg_str});', static, None, None, line_infos=[expr.line_info] + [x.line_infos for x in fn_args])
			c.mem_ids = mem_ids
			if fn.throws and not context.ignore_static:
				c.check_trap = True

				cond = "if (cpu->return_pending) " if fn.throws == arch.FunctionThrows.MAYBE else ""
				c2 = CodeString(cond + 'goto instr_exit_" + std::to_string(ic.current_address_) + ";', static, None, None)

				pre = [CodeString("{ // procedure", StaticType.READ, None, None), CodeString("{ // procedure", StaticType.NONE, None, None)]
				post = [CodeString("} // procedure", StaticType.NONE, None, None), CodeString("} // procedure", StaticType.READ, None, None)]

				return pre + [c, c2] + post

			return c

		raise M2NameError(f'Function {name} not recognized!')

	@generate.register
	def _(self, expr: behav.FunctionCall, context: TransformerContext):
		fn_args = [self.generate(arg, context) for arg in expr.args]

		ref = expr.ref_or_name if isinstance(expr.ref_or_name, arch.Function) else None
		name = ref.name if isinstance(expr.ref_or_name, arch.Function) else expr.ref_or_name

		if ref is not None:
			fn = ref
			static = StaticType.READ if fn.static and all(arg.static != StaticType.NONE for arg in fn_args) else StaticType.NONE

			if not static:
				context.used_arch_data = True
				for arg in fn_args:
					if arg.static and not arg.is_literal:
						arg.code = context.make_static(arg.code, arg.signed)

			arch_args = ['cpu', 'system', 'plugin_pointers'] if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (not fn.static and not fn.extern) else []
			arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

			signed = fn.data_type == arch.DataType.S
			regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))

			c = CodeString(f'{fn.name}({arg_str})', static, fn.size, signed, regs_affected, [expr.line_info] + [x.line_infos for x in fn_args])
			c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

			if fn.throws and not context.ignore_static:
				fn_id = FnID(fn, context.fn_var_count, c)
				repl_c = CodeString(f'{FN_VAL_REPL}{context.fn_var_count}', static, fn.size, signed, regs_affected)
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
		target: CodeString = self.generate(expr.target, context)
		expr_str: CodeString = self.generate(expr.expr, context)

		static = bool(target.static & StaticType.WRITE) and bool(expr_str.static)

		if not expr_str.static and bool(target.static & StaticType.WRITE) and not context.ignore_static:
			raise M2ValueError('Static target cannot be assigned to non-static expression!')

		if expr_str.static and not expr_str.is_literal:
			if bool(target.static & StaticType.WRITE):
				if context.ignore_static:
					expr_str.code = Template(f'{expr_str.code}').safe_substitute(**replacements.rename_dynamic)
				else:
					expr_str.code = Template(f'{expr_str.code}').safe_substitute(**replacements.rename_static)
			else:
				expr_str.code = context.make_static(expr_str.code, expr_str.signed)

		if bool(target.static & StaticType.READ):
			target.code = Template(target.code).safe_substitute(replacements.rename_write)

		context.affected_regs.update(target.regs_affected)
		context.dependent_regs.update(expr_str.regs_affected)

		if not target.is_mem_access and not expr_str.is_mem_access:
			if target.actual_size > target.size:
				if target.signed:
					shift = target.actual_size - target.size
					expr_str.code = f'(((etiss_int{target.actual_size})({expr_str.code})) << {shift}) >> {shift}'
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
		left = self.generate(expr.left, context)
		op = expr.op
		right = self.generate(expr.right, context)

		if not left.static and right.static and not right.is_literal:
			right.code = context.make_static(right.code, right.signed)
		if not right.static and left.static and not left.is_literal:
			left.code = context.make_static(left.code, left.signed)

		c = CodeString(
			f'{left.code} {op.value} {right.code}',
			left.static and right.static,
			left.size if left.size > right.size else right.size,
			left.signed or right.signed,
			set.union(left.regs_affected, right.regs_affected),
			[expr.line_info] + left.line_infos + right.line_infos,
		)
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

		outputs.extend(flatten(stmts[0]))
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
		cond = self.generate(expr.cond, context)
		then_expr = self.generate(expr.then_expr, context)
		else_expr = self.generate(expr.else_expr, context)

		static = StaticType.NONE not in [x.static for x in (cond, then_expr, else_expr)]

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
		expr_str = self.generate(expr.expr, context)

		if expr.data_type is None:
			expr.data_type = arch.DataType.S if expr_str.signed else arch.DataType.U

		if expr.size is None:
			expr._size = expr_str.size
			expr._actual_size = expr_str.actual_size


		code_str = expr_str.code

		if expr.data_type == arch.DataType.S and expr_str.actual_size != expr_str.size:
			target_size = expr.actual_size

			if isinstance(expr.size, int):
				code_str = f'((etiss_int{target_size})(((etiss_int{target_size}){expr_str.code}) << ({target_size - expr.size})) >> ({target_size - expr.size}))'
			else:
				code_str = f'((etiss_int{target_size})(({expr_str.code}) << ({target_size} - {expr.size})) >> ({target_size} - {expr.size}))'
		else:
			code_str = f'({data_type_map[expr.data_type]}{expr.actual_size})({code_str})'

		c = CodeString(code_str, expr_str.static, expr.size, expr.data_type == arch.DataType.S, expr_str.regs_affected, line_infos=[expr.line_info] + expr_str.line_infos)
		c.mem_ids = expr_str.mem_ids

		return c

	@generate.register
	def _(self, expr: behav.NamedReference, context: TransformerContext):
		referred_var = expr.reference
		static = StaticType.NONE
		name = referred_var.name

		if name in replacements.rename_static:
			name = f'${{{name}}}'
			static = StaticType.READ

		if isinstance(referred_var, arch.Memory):
			if not static:
				ref = "*" if len(referred_var.children) > 0 else ""
				name = f"{ref}{replacements.default_prefix}{name}"
			signed = False
			size = referred_var.size
			context.used_arch_data = True

		elif isinstance(referred_var, arch.BitFieldDescr):
			signed = referred_var.data_type == arch.DataType.S
			size = referred_var.size
			static = StaticType.READ

		elif isinstance(referred_var, arch.Scalar):
			signed = referred_var.data_type == arch.DataType.S
			size = referred_var.size
			if context.static_scalars:
				static = referred_var.static

		elif isinstance(referred_var, arch.Constant):
			signed = referred_var.value < 0
			size = context.native_size
			static = StaticType.READ
			name = f'{referred_var.value}'

		elif isinstance(referred_var, arch.FnParam):
			signed = referred_var.data_type == arch.DataType.S
			size = referred_var.size
			static = StaticType.RW

		elif isinstance(referred_var, arch.Intrinsic):
			if context.ignore_static:
				raise TypeError("intrinsic not allowed in function")

			signed = referred_var.data_type == arch.DataType.S
			size = referred_var.size
			static = StaticType.READ

			if referred_var == context.intrinsics["__encoding_size"]:
				name = str(context.instr_size // 8)

		else:
			raise TypeError("wrong type")

		if context.ignore_static:
			static = StaticType.RW

		return CodeString(name, static, size, signed, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.IndexedReference, context: TransformerContext):
		name = expr.reference.name
		index = self.generate(expr.index, context)
		referred_mem = expr.reference

		if isinstance(referred_mem, arch.Memory):
			context.used_arch_data = True

		size = referred_mem.size

		index_code = index.code
		if index.static and not context.ignore_static and not index.is_literal:
			index.code = context.make_static(index.code, index.signed)

		if context.ignore_static:
			static = StaticType.RW
		else:
			static = StaticType.NONE

		if arch.MemoryAttribute.IS_MAIN_MEM in referred_mem.attributes:
			size = expr.inferred_type._width
			c = CodeString(f'{MEM_VAL_REPL}{context.mem_var_count}', static, size, False, line_infos=[expr.line_info] + index.line_infos)
			c.mem_ids.append(MemID(referred_mem, context.mem_var_count, index, size))
			context.mem_var_count += 1
			return c

		code_str = f'{replacements.prefixes.get(name, replacements.default_prefix)}{name}[{index.code}]'
		if len(referred_mem.children) > 0:
			code_str = '*' + code_str
		c = CodeString(code_str, static, size, False, line_infos=[expr.line_info] + index.line_infos)
		if arch.MemoryAttribute.IS_MAIN_REG in referred_mem.attributes:
			c.regs_affected.add(index_code)
		return c

	@generate.register
	def _(self, expr: behav.SliceOperation, context: TransformerContext):
		expr_str = self.generate(expr.expr, context)
		left = self.generate(expr.left, context)
		right = self.generate(expr.right, context)

		static = StaticType.NONE not in [x.static for x in (expr_str, left, right)]

		if not static:
			if expr_str.static and not expr_str.is_literal:
				expr_str.code = context.make_static(expr_str.code, expr_str.signed)
			if left.static and not left.is_literal:
				left.code = context.make_static(left.code, left.signed)
			if right.static and not right.is_literal:
				right.code = context.make_static(right.code, right.signed)

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
		except ValueError:
			new_size = expr_str.size
			mask = f"((1 << (({left.code}) - ({right.code}) + 1)) - 1)"
			simple_mask = False

		if simple_mask and (int(right.code.replace("U", "").replace("L", "")) == 0):
			code = f"(({expr_str.code}) & {mask})"
		else:
			code = f"((({expr_str.code}) >> ({right.code})) & {mask})"
		c = CodeString(code, static, new_size, expr_str.signed,
			set.union(expr_str.regs_affected, left.regs_affected, right.regs_affected), [expr.line_info] + expr_str.line_infos + left.line_infos + right.line_infos)
		c.mem_ids = expr_str.mem_ids + left.mem_ids + right.mem_ids
		return c

	@generate.register
	def _(self, expr: behav.ConcatOperation, context: TransformerContext):
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
	def _(self, expr: behav.NumberLiteral, context: TransformerContext):
		lit = int(expr.value)
		size = min(lit.bit_length(), 64)
		sign = lit < 0

		twocomp_lit = (lit + (1 << 64)) % (1 << 64)

		postfix = "U" if not sign else ""
		postfix += "LL"

		return CodeString(str(twocomp_lit) + postfix, True, size, sign, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.IntLiteral, context: TransformerContext):
		lit = int(expr.value)
		size = min(expr.bit_size, 128)
		sign = expr.signed

		minus = ""
		if lit > 0 and sign and (lit >> (size - 1)) & 1:
			minus = "-"

		_ = (lit + (1 << size)) % (1 << size)

		postfix = "U" if not sign else ""
		postfix += "LL"

		ret = CodeString(minus + str(lit) + postfix, True, size, sign, line_infos=expr.line_info)
		ret.is_literal = True
		return ret

	@generate.register
	def _(self, expr: behav.StringLiteral, context: TransformerContext):
		return CodeString(f'"{expr.value}"', StaticType.READ, None, False, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.CodeLiteral, context: TransformerContext):
		return CodeString(expr.val, False, context.native_size, False, line_infos=expr.line_info)

	@generate.register
	def _(self, expr: behav.Operator, context: TransformerContext):
		return expr.value

	@generate.register
	def _(self, expr: behav.Group, context: TransformerContext):
		expr_str = self.generate(expr.expr, context)
		if isinstance(expr_str, CodeString):
			expr_str.code = f'({expr_str.code})'
			expr_str.line_infos.append(expr.line_info)
		else:
			expr_str = f'({expr_str})'
		return expr_str
