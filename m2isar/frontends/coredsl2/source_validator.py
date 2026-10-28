"""Validate source information that is lost when lowering to the metamodel.

Rules follow the analyzer in the source bundle of MINRES CoreDSL 2.0.21.
The semantic pass handles known integer/array types and scoped ISA parameters.
Remaining elaboration and provider gaps are tracked in the parity map.
"""

import logging
from contextlib import contextmanager

from ...diagnostics import M2ValidationError
from ...metamodel.code_info import LineInfoFactory
from ...warnings import WarningsManager
from .constant_expressions import constant_value, integer_value, integer_literal
from .parser_gen import CoreDSL2Parser as P, CoreDSL2Visitor

logger = logging.getLogger("validate_source")


# CoreDslAnalyzer.attributeRegistry in the 2.0.21 source bundle. Parameter
# count errors intentionally share InvalidAttributePlacement upstream.
ATTRIBUTES = {
    "enable": ("instruction", 1),
    "hls": ("instruction", 0),
    "no_cont": ("instruction", 0),
    "cond": ("instruction", 0),
    "flush": ("instruction", 0),
    "type": ("instruction", 1),
    "expected_encoding_size": ("instruction", 1),
    "do_not_synthesize": ("function", 0),
    "clk_budget": ("function", 1),
    "uses_mem": ("function", 0),
    "is_pc": ("declarator", 0),
    "is_main_reg": ("declarator", 0),
    "is_main_mem": ("declarator", 0),
    "is_interlock_for": ("declarator", 1),
    # TODO: add M2-ISA-R specific attrs here automatically?
}


def location(ctx):
    return LineInfoFactory.make(
        ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop, ctx.start.line, ctx.stop.line
    )


def unresolved(ctx, kind, name):
    """The release's linking diagnostic for a name that does not resolve."""
    return M2ValidationError(
        f"Couldn't resolve reference to {kind} '{name}'.", "org.eclipse.xtext.diagnostics.Diagnostic.Linking", location(ctx)
    )


class Diagnostics(list):
    """Validation errors reported together: the first is raised, the rest are attached to it."""

    def add(self, ctx, issue, message):
        self.append(M2ValidationError(message, issue, location(ctx)))

    @contextmanager
    def collect(self):
        """Record a validation error raised in the block instead of propagating it."""
        try:
            yield
        except M2ValidationError as error:
            self.append(error)

    def raise_if_any(self):
        if self:
            self[0].related_diagnostics.extend(self[1:])
            raise self[0]


class ScopeStack:
    """Lexical scopes in ``self.scopes``: name -> entity dicts, innermost last."""

    @contextmanager
    def scope(self, names=None):
        self.scopes.append({} if names is None else names)
        try:
            yield
        finally:
            self.scopes.pop()

    @contextmanager
    def only_scopes(self, scopes):
        """Replace the whole scope stack for the block."""
        earlier, self.scopes = self.scopes, scopes
        try:
            yield
        finally:
            self.scopes = earlier


@contextmanager
def in_progress(active, key):
    """Mark ``key`` active for the block; yield whether it already was (a cycle)."""
    if key in active:
        yield True
        return
    active.add(key)
    try:
        yield False
    finally:
        active.remove(key)


def dependencies(definition):
    """Names of the instruction sets a core or instruction set builds on."""
    if isinstance(definition, P.Instruction_setContext):
        return [*definition.extension, *definition.combines]
    return definition.contributing_types


def contributors(definitions, root):
    """``root`` and every definition it builds on, each once, dependencies first."""
    result, seen = [], set()

    def visit(ctx):
        if ctx.name.text in seen:
            return
        seen.add(ctx.name.text)
        for dependency in dependencies(ctx):
            if dependency.text in definitions:
                visit(definitions[dependency.text])
        result.append(ctx)

    visit(root)
    return result


def provided(definitions, starts):
    """``starts`` and the definitions they build on, each once, in lookup precedence order."""
    result, seen = [], set()

    def visit(ctx):
        if ctx.name.text in seen:
            return
        seen.add(ctx.name.text)
        result.append(ctx)
        for dependency in dependencies(ctx):
            if dependency.text in definitions:
                visit(definitions[dependency.text])

    for start in starts:
        visit(start)
    return result


def is_const(declaration):
    return any(q.getText() == "const" for q in declaration.qualifiers)


def is_alias(type_specifier):
    return type_specifier.ptr is not None and type_specifier.ptr.text == "&"


