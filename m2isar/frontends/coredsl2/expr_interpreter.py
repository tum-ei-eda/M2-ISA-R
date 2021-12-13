from ...metamodel import arch, behav

def group(self: behav.Group, context):
	return self.expr.generate(context)

def int_literal(self: behav.IntLiteral, context):
	return self.value

def named_reference(self: behav.NamedReference, context):
	if isinstance(self.reference, arch.Constant) and self.reference.value is not None:
		return self.reference.value
	raise ValueError("non-interpretable value encountered")

def binary_operation(self: behav.BinaryOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)
	return eval(f"{left}{self.op.value}{right}")

def unary_operation(self: behav.UnaryOperation, context):
	right = self.right.generate(context)
	return eval(f"{self.op.value}{right}")
