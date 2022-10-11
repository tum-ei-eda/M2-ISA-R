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

from ... import M2NameError, M2SyntaxError, M2ValueError
from ...metamodel import arch, behav
from . import replacements
from .instruction_utils import (MEM_VAL_REPL, CodeString, MemID, StaticType,
                                TransformerContext, data_type_map)

logger = logging.getLogger("instr_transform")

def operation(self: behav.Operation, context: TransformerContext):
	"""Generate an `Operation` model object. Essentially generate all children,
	concatenate their code, and add exception behavior if needed.
	"""

	args = [stmt.generate(context) for stmt in self.statements]

	code_str = '\n'.join(args)

	# only generate return statements if not in a function
	if not context.ignore_static:
		code_str += '\npartInit.code() += "cpu->instructionPointer = cpu->nextPc;\\n";'# + code_str
		return_conditions = []
		return_needed = any((
			context.generates_exception,
			arch.InstrAttribute.NO_CONT in context.attributes,
			arch.InstrAttribute.COND in context.attributes,
			arch.InstrAttribute.FLUSH in context.attributes
		))

		if context.generates_exception:
			return_conditions.append("cpu->return_pending")
		if arch.InstrAttribute.NO_CONT in context.attributes and arch.InstrAttribute.COND in context.attributes:
			return_conditions.append(f'cpu->nextPc != " + std::to_string(ic.current_address_ + {int(context.instr_size / 8)}) + "')
		elif arch.InstrAttribute.NO_CONT in context.attributes:
			return_conditions.clear()
		if arch.InstrAttribute.FLUSH in context.attributes:
			code_str = 'partInit.code() += "cpu->exception = ETISS_RETURNCODE_RELOADBLOCKS;\\n";\n' + code_str
			return_conditions.clear()

		if return_needed:
			cond_str = ("if (" + " | ".join(return_conditions) + ") ") if return_conditions else ""
			code_str += f'\npartInit.code() += "{cond_str}return cpu->exception;\\n";'

	elif arch.FunctionAttribute.ETISS_EXC_ENTRY in context.attributes:
		code_str = "cpu->return_pending = 1;\n" + code_str

	return code_str

def return_(self: behav.Return, context: TransformerContext):
	return f'return {self.expr.generate(context).code};'

def scalar_definition(self: behav.ScalarDefinition, context: TransformerContext):
	"""Generate a scalar definition. Calculates the actual required data width and generates
	a variable instantiation."""

	if context.static_scalars:
		if context.ignore_static:
			static = StaticType.RW
		else:
			static = self.scalar.static
	else:
		static = StaticType.NONE

	context.scalars[self.scalar.name] = self.scalar
	actual_size = 1 << (self.scalar.size - 1).bit_length()
	if actual_size < 8:
		actual_size = 8
	c = CodeString(f'{data_type_map[self.scalar.data_type]}{actual_size} {self.scalar.name}', static, self.scalar.size, self.scalar.data_type == arch.DataType.S, False)
	#c.scalar = self.scalar
	return c