def return_terminated(ctx):
    if isinstance(ctx, P.Block_statementContext):
        return return_terminated(ctx.block())
    if isinstance(ctx, P.BlockContext):
        return bool(ctx.items) and return_terminated(ctx.items[-1])
    if isinstance(ctx, P.Block_itemContext):
        return ctx.statement() is not None and return_terminated(ctx.statement())
    if isinstance(ctx, P.If_statementContext):
        return len(ctx.stmt) > len(ctx.cond) and all(return_terminated(stmt) for stmt in ctx.stmt)
    return isinstance(ctx, P.Return_statementContext)


def statement_expression(ctx):
    # Parentheses do not make an expression into a valid statement in MINRES.
    return isinstance(
        ctx,
        (P.Assignment_expressionContext, P.Method_callContext, P.Preinc_expressionContext, P.Postinc_expressionContext),
    )


class SourceValidator(CoreDSL2Visitor, WarningsManager):
    def __init__(self, warnings_info):
        CoreDSL2Visitor.__init__(self)
        WarningsManager.__init__(self, warnings_info)
        self.function = None
        self.loop_depth = 0
        self.switch_depth = 0

    @staticmethod
    def error(ctx, issue, message):
        raise M2ValidationError(message, issue, location(ctx))

    def warning(self, ctx, name, message):
        self.emit_warning(message, name, logger, location(ctx))

    def constant(self, ctx):
        try:
            return constant_value(ctx)
        except ZeroDivisionError:
            self.error(ctx, "DivisionByZero", "Division by zero")
        except ValueError as exc:
            self.error(ctx, "org.eclipse.xtext.diagnostics.Diagnostic.Syntax", str(exc))

    def visitInteger_type(self, ctx):
        if ctx.size is not None:
            width = self.constant(ctx.size)
            if width is not None and width <= 0:
                self.error(ctx, "InvalidIntegerTypeSize", "Integer type size must be greater than 0")
            if width is not None and width > 2147483647:
                self.error(ctx, "InvalidIntegerTypeSize", "Integer type size must not exceed Integer.MAX_VALUE")
        return self.visitChildren(ctx)

    def visitAttribute(self, ctx):
        owner = ctx.parentCtx
        if isinstance(owner, (P.InstructionContext, P.Section_instructionsContext)):
            usage = "instruction"
        elif isinstance(owner, P.Function_definitionContext):
            usage = "function"
        elif isinstance(owner, (P.DeclarationContext, P.DeclaratorContext)):
            usage = "declarator"
        else:
            usage = "alwaysBlock"
        name = ctx.name.text
        rule = ATTRIBUTES.get(name)
        if rule is None:
            self.warning(ctx, "unknown-attribute", f"Unknown attribute '{name}'")
        else:
            allowed, count = rule
            if usage != allowed:
                self.error(ctx, "InvalidAttributePlacement", f"Attribute '{name}' cannot be placed here")
            if len(ctx.params) != count:
                count_string = "1 parameter" if count == 1 else f"{count} parameters"
                self.error(
                    ctx,
                    "InvalidAttributePlacement",
                    f"Attribute '{name}' requires exactly {count_string}, but got {len(ctx.params)}",
                )
            if name == "expected_encoding_size":
                expected = self.constant(ctx.params[0])
                instructions = (
                    [owner]
                    if isinstance(owner, P.InstructionContext)
                    else [
                        instruction
                        for instruction in owner.instructions
                        if not any(attribute.name.text == name for attribute in instruction.attributes)
                    ]
                )
                for instruction in instructions:
                    actual = self.encoding_size(instruction)
                    if expected is not None and actual is not None and actual != expected:
                        self.warning(
                            instruction,
                            "unexpected-instruction-size",
                            f"Expected an encoding size of {expected}, but got {actual}",
                        )
        return self.visitChildren(ctx)

    def encoding_size(self, instruction):
        try:
            return self._encoding_size(instruction)
        except ValueError as exc:
            self.error(instruction, "org.eclipse.xtext.diagnostics.Diagnostic.Syntax", str(exc))

    def _encoding_size(self, instruction):
        total = 0
        for entry in instruction.encoding:
            if isinstance(entry, P.Bit_fieldContext):
                left, right = integer_value(entry.left.getText()), integer_value(entry.right.getText())
                if not (0 <= left <= 2147483647 and 0 <= right <= 2147483647):
                    self.error(entry, "IndexOutOfRange", "Index out of range")
                total += abs(left - right) + 1
            else:
                total += integer_literal(entry.value.getText())[1]
        return total

    def visitInstruction(self, ctx):
        self.encoding_size(ctx)
        return self.visitChildren(ctx)

    def visitFunction_definition(self, ctx):
        if ctx.extern is None and ctx.behavior is None:
            self.error(ctx, "MissingFunctionBody", "Non-extern function declaration must specify an implementation")
        previous = self.function
        self.function = ctx
        try:
            self.visitChildren(ctx)
        finally:
            self.function = previous

    def visitParameter_declaration(self, ctx):
        if is_alias(ctx.type_):
            self.error(ctx, "ReferenceParameterDeclaration", "Function parameters may not be passed by reference")
        if ctx.type_.getText() == "void":
            self.error(ctx, "VoidDeclaration", "Declarations may not use type void")
        return self.visitChildren(ctx)

    def visitEnumerator(self, ctx):
        if ctx.init is not None and ctx.init.expr is None:
            self.error(ctx.init, "InvalidListInitializer", "Enum members must not use list initializers")
        return self.visitChildren(ctx)

    def visitDeclaration(self, ctx):
        if isinstance(ctx.parentCtx, P.Composite_definitionContext):
            # Release elaboration checks field types, but skips ordinary
            # variable declaration checks. MultiDeclaration forbids initializers.
            for member in ctx.declarations:
                if member.init is not None:
                    self.error(
                        member.init,
                        "org.eclipse.xtext.diagnostics.Diagnostic.Syntax",
                        "Composite field declarations may not specify an initializer",
                    )
            return self.visitChildren(ctx)
        qualifiers = [q.getText() for q in ctx.qualifiers]
        storage = [s.getText() for s in ctx.storage]
        isa = isinstance(ctx.parentCtx, P.Section_arch_stateContext)
        if isa and ctx.type_.getText() == "void":
            self.error(ctx, "VoidDeclaration", "Declarations may not use type void")
        if isa and len(set(qualifiers)) != len(qualifiers):
            self.error(ctx, "DuplicateQualifier", "Duplicate qualifier")
        if isa and len(storage) > 1:
            self.error(
                ctx, "MultipleStorageClassSpecifiers", "A declaration may not specify more than one storage class"
            )
        # Unqualified non-alias ISA declarations are parameters, including const.
        alias = is_alias(ctx.type_)
        parameter = isa and bool(ctx.declarations) and not storage and not alias
        if parameter:
            if not isinstance(ctx.type_.type_, (P.Integer_typeContext, P.Bool_typeContext)):
                self.error(
                    ctx,
                    "InvalidIsaParameterType",
                    "ISA parameters may only have integer types (signed, unsigned, bool)",
                )
            if "volatile" in qualifiers:
                self.error(ctx, "InvalidIsaParameterDeclaration", "ISA parameters may not be declared as volatile")
        for decl in ctx.declarations:
            for dimension in decl.size:
                size = self.constant(dimension)
                if size is not None and size < 0:
                    self.error(dimension, "InvalidArraySize", "Negative array size is invalid")
                if size == 0:
                    self.warning(decl, "array-size-zero", "Array size is zero")
                if size is not None and size > 2147483647 and "extern" not in storage:
                    self.warning(decl, "invalid-array-size", "Array size is greater than Integer.MAX_VALUE")
            if parameter and "const" not in qualifiers and decl.size:
                self.error(decl, "InvalidIsaParameterDeclaration", "An ISA parameter may not be declared as an array")
            if any(s in ("extern", "register") for s in storage) and len(decl.size) > 1:
                self.error(
                    decl.size[-2], "MultidimensionalAddressSpace", "Multidimensional address spaces are not allowed"
                )
            if isa and alias and decl.init is None:
                self.error(decl, "UninitializedAlias", "An identifier declared as alias must be initialized")
            if isa and alias and decl.init.expr is None:
                self.error(
                    decl, "InvalidListInitializer", "An identifier declared as alias must not use a list initializer"
                )
            if (
                isa
                and "const" in qualifiers
                and decl.init is None
                and not isinstance(ctx.parentCtx, P.Composite_definitionContext)
                and not any(s in ("extern", "register") for s in storage)
            ):
                self.error(decl, "UninitializedConstant", "An identifier declared as const must be initialized")
        return self.visitChildren(ctx)

    def visitBlock(self, ctx):
        unreachable = False
        for item in ctx.items:
            self.visit(item)
            if unreachable:
                self.warning(item, "unreachable-code", "Unreachable code")
            if return_terminated(item):
                unreachable = True

    def visitReturn_statement(self, ctx):
        return self.visitChildren(ctx)

    def visitBreak_statement(self, ctx):
        if not (self.loop_depth or self.switch_depth):
            self.error(ctx, "StrayControlFlowStatement", "Unexpected break statement")

    def visitContinue_statement(self, ctx):
        if not self.loop_depth:
            self.error(ctx, "StrayControlFlowStatement", "Unexpected continue statement")

    def visit_loop(self, ctx):
        condition = ctx.cond.end_expr if isinstance(ctx, P.For_statementContext) else ctx.cond
        if condition is not None:
            self.check_condition(condition)
        self.loop_depth += 1
        try:
            return self.visitChildren(ctx)
        finally:
            self.loop_depth -= 1

    visitFor_statement = visit_loop
    visitWhile_statement = visit_loop
    visitDo_statement = visit_loop

    def visitSwitch_statement(self, ctx):
        self.switch_depth += 1
        try:
            return self.visitChildren(ctx)
        finally:
            self.switch_depth -= 1

    def visitSpawn_statement(self, ctx):
        parent = ctx.parentCtx
        direct = isinstance(parent, P.InstructionContext) and parent.behavior is ctx
        if isinstance(parent, P.Block_itemContext):
            block = parent.parentCtx
            block_stmt = block.parentCtx
            instruction = block_stmt.parentCtx
            direct = (
                isinstance(instruction, P.InstructionContext)
                and instruction.behavior is block_stmt
                and block.items[-1] is parent
            )
        if not direct:
            self.error(
                ctx,
                "InvalidSpawnStatementPlacement",
                "A spawn statement must be the last statement of an instruction's behavior block",
            )
        return self.visitChildren(ctx)

    def visitExpression_statement(self, ctx):
        # The semantic pass must inspect the expression before checking whether
        # it can be a statement, so child diagnostics are not lost.
        return self.visitChildren(ctx)

    def visitFor_condition(self, ctx):
        return self.visitChildren(ctx)

    def check_condition(self, expr):
        if isinstance(expr, P.Assignment_expressionContext) and expr.bop.text == "=":
            self.warning(expr, "likely-accidental-assignment", "Likely accidental assignment")

    def visitIf_statement(self, ctx):
        for cond in ctx.cond:
            self.check_condition(cond)
        return self.visitChildren(ctx)


