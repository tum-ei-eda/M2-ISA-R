from itertools import chain
from string import Template

from ...metamodel import arch, behav
from . import replacements
from .instruction_utils import (MEM_VAL_REPL, CodeString, MemID, StaticType,
                                TransformerContext, data_type_map)

USE_STATIC_SCALARS = False

def operation(self: behav.Operation, context: TransformerContext):
	args = [stmt.generate(context) for stmt in self.statements]

	code_str = '\n'.join(args)

	if context.is_exception:
		code_str += '\npartInit.code() += "return exception;\\n";'
	elif context.generates_exception:
		code_str = f'partInit.code() += "exception = 0;\\n"\n{code_str}\npartInit.code() += "if (exception) return exception;\\n";'
	elif arch.InstrAttribute.NO_CONT in context.attribs:
		code_str += '\npartInit.code() += "return 0;\\n";'

	return code_str

def return_(self: behav.Return, context: TransformerContext):
	return f'return {self.expr.generate(context).code};'

def scalar_definition(self: behav.ScalarDefinition, context: TransformerContext):
	context.scalars[self.scalar.name] = self.scalar
	actual_size = 1 << (self.scalar.size - 1).bit_length()
	if actual_size < 8:
		actual_size = 8
	c = CodeString(f'{data_type_map[self.scalar.data_type]}{actual_size} {self.scalar.name}', StaticType.WRITE if USE_STATIC_SCALARS else StaticType.NONE, self.scalar.size, self.scalar.data_type == arch.DataType.S, False)
	c.scalar = self.scalar
	return c

def procedure_call(self: behav.ProcedureCall, context: TransformerContext):
	fn_args = [arg.generate(context) for arg in self.args]

	if isinstance(self.ref_or_name, arch.Function):
		fn = self.ref_or_name
		static = fn.static

		if not static:
			context.used_arch_data = True
			for arg in fn_args:
				if arg.static:
					arg.code = context.make_static(arg.code)

		arch_args = ['cpu', 'system', 'plugin_pointers'] if not fn.static else []
		arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

		mem_access = True in [arg.is_mem_access for arg in fn_args]
		mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
		context.dependent_regs.update(regs_affected)

		code_str = ''
		if mem_access:
			context.generates_exception = True
			for m_id in mem_ids:
				code_str += f'partInit.code() += "etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};\\n";\n'
				code_str += f'partInit.code() += "exception = (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});\\n";\n'

		code_str += f'partInit.code() += "{fn.name}({arg_str});"'

		return code_str

	elif self.ref_or_name == 'wait':
		context.generates_exception = True
		return 'partInit.code() += "exception = ETISS_RETURNCODE_CPUFINISHED;\\n";'

	elif self.ref_or_name == 'raise':
		sender, code = fn_args
		exc_id = (int(sender.code), int(code.code))
		if exc_id not in replacements.exception_mapping:
			raise ValueError(f'Exception {exc_id} not defined!')

		#context.generates_exception = True
		return f'partInit.code() += "return {replacements.exception_mapping[exc_id]};\\n";'

	elif self.ref_or_name.startswith('dispatch_'):
		if fn_args is None: fn_args = []

		context.used_arch_data = True

		name = self.ref_or_name[len("dispatch_"):]
		arg_str = ', '.join([context.make_static(arg.code) if arg.static else arg.code for arg in fn_args])

		mem_access = True in [arg.is_mem_access for arg in fn_args]
		mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
		context.dependent_regs.update(regs_affected)

		code_str = ''
		if mem_access:
			context.generates_exception = True
			for m_id in mem_ids:
				code_str += f'partInit.code() += "etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};\\n";\n'
				code_str += f'partInit.code() += "exception = (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});\\n";\n'

		code_str += f'partInit.code() += "{name}({arg_str});"'
		return code_str

	else:
		raise ValueError(f'Function {self.ref_or_name} not recognized!')