def procedure_call(self: behav.ProcedureCall, context: TransformerContext):
	"""Generate a procedure call (Function call without usage of the return value)."""

	fn_args = [arg.generate(context) for arg in self.args]

	# extract function object reference
	ref = self.ref_or_name if isinstance(self.ref_or_name, arch.Function) else None
	name = ref.name if isinstance(self.ref_or_name, arch.Function) else self.ref_or_name

	if name == 'wait':
		# obsolete
		context.generates_exception = True
		return 'partInit.code() += "cpu->exception = ETISS_RETURNCODE_CPUFINISHED;\\n";'

	# elif name == 'raise':
	# 	sender, code = fn_args
	# 	exc_id = tuple([int(x.code.replace("U", "").replace("L", "")) for x in (sender, code)])
	# 	if exc_id not in replacements.exception_mapping:
	# 		raise ValueError(f'Exception {exc_id} not defined!')

	# 	context.generates_exception = True
	# 	return f'partInit.code() += "cpu->exception = {replacements.exception_mapping[exc_id]};\\n";'

	elif ref is not None:
		# if there is a function object, use its information
		fn = ref

		# determine if procedure call is entirely static
		static = StaticType.READ if fn.static and all(arg.static != StaticType.NONE for arg in fn_args) else StaticType.NONE

		# convert singular static arguments
		if not static:
			context.used_arch_data = True
			for arg in fn_args:
				if arg.static and not arg.is_literal:
					arg.code = context.make_static(arg.code)

		# generate argument string, add ETISS arch data if required
		arch_args = ['cpu', 'system', 'plugin_pointers'] if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (not fn.static and not fn.extern) else []
		arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

		# check if any argument is a memory access
		mem_access = True in [arg.is_mem_access for arg in fn_args]
		mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

		# update affected and dependent registers
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
		context.dependent_regs.update(regs_affected)

		code_str = ''

		# generate a memory access if required
		# TODO: refactor memory access generation into function
		if mem_access:
			context.generates_exception = True
			for m_id in mem_ids:
				code_str += context.wrap_codestring(f'etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};') + '\n'
				code_str += context.wrap_codestring(f'cpu->exception = (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});') + '\n'

		# add special behavior if this function is an exception entry point
		if arch.FunctionAttribute.ETISS_EXC_ENTRY in fn.attributes:
			context.generates_exception = True
			exc_code = "cpu->exception = "
		else:
			exc_code = ""

		code_str += context.wrap_codestring(f'{exc_code}{fn.name}({arg_str});')

		return code_str

	elif name.startswith('dispatch_'):
		if fn_args is None: fn_args = []

		context.used_arch_data = True

		name = name.removeprefix("dispatch_")
		arg_str = ', '.join([context.make_static(arg.code) if arg.static and not arg.is_literal else arg.code for arg in fn_args])

		mem_access = True in [arg.is_mem_access for arg in fn_args]
		mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
		context.dependent_regs.update(regs_affected)

		code_str = ''
		if mem_access:
			context.generates_exception = True
			for m_id in mem_ids:
				code_str += f'partInit.code() += "etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};\\n";\n'
				code_str += f'partInit.code() += "cpu->exception = (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});\\n";\n'

		code_str += f'partInit.code() += "{name}({arg_str});";'
		return code_str

	else:
		raise M2NameError(f'Function {name} not recognized!')

