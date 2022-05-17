import logging

from ...backends import StaticType
from ...metamodel import arch, behav
from .parser_gen import CoreDSL2Parser, CoreDSL2Visitor
from .utils import RADIX, SHORTHANDS, SIGNEDNESS, flatten_list

logger = logging.getLogger("behav_builder")

class BehaviorModelBuilder(CoreDSL2Visitor):

	def __init__(self, constants: "dict[str, arch.Constant]", memories: "dict[str, arch.Memory]", memory_aliases: "dict[str, arch.Memory]",
		fields: "dict[str, arch.BitFieldDescr]", functions: "dict[str, arch.Function]", warned_fns: "set[str]"):

		super().__init__()

		self._constants = constants
		self._memories = memories
		self._memory_aliases = memory_aliases
		self._fields = fields
		self._scalars = {}
		self._functions = functions
		self.warned_fns = warned_fns if warned_fns is not None else set()

	def visitChildren(self, node):
		ret = super().visitChildren(node)
		if isinstance(ret, list) and len(ret) == 1:
			return ret[0]
		return ret

	def aggregateResult(self, aggregate, nextResult):
		ret = aggregate
		if nextResult is not None:
			if ret is None:
				ret = [nextResult]
			else:
				ret += [nextResult]
		return ret

	def visitProcedure_call(self, ctx: CoreDSL2Parser.Procedure_callContext):
		name = ctx.ref.text
		ref = self._functions.get(name, None)

		args = [self.visit(obj) for obj in ctx.args] if ctx.args else []

		if ref is None:
			raise ValueError(f"function {name} is not defined")

		return behav.ProcedureCall(ref, args)

	def visitMethod_call(self, ctx: "CoreDSL2Parser.Method_callContext"):
		name = ctx.ref.text
		ref = self._functions.get(name, None)

		args = [self.visit(obj) for obj in ctx.args] if ctx.args else []

		if ref is None:
			raise ValueError(f"function {name} is not defined")

		return behav.FunctionCall(ref, args)

	def visitBlock(self, ctx: CoreDSL2Parser.BlockContext):
		items = [self.visit(obj) for obj in ctx.items]
		items = flatten_list(items)
		return items

	def visitDeclaration(self, ctx: CoreDSL2Parser.DeclarationContext):
		storage = [self.visit(obj) for obj in ctx.storage]
		qualifiers = [self.visit(obj) for obj in ctx.qualifiers]
		attributes = [self.visit(obj) for obj in ctx.attributes]

		type_ = self.visit(ctx.type_)

		decls: "list[CoreDSL2Parser.DeclaratorContext]" = ctx.declarations

		ret_decls = []

		for decl in decls:
			name = decl.name.text

			s = arch.Scalar(name, None, StaticType.NONE, type_.width, arch.DataType.S if type_.signed else arch.DataType.U)
			self._scalars[name] = s
			sd = behav.ScalarDefinition(s)

			if decl.init: # create scalar definition and assignment
				init = self.visit(decl.init)

				a = behav.Assignment(sd, init)
				ret_decls.append(a)
			else: # create only scalar definition
				ret_decls.append(sd)

		return ret_decls

	def visitReturn_statement(self, ctx: CoreDSL2Parser.Return_statementContext):
		expr = self.visit(ctx.expr) if ctx.expr else None
		return behav.Return(expr)

	def visitWhile_statement(self, ctx: CoreDSL2Parser.While_statementContext):
		stmt = self.visit(ctx.stmt) if ctx.stmt else None
		cond = self.visit(ctx.cond)

		if not isinstance(stmt, list):
			stmt = [stmt]

		return behav.Loop(cond, stmt, False)

	def visitDo_statement(self, ctx: CoreDSL2Parser.Do_statementContext):
		stmt = self.visit(ctx.stmt) if ctx.stmt else None
		cond = self.visit(ctx.cond)

		if not isinstance(stmt, list):
			stmt = [stmt]

		return behav.Loop(cond, stmt, True)

	def visitFor_statement(self, ctx: CoreDSL2Parser.For_statementContext):
		start_decl, start_expr, end_expr, loop_exprs = self.visit(ctx.cond)
		stmt = self.visit(ctx.stmt) if ctx.stmt else None

		if not isinstance(stmt, list):
			stmt = [stmt]

		ret = []

		if start_decl is not None:
			ret.append(start_decl)
		if start_expr is not None:
			ret.append(start_expr)

		if loop_exprs:
			stmt.extend(loop_exprs)

		ret.append(behav.Loop(end_expr, stmt, False))

		return ret

	def visitFor_condition(self, ctx: CoreDSL2Parser.For_conditionContext):
		start_decl = self.visit(ctx.start_decl) if ctx.start_decl else None
		start_expr = self.visit(ctx.start_expr) if ctx.start_expr else None
		end_expr = self.visit(ctx.end_expr) if ctx.end_expr else None
		loop_exprs = [self.visit(obj) for obj in ctx.loop_exprs] if ctx.loop_exprs else None

		return start_decl, start_expr, end_expr, loop_exprs

	def visitIf_statement(self, ctx: CoreDSL2Parser.If_statementContext):
		conds = [self.visit(x) for x in ctx.cond]
		stmts = [self.visit(x) for x in ctx.stmt]

		stmts = [[x] if not isinstance(x, list) else x for x in stmts]

		return behav.Conditional(conds, stmts)

	def visitConditional_expression(self, ctx: CoreDSL2Parser.Conditional_expressionContext):
		cond = self.visit(ctx.cond)
		then_expr = self.visit(ctx.then_expr)
		else_expr = self.visit(ctx.else_expr)

		return behav.Ternary(cond, then_expr, else_expr)

	def visitBinary_expression(self, ctx: CoreDSL2Parser.Binary_expressionContext):
		left = self.visit(ctx.left)
		op =  behav.Operator(ctx.bop.text)
		right = self.visit(ctx.right)

		return behav.BinaryOperation(left, op, right)

	def visitPreinc_expression(self, ctx: CoreDSL2Parser.Preinc_expressionContext):
		raise NotImplementedError("pre-increment expressions are not supported yet")

	def visitPostinc_expression(self, ctx: CoreDSL2Parser.Preinc_expressionContext):
		raise NotImplementedError("post-increment expressions are not supported yet")

	def visitPrefix_expression(self, ctx: CoreDSL2Parser.Prefix_expressionContext):
		op = behav.Operator(ctx.prefix.text)
		right = self.visit(ctx.right)

		return behav.UnaryOperation(op, right)

	def visitParens_expression(self, ctx: CoreDSL2Parser.Parens_expressionContext):
		expr = self.visit(ctx.expr)
		return behav.Group(expr)

	def visitSlice_expression(self, ctx: CoreDSL2Parser.Slice_expressionContext):
		expr = self.visit(ctx.expr)

		left = self.visit(ctx.left)
		right = self.visit(ctx.right) if ctx.right else left

		if isinstance(expr, behav.NamedReference) and isinstance(expr.reference, arch.Memory) and expr.reference.data_range.length > 1:
			return behav.IndexedReference(expr.reference, left, right)
		else:
			return behav.SliceOperation(expr, left, right)

	def visitConcat_expression(self, ctx: CoreDSL2Parser.Concat_expressionContext):
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)

		return behav.ConcatOperation(left, right)

	def visitAssignment_expression(self, ctx: CoreDSL2Parser.Assignment_expressionContext):
		op = ctx.bop.text
		left = self.visit(ctx.left)
		right = self.visit(ctx.right)

		if op != "=":
			op2 = behav.Operator(op[:-1])
			right = behav.BinaryOperation(left, op2, right)

		return behav.Assignment(left, right)

	def visitReference_expression(self, ctx: CoreDSL2Parser.Reference_expressionContext):
		name = ctx.ref.text

		var = self._scalars.get(name) or \
			self._fields.get(name) or \
			self._constants.get(name) or \
			self._memory_aliases.get(name) or \
			self._memories.get(name)

		if var is None:
			raise ValueError(f"Named reference {name} does not exist!")

		return behav.NamedReference(var)

	def visitInteger_constant(self, ctx: CoreDSL2Parser.Integer_constantContext):
		text: str = ctx.value.text.lower()

		tick_pos = text.find("'")

		if tick_pos != -1:
			width = int(text[:tick_pos])
			radix = text[tick_pos+1]
			value = int(text[tick_pos+2:], RADIX[radix])

		else:
			value = int(text, 0)
			width = value.bit_length()

		return behav.IntLiteral(value, width)

	def visitCast_expression(self, ctx: CoreDSL2Parser.Cast_expressionContext):
		expr = self.visit(ctx.right)
		if ctx.type_:
			type_ = self.visit(ctx.type_)
			sign = arch.DataType.S if type_.signed else arch.DataType.U
			size = type_.width

		if ctx.sign:
			sign = self.visit(ctx.sign)
			sign = arch.DataType.S if sign else arch.DataType.U
			size = None

		return behav.TypeConv(sign, size, expr)

	def visitType_specifier(self, ctx: CoreDSL2Parser.Type_specifierContext):
		type_ = self.visit(ctx.type_)
		if ctx.ptr:
			type_.ptr = ctx.ptr.text
		return type_

	def visitInteger_type(self, ctx: CoreDSL2Parser.Integer_typeContext):
		signed = True
		width = None

		if ctx.signed is not None:
			signed = self.visit(ctx.signed)

		if ctx.size is not None:
			width = self.visit(ctx.size)

		if ctx.shorthand is not None:
			width = self.visit(ctx.shorthand)

		if isinstance(width, behav.BaseNode):
			width = width.generate(None)
		else:
			raise ValueError("width has wrong type")

		return arch.IntegerType(width, signed, None)

	def visitVoid_type(self, ctx: CoreDSL2Parser.Void_typeContext):
		return arch.VoidType(None)

	def visitBool_type(self, ctx: CoreDSL2Parser.Bool_typeContext):
		return arch.IntegerType(1, False, None)

	def visitInteger_signedness(self, ctx: CoreDSL2Parser.Integer_signednessContext):
		return SIGNEDNESS[ctx.children[0].symbol.text]

	def visitInteger_shorthand(self, ctx: CoreDSL2Parser.Integer_shorthandContext):
		return behav.IntLiteral(SHORTHANDS[ctx.children[0].symbol.text])