def validate_source(tree, warnings_info, parameter_values=None):

    try:
        _validate_source(tree, warnings_info, parameter_values)
    except M2ValidationError as error:
        if error.issue_code in (
            "com.minres.coredsl.DivisionByZero",
            "com.minres.coredsl.InvalidConstantExpressionNode",
            "com.minres.coredsl.InvalidConstantExpressionIdentifier",
            "com.minres.coredsl.UnsupportedLanguageFeature",
            "com.minres.coredsl.InvalidArraySize",
            "com.minres.coredsl.MultidimensionalAddressSpace",
            "com.minres.coredsl.UnassignedIsaParameter",
            "com.minres.coredsl.InvalidIntegerTypeSize",
        ):
            from .source_semantics import invalid_elaboration_summaries

            for diagnostic in invalid_elaboration_summaries(tree, parameter_values):

                def already_reported(existing):
                    primary, related = existing.line_info, diagnostic.line_info
                    same_location = (
                        primary is not None
                        and related is not None
                        and primary.file_path == related.file_path
                        and primary.start_chr <= related.stop_chr
                        and related.start_chr <= primary.stop_chr
                    )
                    return (diagnostic.issue_code == existing.issue_code and same_location) or any(
                        already_reported(child) for child in existing.related_diagnostics
                    )

                if already_reported(error):
                    continue
                error.related_diagnostics.append(diagnostic)
        raise