def function_call(self: behav.FunctionCall, context: TransformerContext):
	"""Generate a regular function call (with further use of return value)."""

	fn_args = [arg.generate(context) for arg in self.args]

	# extract function object reference
	ref = self.ref_or_name if isinstance(self.ref_or_name, arch.Function) else None
	name = ref.name if isinstance(self.ref_or_name, arch.Function) else self.ref_or_name

	if name == 'wait':
		# obsolete
		context.generates_exception = True
		return 'partInit.code() += "cpu->exception = ETISS_RETURNCODE_CPUFINISHED;\\n";'

	elif name == 'raise':
		# obsolete, should not happen as raise should only ever be used as a procedure
		sender, code = fn_args
		exc_id = (int(sender.code), int(code.code))
		if exc_id not in replacements.exception_mapping:
			raise M2ValueError(f'Exception {exc_id} not defined!')

		context.generates_exception = True
		return f'partInit.code() += "cpu->exception = {replacements.exception_mapping[exc_id]};\\n";'

	elif name == 'choose':
		# obsolete, old implementation of ternary
		cond, then_stmts, else_stmts = fn_args
		static = StaticType.NONE not in [x.static for x in fn_args]
		if not static:
			if cond.static and not cond.is_literal:
				cond.code = context.make_static(cond.code)
			if then_stmts.static and not then_stmts.is_literal:
				then_stmts.code = context.make_static(then_stmts.code)
			if else_stmts.static and not else_stmts.is_literal:
				else_stmts.code = context.make_static(else_stmts.code)

		c = CodeString(f'({cond}) ? ({then_stmts}) : ({else_stmts})', static, then_stmts.size if then_stmts.size > else_stmts.size else else_stmts.size, then_stmts.signed or else_stmts.signed, False, set.union(cond.regs_affected, then_stmts.regs_affected, else_stmts.regs_affected))
		c.mem_ids = cond.mem_ids + then_stmts.mem_ids + else_stmts.mem_ids

		return c

	elif name == 'sext':
		# obsolete, sign extensions are handled via type casts (unfortunately)
		expr = fn_args[0]
		target_size = context.native_size
		source_size = expr.size

		if len(fn_args) >= 2:
			target_size = int(fn_args[1].code.replace("L", "").replace("U", ""))
		if len(fn_args) >= 3:
			try:
				source_size = int(fn_args[2].code.replace("L", "").replace("U", ""))
			except ValueError:
				source_size = context.make_static(fn_args[2].code)

		if isinstance(source_size, int):
			if source_size >= target_size:
				code_str = f'(etiss_int{target_size})({expr.code})'
			else:
				if (source_size & (source_size - 1) == 0): # power of two
					code_str = f'(etiss_int{target_size})((etiss_int{source_size})({expr.code}))'
				else:
					code_str = f'((etiss_int{target_size})({expr.code}) << ({target_size - source_size})) >> ({target_size - source_size})'
		else:
			code_str = f'((etiss_int{target_size})({expr.code}) << ({target_size} - {source_size})) >> ({target_size} - {source_size})'

		c = CodeString(code_str, expr.static, target_size, True, expr.is_mem_access, expr.regs_affected)
		c.mem_ids = expr.mem_ids

		return c

	elif name == 'zext':
		# obsolete, effectively does nothing in our context
		expr = fn_args[0]
		target_size = context.native_size

		if len(fn_args) >= 2:
			target_size = int(fn_args[1].code.replace("L", "").replace("U", ""))

		c = CodeString(f'(etiss_uint{target_size})({expr.code})', expr.static, target_size, expr.signed, expr.is_mem_access, expr.regs_affected)
		c.mem_ids = expr.mem_ids

		return c

	elif name == 'shll':
		# obsolete, replaced by standard shift operators
		expr, amount = fn_args
		if expr.static and not expr.is_literal and not amount.static:
			expr.code = context.make_static(expr.code)
		if amount.static and not amount.is_literal and not expr.static:
			amount.code = context.make_static(amount.code)
		return CodeString(f'({expr.code}) << ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

	elif name == 'shrl':
		# obsolete, replaced by standard shift operators
		expr, amount = fn_args
		if expr.static and not expr.is_literal and not amount.static:
			expr.code = context.make_static(expr.code)
		if amount.static and not amount.is_literal and not expr.static:
			amount.code = context.make_static(amount.code)
		return CodeString(f'({expr.code}) >> ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

	elif name == 'shra':
		# obsolete, replaced by standard shift operators
		expr, amount = fn_args
		if expr.static and not expr.is_literal and not amount.static:
			expr.code = context.make_static(expr.code)
		if amount.static and not amount.is_literal and not expr.static:
			amount.code = context.make_static(amount.code)
		return CodeString(f'(etiss_int{expr.actual_size})({expr.code}) >> ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

	elif ref is not None:
		# if there is a function object, use its information

		fn = ref

		# determine if function call is entirely static
		static = StaticType.READ if fn.static and all(arg.static != StaticType.NONE for arg in fn_args) else StaticType.NONE

		# convert singular static arguments
		if not static:
			context.used_arch_data = True
			for arg in fn_args:
				if arg.static and not arg.is_literal:
					arg.code = context.make_static(arg.code)

		# generate argument string, add ETISS arch data if required
		arch_args = ['cpu', 'system', 'plugin_pointers'] if arch.FunctionAttribute.ETISS_NEEDS_ARCH in fn.attributes or (not fn.static and not fn.extern) else []
		arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

		# check if any argument is a memory access
		mem_access = True in [arg.is_mem_access for arg in fn_args]
		# keep track of signedness of function return value
		signed = fn.data_type == arch.DataType.S
		# keep track of affected registers
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))

		c = CodeString(f'{fn.name}({arg_str})', static, fn.size, signed, mem_access, regs_affected)
		c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

		return c

	elif name.startswith('fdispatch_'):
		# obsolete, replaced by 'extern' functions
		if fn_args is None: fn_args = []
		mem_access = True in [arg.is_mem_access for arg in fn_args]
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
		name = name.removeprefix("fdispatch_")
		arg_str = ', '.join([context.make_static(arg.code) if arg.static and not arg.is_literal else arg.code for arg in fn_args])

		c = CodeString(f'{name}({arg_str})', StaticType.NONE, 64, False, mem_access, regs_affected)
		return c

	else:
		raise M2NameError(f'Function {name} not recognized!')

def conditional(self: behav.Conditional, context: TransformerContext):
	"""Generate a conditional ('if' with optional 'else if' and 'else' blocks"""

	# generate conditions and statement blocks
	conds: "list[CodeString]" = [x.generate(context) for x in self.conds]
	stmts: "list[list[str]]" = [[y.generate(context) for y in x] for x in self.stmts]

	# check if all conditions are static
	static = all(x.static for x in conds)

	code_str = ""

	# generate memory accesses for any conditions that require one
	for cond in conds:
		if cond.is_mem_access:
			context.generates_exception = True

			for m_id in cond.mem_ids:
				code_str += context.wrap_codestring(f'etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};') + '\n'
				code_str += context.wrap_codestring(f'((${{ARCH_NAME}}*)cpu)->exception |= (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});') + '\n'

	# generate the opening 'if' statement
	cond_str = f'if ({conds[0]}) {{'
	if not static:
		cond_str = f'partInit.code() += "{cond_str}\\n";'
		context.dependent_regs.update(conds[0].regs_affected)

	code_str += cond_str + '\n'
	code_str += '\n'.join(stmts[0])
	code_str += '\n}' if static else '\npartInit.code() += "}\\n";'

	# generate any 'else if' blocks
	for elif_cond, elif_stmts in zip(conds[1:], stmts[1:]):
		elif_str = f' else if ({elif_cond}) {{'
		if not static:
			elif_str = f'\npartInit.code() += "{elif_str}\\n";'
			context.dependent_regs.update(elif_cond.regs_affected)

		code_str += elif_str + '\n'
		code_str += '\n'.join(elif_stmts)
		code_str += '\n}' if static else '\npartInit.code() += "}\\n";'

	# generate a closing 'else' statement
	if len(conds) < len(stmts):
		code_str += ' else {\n' if static else '\npartInit.code() += " else {\\n";\n'
		code_str += '\n'.join(stmts[-1])
		code_str += '\n}' if static else '\npartInit.code() += "}\\n";'

	return code_str

def loop(self: behav.Loop, context: TransformerContext):
	"""Generate 'while' and 'do .. while' loops."""

	# generate the loop condition and body
	cond = self.cond.generate(context)
	stmts = [stmt.generate(context) for stmt in self.stmts]

	# generate loop begin
	code_str = f"while ({cond}) {{" if not self.post_test else "do {"
	if not cond.static:
		code_str = f'partInit.code() += "{code_str}\\n";'
		context.dependent_regs.update(cond.regs_affected)

	# generate loop body
	code_str += '\n'
	code_str += '\n'.join(stmts)
	code_str += '\n'

	end_code = "}" if not self.post_test else f"}} while({cond});"
	if not cond.static:
		end_code = f'partInit.code() += "{end_code}\\n";'

	code_str += end_code

	return code_str

def ternary(self: behav.Ternary, context: TransformerContext):
	"""Generate a ternary expression."""

	# generate condition and 'then' and 'else' statements
	cond = self.cond.generate(context)
	then_expr = self.then_expr.generate(context)
	else_expr = self.else_expr.generate(context)

	static = StaticType.NONE not in [x.static for x in (cond, then_expr, else_expr)]

	# convert singular static sub-components
	if not static:
		if cond.static and not cond.is_literal:
			cond.code = context.make_static(cond.code)
		if then_expr.static and not then_expr.is_literal:
			then_expr.code = context.make_static(then_expr.code)
		if else_expr.static and not else_expr.is_literal:
			else_expr.code = context.make_static(else_expr.code)

	c = CodeString(f'({cond}) ? ({then_expr}) : ({else_expr})', static, then_expr.size if then_expr.size > else_expr.size else else_expr.size, then_expr.signed or else_expr.signed, any((cond.is_mem_access, then_expr.is_mem_access, else_expr.is_mem_access)), set.union(cond.regs_affected, then_expr.regs_affected, else_expr.regs_affected))
	c.mem_ids = cond.mem_ids + then_expr.mem_ids + else_expr.mem_ids

	return c

def assignment(self: behav.Assignment, context: TransformerContext):
	"""Generate an assignment expression"""

	# generate target and value expressions
	target: CodeString = self.target.generate(context)
	expr: CodeString = self.expr.generate(context)

	# check staticness
	static = bool(target.static & StaticType.WRITE) and bool(expr.static)

	code_lines = []

	# TODO: should not be needed any more
	if target.scalar and not context.ignore_static:
		if expr.static:
			if target.scalar.static == StaticType.WRITE and context.static_scalars:
				code_lines.append(f'partInit.code() += "{target.code};\\n";')
			target.scalar.static |= StaticType.READ
		else:
			#if target.scalar.static == StaticType.RW:
			#	target.code = f'{data_type_map[target.scalar.data_type]}{target.scalar.actual_size} {target.code}'

			target.scalar.static = StaticType.NONE
			target.static = StaticType.NONE

	# error out if a static target should be assigned a non-static value
	if not expr.static and bool(target.static & StaticType.WRITE) and not context.ignore_static:
		raise M2ValueError('Static target cannot be assigned to non-static expression!')

	# convert assignment value staticness
	if expr.static and not expr.is_literal:
		if bool(target.static & StaticType.WRITE):
			if context.ignore_static:
				expr.code = Template(f'{expr.code}').safe_substitute(**replacements.rename_dynamic)
			else:
				expr.code = Template(f'{expr.code}').safe_substitute(**replacements.rename_static)

		else:
			expr.code = context.make_static(expr.code)

	# convert target staticness
	if bool(target.static & StaticType.READ):
		target.code = Template(target.code).safe_substitute(replacements.rename_write)

	# keep track of affected and dependent registers
	context.affected_regs.update(target.regs_affected)
	context.dependent_regs.update(expr.regs_affected)

	# mask of unneeded bits
	if not target.is_mem_access and not expr.is_mem_access:
		if target.actual_size > target.size:
			expr.code = f'({expr.code}) & {hex((1 << target.size) - 1)}'

		code_lines.append(context.wrap_codestring(f'{target.code} = {expr.code};', static))

	else:
		context.generates_exception = True

		# generate any memory (read) accesses in the assignment value expression
		for m_id in expr.mem_ids:
			# if no explicit memory access size was given, determine from the target size
			if not expr.mem_corrected:
				logger.debug("assuming mem read size at %d", target.size)
				m_id.access_size = target.size

			code_lines.append(context.wrap_codestring(f'etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};'))
			code_lines.append(context.wrap_codestring(f'cpu->exception |= (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});'))
			raise_fn_call = behav.FunctionCall(context.mem_raise_fn, [behav.CodeLiteral("cpu->exception")]).generate(context)
			code_lines.append(context.wrap_codestring(f'if (cpu->exception) {raise_fn_call.code};'))

		# generate target memory (write) access
		if target.is_mem_access:
			if len(target.mem_ids) != 1:
				raise M2SyntaxError('Only one memory access is allowed as assignment target!')

			if not target.mem_corrected:
				logger.debug("assuming mem write size at %d", expr.size)
				target.mem_ids[0].access_size = expr.size

			m_id = target.mem_ids[0]

			code_lines.append(context.wrap_codestring(f'etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id} = {expr.code};'))
			code_lines.append(context.wrap_codestring(f'cpu->exception |= (*(system->dwrite))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});'))
			raise_fn_call = behav.FunctionCall(context.mem_raise_fn, [behav.CodeLiteral("cpu->exception")]).generate(context)
			code_lines.append(context.wrap_codestring(f'if (cpu->exception) {raise_fn_call.code};'))
		else:
			code_lines.append(context.wrap_codestring(f'{target.code} = {expr.code};'))

	return '\n'.join(code_lines)

def binary_operation(self: behav.BinaryOperation, context: TransformerContext):
	"""Generate a binary expression"""

	# generate LHS and RHS of the expression
	left = self.left.generate(context)
	op = self.op
	right = self.right.generate(context)

	# convert staticness if needed
	if not left.static and right.static and not right.is_literal:
		right.code = context.make_static(right.code)
	if not right.static and left.static and not left.is_literal:
		left.code = context.make_static(left.code)

	c = CodeString(f'{left.code} {op.value} {right.code}', left.static and right.static, left.size if left.size > right.size else right.size, left.signed or right.signed, left.is_mem_access or right.is_mem_access, set.union(left.regs_affected, right.regs_affected))
	# keep track of any memory accesses
	c.mem_ids = left.mem_ids + right.mem_ids
	return c

def unary_operation(self: behav.UnaryOperation, context: TransformerContext):
	op = self.op
	right = self.right.generate(context)

	c = CodeString(f'{op.value}({right.code})', right.static, right.size, right.signed, right.is_mem_access, right.regs_affected)
	c.mem_ids = right.mem_ids
	return c

def slice_operation(self: behav.SliceOperation, context: TransformerContext):
	"""Generate a slice expression"""

	# generate expression to be sliced and lower and upper slice bound
	expr = self.expr.generate(context)
	left = self.left.generate(context)
	right = self.right.generate(context)

	static = StaticType.NONE not in [x.static for x in (expr, left, right)]

	if not static:
		if expr.static and not expr.is_literal:
			expr.code = context.make_static(expr.code)
		if left.static and not left.is_literal:
			left.code = context.make_static(left.code)
		if right.static and not right.is_literal:
			right.code = context.make_static(right.code)

	# slice with fixed integers if slice bounds are integers
	try:
		new_size = int(left.code.replace("U", "").replace("L", "")) - int(right.code.replace("U", "").replace("L", "")) + 1
		mask = (1 << (int(left.code.replace("U", "").replace("L", "")) - int(right.code.replace("U", "").replace("L", "")) + 1)) - 1

	# slice with actual lower and upper bound code if not possible to slice with integers
	except Exception:
		new_size = expr.size
		mask = f"((1 << (({left.code}) - ({right.code}) + 1)) - 1)"

	c = CodeString(f"((({expr.code}) >> ({right.code})) & {mask})", static, new_size, expr.signed, expr.is_mem_access or left.is_mem_access or right.is_mem_access, set.union(expr.regs_affected, left.regs_affected, right.regs_affected))
	c.mem_ids = expr.mem_ids + left.mem_ids + right.mem_ids
	return c

def concat_operation(self: behav.ConcatOperation, context: TransformerContext):
	"""Generate a concatenation expression"""

	# generate LHS and RHS operands
	left = self.left.generate(context)
	right = self.right.generate(context)

	if not left.static and right.static and not right.is_literal:
		right.code = context.make_static(right.code)
	if not right.static and left.static and not left.is_literal:
		left.code = context.make_static(left.code)

	new_size = left.size + right.size
	c = CodeString(f"((({left.code}) << {right.size}) | ({right.code}))", left.static and right.static, new_size, left.signed or right.signed, left.is_mem_access or right.is_mem_access, set.union(left.regs_affected, right.regs_affected))
	c.mem_ids = left.mem_ids + right.mem_ids
	return c

def named_reference(self: behav.NamedReference, context: TransformerContext):
	"""Generate a named reference"""

	# extract referred object
	referred_var = self.reference

	static = StaticType.NONE
	scalar = None

	name = referred_var.name

	# check if static name replacement is needed
	if name in replacements.rename_static:
		name = f'${{{name}}}'
		static = StaticType.READ

	# check which type of reference has to be generated
	if isinstance(referred_var, arch.Memory):
		# architecture memory object (register, memory interface)
		if not static:
			ref = "*" if len(referred_var.children) > 0 else ""
			name = f"{ref}{replacements.default_prefix}{name}"
		signed = False
		size = referred_var.size
		context.used_arch_data = True

	elif isinstance(referred_var, arch.BitFieldDescr):
		# instruction encoding operand
		signed = referred_var.data_type == arch.DataType.S
		size = referred_var.size
		static = StaticType.READ

	elif isinstance(referred_var, arch.Scalar):
		# scalar
		signed = referred_var.data_type == arch.DataType.S
		size = referred_var.size
		if context.static_scalars:
			static = referred_var.static
		scalar = referred_var

	elif isinstance(referred_var, arch.Constant):
		# architecture constant
		signed = referred_var.value < 0
		size = context.native_size
		static = StaticType.READ
		name = f'{referred_var.value}'

	elif isinstance(referred_var, arch.FnParam):
		# function argument
		signed = referred_var.data_type == arch.DataType.S
		size = referred_var.size
		static = StaticType.RW

	else:
		# should not happen
		signed = False

	if context.ignore_static:
		static = StaticType.RW

	c = CodeString(name, static, size, signed, False)
	#c.scalar = scalar
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

	# convert static index expression
	index_code = index.code
	if index.static and not context.ignore_static and not index.is_literal:
		index.code = context.make_static(index.code)

	if context.ignore_static:
		static = StaticType.RW
	else:
		static = StaticType.NONE

	if arch.MemoryAttribute.IS_MAIN_MEM in referred_mem.attributes:
		# generate memory access if main memory is accessed
		c = CodeString(f'{MEM_VAL_REPL}{context.mem_var_count}', static, size, False, True)
		c.mem_ids.append(MemID(referred_mem, context.mem_var_count, index, size))
		context.mem_var_count += 1
		return c
	else:
		# generate normal indexed access if not
		code_str = f'{replacements.prefixes.get(name, replacements.default_prefix)}{name}[{index.code}]'
		if len(referred_mem.children) > 0:
			code_str = '*' + code_str
		if size != referred_mem.size:
			code_str = f'(etiss_uint{size})' + code_str
		c = CodeString(code_str, static, size, False, False)
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
			code_str = f'((etiss_int{target_size})(({expr.code}) << ({target_size - expr.size})) >> ({target_size - expr.size}))'
		else:
			code_str = f'((etiss_int{target_size})(({expr.code}) << ({target_size} - {expr.size})) >> ({target_size} - {expr.size}))'

	# normal type conversion
	# TODO: check if behavior adheres to CoreDSL 2 spec
	else:
		code_str = f'({data_type_map[self.data_type]}{self.actual_size})({code_str})'

	c = CodeString(code_str, expr.static, self.size, self.data_type == arch.DataType.S, expr.is_mem_access, expr.regs_affected)
	c.mem_ids = expr.mem_ids
	c.mem_corrected = expr.mem_corrected

	return c

def int_literal(self: behav.IntLiteral, context: TransformerContext):
	"""Generate an integer literal."""

	lit = int(self.value)
	size = min(self.bit_size, 64)
	sign = self.signed

	twocomp_lit = (lit + (1 << size)) % (1 << size)

	# add c postfix for large numbers
	postfix = "U" if not sign else ""
	if size > 32:
		postfix += "L"
	if size > 64:
		postfix += "L"

	ret = CodeString(str(lit) + postfix, True, size, sign, False)
	ret.is_literal = True
	return ret

def number_literal(self: behav.NumberLiteral, context: TransformerContext):
	"""Generate generic number literal. Currently unused."""

	lit = int(self.value)
	size = min(lit.bit_length(), 64)
	sign = lit < 0

	twocomp_lit = (lit + (1 << 64)) % (1 << 64)

	postfix = "U" if not sign else ""
	if size > 32:
		postfix += "L"
	if size > 64:
		postfix += "L"

	return CodeString(str(twocomp_lit) + postfix, True, size, sign, False)

def group(self: behav.Group, context: TransformerContext):
	"""Generate a group of expressions."""

	expr = self.expr.generate(context)
	if isinstance(expr, CodeString):
		expr.code = f'({expr.code})'
	else:
		expr = f'({expr})'
	return expr

def operator(self: behav.Operator, context: TransformerContext):
	return self.op

def code_literal(self: behav.CodeLiteral, context: TransformerContext):
	return CodeString(self.val, False, context.native_size, False, False)