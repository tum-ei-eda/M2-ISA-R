from ...metamodel import arch, behav

def int_literal(self: behav.IntLiteral, context):
	return self.value

def named_reference(self: behav.NamedReference, context):
	if isinstance(self.reference, arch.Constant) and self.reference.value:
		return self.reference.value
	raise ValueError("non-interpretable value encountered")

def binary_operation(self: behav.BinaryOperation, context):
	left = self.left.generate(context)
	right = self.right.generate(context)
	return eval(f"{left}{self.op}{right}")

def unary_operation(self: behav.UnaryOperation, context):
	right = self.right.generate(context)
	return eval(f"{self.op}{right}")