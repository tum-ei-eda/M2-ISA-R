from ...metamodel import arch, behav

def operation(self: behav.Operation, context):
	statements = []
	for stmt in self.statements:
		try:
			temp = stmt.generate(context)
			if isinstance(temp, list):
				statements.extend(temp)
			else:
				statements.append(temp)
		except (NotImplementedError, ValueError) as e:
			print(f"cant simplify {stmt}")

	self.statements = statements
	return self

def binary_operation(self: behav.BinaryOperation, context):
	self.left = self.left.generate(context)
	self.right = self.right.generate(context)

	if isinstance(self.left, behav.IntLiteral) and isinstance(self.right, (behav.NamedReference, behav.IndexedReference)):
		if self.left.bit_size < self.right.reference.size:
			self.left.bit_size = self.right.reference.size

	if isinstance(self.right, behav.IntLiteral) and isinstance(self.left, (behav.NamedReference, behav.IndexedReference)):
		if self.right.bit_size < self.left.reference.size:
			self.right.bit_size = self.left.reference.size

	if isinstance(self.left, behav.IntLiteral) and isinstance(self.right, behav.IntLiteral):
		res: int = eval(f"{self.left.value}{self.op.value}{self.right.value}")
		return behav.IntLiteral(res, max(self.left.bit_size, self.right.bit_size, res.bit_length()))

	return self

def slice_operation(self: behav.SliceOperation, context):
	self.expr = self.expr.generate(context)
	self.left = self.left.generate(context)
	self.right = self.right.generate(context)

	return self

def concat_operation(self: behav.ConcatOperation, context):
	self.left = self.left.generate(context)
	self.right = self.right.generate(context)

	return self

def number_literal(self: behav.IntLiteral, context):
	return self

def int_literal(self: behav.IntLiteral, context):
	return self

def scalar_definition(self: behav.ScalarDefinition, context):
	return self

def assignment(self: behav.Assignment, context):
	self.expr = self.expr.generate(context)

	if isinstance(self.expr, behav.IntLiteral) and isinstance(self.target, (behav.NamedReference, behav.IndexedReference)):
		if self.expr.bit_size < self.target.reference.size:
			self.expr.bit_size = self.target.reference.size

	#if isinstance(self.expr, behav.IntLiteral) and isinstance(self.target, behav.ScalarDefinition):
#		self.target.scalar.value = self.expr.value

	return self

def conditional(self: behav.Conditional, context):
	self.cond = self.cond.generate(context)

	for stmt in self.then_stmts:
		stmt = stmt.generate(context)
	for stmt in self.else_stmts:
		stmt = stmt.generate(context)

	if isinstance(self.cond, behav.IntLiteral):
		if self.cond.value:
			return self.then_stmts
		else:
			return self.else_stmts

	return self

def loop(self: behav.Loop, context):
	return self

def ternary(self: behav.Ternary, context):
	self.cond = self.cond.generate(context)
	self.then_expr = self.then_expr.generate(context)
	self.else_expr = self.else_expr.generate(context)

	if isinstance(self.cond, behav.IntLiteral):
		if self.cond.value:
			return self.then_expr
		else:
			return self.else_expr

	return self

def return_(self: behav.Return, context):
	self.expr = self.expr.generate(context)

	return self

def unary_operation(self: behav.UnaryOperation, context):
	self.right = self.right.generate(context)
	if isinstance(self.right, behav.IntLiteral):
		res: int = eval(f"{self.op.value}{self.right.value}")
		return behav.IntLiteral(res, max(self.right.bit_size, res.bit_length()))

	return self

def named_reference(self: behav.NamedReference, context):
	if isinstance(self.reference, arch.Constant):
		return behav.IntLiteral(self.reference.value, self.reference.size, self.reference.signed)

	#if isinstance(self.reference, arch.Scalar) and self.reference.value is not None:
#		return behav.IntLiteral(self.reference.value, self.reference.size, self.reference.data_type == arch.DataType.S)

	return self

def indexed_reference(self: behav.IndexedReference, context):
	self.index = self.index.generate(context)

	return self

def type_conv(self: behav.TypeConv, context):
	self.expr = self.expr.generate(context)
	if isinstance(self.expr, behav.IntLiteral):
		self.expr.bit_size = self.size
		self.expr.signed = self.data_type == arch.DataType.S
		return self.expr

	return self

def callable(self: behav.Callable, context):
	for stmt in self.args:
		stmt = stmt.generate(context)

	return self

def group(self: behav.Group, context):
	self.expr = self.expr.generate(context)

	if isinstance(self.expr, behav.IntLiteral):
		return self.expr

	return self