def _validate_source(tree, warnings_info, parameter_values=None):
    validator = SourceValidator(warnings_info)
    definitions = {ctx.name.text: ctx for ctx in tree.definitions if isinstance(ctx, P.Instruction_setContext)}
    linking_errors = Diagnostics()
    for definition in tree.definitions:
        for dependency in dependencies(definition):
            if dependency.text not in definitions:
                linking_errors.append(unresolved(definition, "InstructionSet", dependency.text))
    from .source_linking import NameLinker

    with linking_errors.collect():
        NameLinker(tree).validate(tree)
    linking_errors.raise_if_any()
    cycle_errors = Diagnostics()
    for root in definitions:
        stack, visited = [], set()

        def check_inheritance(name):
            if name in stack:
                if name == root:
                    chain = stack[stack.index(name) :] + [name]
                    cycle_errors.append(
                        M2ValidationError(
                            "Cyclic instruction set inheritance: " + " -> ".join(chain),
                            "CyclicInstructionSetInheritance",
                            location(definitions[root]),
                        )
                    )
                return
            if name in visited:
                return
            visited.add(name)
            stack.append(name)
            ctx = definitions[name]
            for dependency in [*ctx.extension, *ctx.combines]:
                check_inheritance(dependency.text)
            stack.pop()

        check_inheritance(root)
    cycle_errors.raise_if_any()
    validator.visit(tree)
    from .source_semantics import validate_semantics

    validate_semantics(tree, warnings_info, parameter_values)