def function_call(self: behav.FunctionCall, context: TransformerContext):
	fn_args = [arg.generate(context) for arg in self.args]

	if isinstance(self.ref_or_name, arch.Function):
		fn = self.ref_or_name
		static = fn.static

		if not static:
			context.used_arch_data = True
			for arg in fn_args:
				if arg.static:
					arg.code = context.make_static(arg.code)

		arch_args = ['cpu', 'system', 'plugin_pointers'] if not fn.static else []
		arg_str = ', '.join(arch_args + [arg.code for arg in fn_args])

		mem_access = True in [arg.is_mem_access for arg in fn_args]
		signed = True in [arg.signed for arg in fn_args]
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))

		static = StaticType.READ if static and all(arg.static != StaticType.NONE for arg in fn_args) else StaticType.NONE

		c = CodeString(f'{fn.name}({arg_str})', static, fn.size, signed, mem_access, regs_affected)
		c.mem_ids = list(chain.from_iterable([arg.mem_ids for arg in fn_args]))

		return c

	elif self.ref_or_name == 'wait':
		context.generates_exception = True
		return 'partInit.code() += "exception = ETISS_RETURNCODE_CPUFINISHED;\\n";'

	elif self.ref_or_name == 'raise':
		sender, code = fn_args
		exc_id = (int(sender.code), int(code.code))
		if exc_id not in replacements.exception_mapping:
			raise ValueError(f'Exception {exc_id} not defined!')

		context.generates_exception = True
		return f'partInit.code() += "exception = {replacements.exception_mapping[exc_id]};\\n";'

	elif self.ref_or_name == 'choose':
		cond, then_stmts, else_stmts = fn_args
		static = StaticType.NONE not in [x.static for x in fn_args]
		if not static:
			if cond.static:
				cond.code = context.make_static(cond.code)
			if then_stmts.static:
				then_stmts.code = context.make_static(then_stmts.code)
			if else_stmts.static:
				else_stmts.code = context.make_static(else_stmts.code)

		c = CodeString(f'({cond}) ? ({then_stmts}) : ({else_stmts})', static, then_stmts.size if then_stmts.size > else_stmts.size else else_stmts.size, then_stmts.signed or else_stmts.signed, False, set.union(cond.regs_affected, then_stmts.regs_affected, else_stmts.regs_affected))
		c.mem_ids = cond.mem_ids + then_stmts.mem_ids + else_stmts.mem_ids

		return c

	elif self.ref_or_name == 'sext':
		expr = fn_args[0]

		target_size = context.native_size
		source_size = expr.size

		if len(fn_args) >= 2:
			target_size = int(fn_args[1].code)
		if len(fn_args) >= 3:
			try:
				source_size = int(fn_args[2].code)
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

	elif self.ref_or_name == 'zext':
		expr = fn_args[0]
		if len(fn_args) == 1:
			target_size = expr.size
		else:
			target_size = int(fn_args[1].code)

		c = CodeString(f'(etiss_uint{target_size})({expr.code})', expr.static, target_size, expr.signed, expr.is_mem_access, expr.regs_affected)
		c.mem_ids = expr.mem_ids

		return c

	elif self.ref_or_name == 'shll':
		expr, amount = fn_args
		if expr.static:
			expr.code = context.make_static(expr.code)
		if amount.static:
			amount.code = context.make_static(amount.code)
		return CodeString(f'({expr.code}) << ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

	elif self.ref_or_name == 'shrl':
		expr, amount = fn_args
		if expr.static:
			expr.code = context.make_static(expr.code)
		if amount.static:
			amount.code = context.make_static(amount.code)
		return CodeString(f'({expr.code}) >> ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

	elif self.ref_or_name == 'shra':
		expr, amount = fn_args
		if expr.static:
			expr.code = context.make_static(expr.code)
		if amount.static:
			amount.code = context.make_static(amount.code)
		return CodeString(f'(etiss_int{expr.actual_size})({expr.code}) >> ({amount.code})', expr.static and amount.static, expr.size, expr.signed, expr.is_mem_access, set.union(expr.regs_affected, amount.regs_affected))

	elif self.ref_or_name.startswith('fdispatch_'):
		if fn_args is None: fn_args = []
		mem_access = True in [arg.is_mem_access for arg in fn_args]
		regs_affected = set(chain.from_iterable([arg.regs_affected for arg in fn_args]))
		name = self.ref_or_name[len("fdispatch_"):]
		arg_str = ', '.join([context.make_static(arg.code) if arg.static else arg.code for arg in fn_args])

		c = CodeString(f'{name}({arg_str})', StaticType.NONE, 64, False, mem_access, regs_affected)
		return c

	else:
		raise ValueError(f'Function {self.ref_or_name} not recognized!')

def conditional(self: behav.Conditional, context: TransformerContext):
	cond = self.cond.generate(context)
	then_stmts = [stmt.generate(context) for stmt in self.then_stmts]
	else_stmts = [stmt.generate(context) for stmt in self.else_stmts]

	code_str = f'if ({cond}) {{'
	if not cond.static:
		code_str = f'partInit.code() += "{code_str}\\n";'
		context.dependent_regs.update(cond.regs_affected)

	code_str += '\n'
	code_str += '\n'.join(then_stmts)
	code_str += '\n}' if cond.static else '\npartInit.code() += "}\\n";'

	if else_stmts:
		code_str += ' else {\n' if cond.static else '\npartInit.code() += " else {\\n";\n'
		code_str += '\n'.join(else_stmts)
		code_str += '\n}' if cond.static else '\npartInit.code() += "}\\n";'

	return code_str

def assignment(self: behav.Assignment, context: TransformerContext):
	target = self.target.generate(context)
	expr = self.expr.generate(context)

	static = bool(target.static & StaticType.WRITE) and bool(expr.static)

	code_str = ''

	if target.scalar and not context.ignore_static:
		if expr.static:
			if target.scalar.static == StaticType.WRITE and USE_STATIC_SCALARS:
				code_str += f'partInit.code() += "{target.code};\\n";\n'
			target.scalar.static |= StaticType.READ
		else:
			#if target.scalar.static == StaticType.RW:
			#	target.code = f'{data_type_map[target.scalar.data_type]}{target.scalar.actual_size} {target.code}'

			target.scalar.static = StaticType.NONE
			target.static = StaticType.NONE

	if not expr.static and bool(target.static & StaticType.WRITE) and not context.ignore_static:
		raise ValueError('Static target cannot be assigned to non-static expression!')

	if expr.static:
		if bool(target.static & StaticType.WRITE):
			expr.code = Template(f'{expr.code}').safe_substitute(**replacements.rename_static)

		else:
			expr.code = context.make_static(expr.code)

	if bool(target.static & StaticType.READ):
		target.code = Template(target.code).safe_substitute(replacements.rename_dynamic)

	context.affected_regs.update(target.regs_affected)
	context.dependent_regs.update(expr.regs_affected)

	if not target.is_mem_access and not expr.is_mem_access:
		if target.actual_size > target.size:
			expr.code = f'({expr.code}) & {hex((1 << target.size) - 1)}'

		code_str += f'{target.code} = {expr.code};'
		if not static and not context.ignore_static:
			code_str = f'partInit.code() += "{code_str}\\n";'

	else:
		context.generates_exception = True
		for m_id in expr.mem_ids:
			code_str += f'partInit.code() += "etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id};\\n";\n'
			code_str += f'partInit.code() += "exception |= (*(system->dread))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});\\n";\n'

		if target.is_mem_access:
			if len(target.mem_ids) != 1:
				raise ValueError('Only one memory access is allowed as assignment target!')

			m_id = target.mem_ids[0]

			code_str += f'partInit.code() += "etiss_uint{m_id.access_size} {MEM_VAL_REPL}{m_id.mem_id} = {expr.code};\\n";\n'
			code_str += f'partInit.code() += "exception |= (*(system->dwrite))(system->handle, cpu, {m_id.index.code}, (etiss_uint8*)&{MEM_VAL_REPL}{m_id.mem_id}, {int(m_id.access_size / 8)});\\n";\n'
		else:
			code_str += f'partInit.code() += "{target.code} = {expr.code};\\n";'

	return code_str

def binary_operation(self: behav.BinaryOperation, context: TransformerContext):
	left = self.left.generate(context)
	op = self.op
	right = self.right.generate(context)

	if not left.static and right.static:
		right.code = context.make_static(right.code)
	if not right.static and left.static:
		left.code = context.make_static(left.code)

	c = CodeString(f'{left.code} {op.value} {right.code}', left.static and right.static, left.size if left.size > right.size else right.size, left.signed or right.signed, left.is_mem_access or right.is_mem_access, set.union(left.regs_affected, right.regs_affected))
	c.mem_ids = left.mem_ids + right.mem_ids
	return c

def unary_operation(self: behav.UnaryOperation, context: TransformerContext):
	op = self.op
	right = self.right.generate(context)

	c = CodeString(f'{op.value}({right.code})', right.static, right.size, right.signed, right.is_mem_access, right.regs_affected)
	c.mem_ids = right.mem_ids
	return c

def named_reference(self: behav.NamedReference, context: TransformerContext):
	referred_var = self.reference

	static = StaticType.NONE
	scalar = None

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
		if USE_STATIC_SCALARS:
			static = referred_var.static
		scalar = referred_var
	elif isinstance(referred_var, arch.Constant):
		signed = referred_var.value < 0
		size = context.native_size
		static = StaticType.READ
		name = f'{referred_var.value}'
	elif isinstance(referred_var, arch.FnParam):
		signed = referred_var.data_type == arch.DataType.S
		size = referred_var.size
		static = StaticType.RW
	else:
		signed = False

	if context.ignore_static:
		static = StaticType.RW

	c = CodeString(name, static, size, signed, False)
	c.scalar = scalar
	return c

def indexed_reference(self: behav.IndexedReference, context: TransformerContext):
	name = self.reference.name
	index = self.index.generate(context)

	referred_mem = self.reference

	size = referred_mem.size

	index_code = index.code
	if index.static and not context.ignore_static:
		index.code = context.make_static(index.code)

	if context.ignore_static:
		static = StaticType.RW
	else:
		static = StaticType.NONE

	if arch.SpaceAttribute.IS_MAIN_MEM in referred_mem.attributes:
		c = CodeString(f'{MEM_VAL_REPL}{context.mem_var_count}', static, size, False, True)
		c.mem_ids.append(MemID(referred_mem, context.mem_var_count, index, size))
		context.mem_var_count += 1
		return c
	else:
		code_str = f'{replacements.prefixes.get(name, replacements.default_prefix)}{name}[{index.code}]'
		if size != referred_mem.size:
			code_str = f'(etiss_uint{size})' + code_str
		c = CodeString(code_str, static, size, False, False)
		if arch.RegAttribute.IS_MAIN_REG in referred_mem.attributes:
			c.regs_affected.add(index_code)
		return c

def type_conv(self: behav.TypeConv, context: TransformerContext):
	expr = self.expr.generate(context)

	if self.data_type is None:
		self.data_type = arch.DataType.S if expr.signed else arch.DataType.U

	if self.size is None:
		self.size = expr.actual_size

	if expr.is_mem_access:
		if not expr.mem_corrected and expr.mem_ids[-1].access_size != self.size:
			expr.mem_ids[-1].access_size = self.size
			expr.size = self.size
			expr.mem_corrected = True
			return expr
		elif expr.mem_ids[-1].access_size == self.size:
			expr.mem_corrected = True

		return expr

	c = CodeString(f'({data_type_map[self.data_type]}{self.size})({expr.code})', expr.static, self.size, self.data_type == arch.DataType.S, expr.is_mem_access, expr.regs_affected)
	c.mem_ids = expr.mem_ids
	return c

def number_literal(self: behav.NumberLiteral, context: TransformerContext):
	lit = self.value
	size = int(lit).bit_length()
	return CodeString(str(lit), True, size, int(lit) < 0, False)

def group(self: behav.Group, context: TransformerContext):
	expr = self.expr.generate(context)
	if isinstance(expr, CodeString):
		expr.code = f'({expr.code})'
	else:
		expr = f'({expr})'
	return expr

def operator(self: behav.Operator, context: TransformerContext):
	return self.op
