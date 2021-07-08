import logging
from typing import Mapping, Set

from lark import Transformer

from ...backends import StaticType
from ...metamodel import arch, behav

logger = logging.getLogger("behavior")

class BehaviorModelBuilder(Transformer):
	def __init__(self, constants: Mapping[str, arch.Constant], memories: Mapping[str, arch.Memory], memory_aliases: Mapping[str, arch.Memory],
		fields: Mapping[str, arch.BitFieldDescr], functions: Mapping[str, arch.Function], warned_fns: Set[str]):

		self._constants = constants
		self._memories = memories
		self._memory_aliases = memory_aliases
		self._fields = fields
		self._scalars = {}
		self._functions = functions
		self.warned_fns = warned_fns if warned_fns is not None else set()

	def get_constant_or_val(self, name_or_val):
		if type(name_or_val) == int:
			return name_or_val
		else:
			return self._constants[name_or_val]

	def FUNCTIONNAME(self, args):
		return args.value

	PROCEDURENAME = FUNCTIONNAME

	def ADD_OP(self, args):
		op = behav.Operator(args.value)
		logger.debug(f'operator {str(op)}')
		return op

	BOOL_OR_OP = ADD_OP
	BOOL_AND_OP = ADD_OP

	BIT_OR_OP = ADD_OP
	BIT_XOR_OP = ADD_OP
	BIT_AND_OP = ADD_OP

	EQ_OP = ADD_OP
	COMP_OP = ADD_OP
	SHIFT_OP = ADD_OP
	MULT_OP = ADD_OP
	UNITARY_OP = ADD_OP

	def stmt_list(self, args):
		return args

	def operation(self, args):
		op = behav.Operation(args)
		logger.debug(f'operation {str(op)}')
		return op

	def scalar_definition(self, args):
		name, data_type, size = args

		if name in self._scalars:
			raise ValueError(f"Scalar {name} already defined!")

		size_val = self.get_constant_or_val(size)

		if not data_type:
			data_type = arch.DataType.U

		s = arch.Scalar(name, None, StaticType.WRITE, size_val, data_type)

		self._scalars[name] = s

		sd = behav.ScalarDefinition(s)
		logger.debug(f'scalar_definition {str(sd)}')
		return sd

	def return_(self, args):
		return behav.Return(args[0])

	def assignment(self, args):
		target, expr = args

		return behav.Assignment(target, expr)

	def indexed_reference(self, args):
		name, index_expr, size = args
		referred_mem = self._memory_aliases.get(name) or self._memories.get(name)

		if referred_mem is None:
			raise ValueError(f"Indexed reference {name} does not exist!")

		ref = behav.IndexedReference(referred_mem, index_expr)
		if size is None:
			return ref
		else:
			return behav.TypeConv(None, size, ref)

	def named_reference(self, args):
		name, size = args
		var = self._scalars.get(name) or \
			self._fields.get(name) or \
			self._constants.get(name) or \
			self._memory_aliases.get(name) or \
			self._memories.get(name)

		if var is None:
			raise ValueError(f"Named reference {name} does not exist!")

		ref = behav.NamedReference(var)
		if size is None:
			return ref
		else:
			return behav.TypeConv(None, size, ref)

	def two_op_expr(self, args):
		left, op, right = args

		return behav.BinaryOperation(left, op, right)

	def unitary_expr(self, args):
		op, right = args

		return behav.UnaryOperation(op, right)

	def number_literal(self, args):
		lit, = args
		return behav.NumberLiteral(int(lit))

	def type_conv(self, args):
		expr, data_type = args

		return behav.TypeConv(data_type, None, expr)

	def conditional(self, args):
		cond, then_stmts, else_stmts = args

		return behav.Conditional(cond, then_stmts, else_stmts)

	def _callable(self, args, type: behav.Callable):
		name, fn_args = args

		if name not in self._functions:
			if name not in self.warned_fns and not name.startswith("fdispatch") and not name.startswith("dispatch"):
				logger.warning(f"Function {name} not defined in instruction set, generator must add it later!")
				self.warned_fns.add(name)
		else:
			name = self._functions[name]

		return type(name, fn_args)

	def procedure(self, args):
		return self._callable(args, behav.ProcedureCall)

	def function(self, args):
		return self._callable(args, behav.FunctionCall)

	def fn_args(self, args):
		return args

	def parens(self, args):
		expr, = args
		return behav.Group(expr)
