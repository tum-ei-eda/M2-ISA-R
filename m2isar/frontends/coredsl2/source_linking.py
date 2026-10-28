"""Resolve source references before semantic validation, as Xtext does."""
from .source_validator import Diagnostics, ScopeStack, contributors, dependencies, provided, unresolved
from .parser_gen import CoreDSL2Parser as P, CoreDSL2Visitor

def reference(ctx):
    if isinstance(ctx, P.Primary_expressionContext):
        ctx = ctx.primary()
    return ctx if isinstance(ctx, P.Reference_expressionContext) else None


class NameLinker(CoreDSL2Visitor, ScopeStack):
    def __init__(self, tree):
        self.definitions = {ctx.name.text: ctx for ctx in tree.definitions
                            if isinstance(ctx, P.Instruction_setContext)}
        self.scopes = []
        self.missing = []
        self.diagnostics = Diagnostics()
        self.composites = {}

    def known(self, name):
        return any(name in scope for scope in reversed(self.scopes))

    def entity_names(self, isa, include_state=True):
        names = {}
        for section in isa.sections:
            if isinstance(section, P.Section_functionsContext):
                names.update((function.name.text, function) for function in section.functions)
            if isinstance(section, P.Section_arch_stateContext):
                for enum in section.enum_types:
                    names.update((member.name.text, member) for member in enum.enumerator_list().enumerators)
                if include_state:
                    names.update((decl.name.text, decl) for declaration in section.declarations
                                 for decl in declaration.declarations)
        return names

    def visitDescription_content(self, ctx):
        for root in ctx.definitions:
            inherited = {}
            # The root itself is not marked as visited, so a cyclic dependency
            # still inherits it (the cycle is reported after linking).
            for isa in provided(self.definitions, [self.definitions[dependency.text]
                                                   for dependency in dependencies(root)
                                                   if dependency.text in self.definitions]):
                for name, entity in self.entity_names(isa).items():
                    inherited.setdefault(name, entity)
            self.composites = {}
            self.types = {}
            for isa in contributors(self.definitions, root):
                for section in isa.sections:
                    if isinstance(section, P.Section_arch_stateContext):
                        for definition in section.composite_types:
                            key = definition.type_.getText(), definition.name.text
                            self.composites.setdefault(key, definition)
                            self.types.setdefault(key, definition)
                        for definition in section.enum_types:
                            self.types.setdefault(('enum', definition.name.text), definition)
            initial = inherited | self.entity_names(root, include_state=False)
            complete = inherited | self.entity_names(root)
            self.scopes = [initial]
            for section in root.sections:
                if isinstance(section, P.Section_arch_stateContext):
                    for child in section.children or []:
                        if isinstance(child, P.DeclarationContext):
                            self.visit(child)
                        elif isinstance(child, (P.Enum_definitionContext, P.Composite_definitionContext)):
                            # Type declarations use full ISA entity scope.
                            with self.only_scopes([complete]):
                                self.visit(child)
                        elif hasattr(child, 'accept'):
                            self.visit(child)
            self.scopes = [complete]
            for section in root.sections:
                if not isinstance(section, P.Section_arch_stateContext):
                    self.visit(section)
        return self.missing

    def visitDeclaration(self, ctx):
        self.visit(ctx.type_)
        for declarator in ctx.declarations:
            self.visit(declarator)
            self.scopes[-1][declarator.name.text] = declarator

    def visitBlock(self, ctx):
        with self.scope():
            for item in ctx.items:
                self.visit(item)

    def visitFor_statement(self, ctx):
        with self.scope():
            return self.visitChildren(ctx)

    def visitFunction_definition(self, ctx):
        params = [] if ctx.params is None else ctx.params.params
        with self.scope({param.decl.name.text: param.decl for param in params if param.decl is not None}):
            return self.visitChildren(ctx)

    def visitInstruction(self, ctx):
        with self.scope({field.name.text: field for field in ctx.encoding if isinstance(field, P.Bit_fieldContext)}):
            return self.visitChildren(ctx)

    def visitReference_expression(self, ctx):
        if not self.known(ctx.ref.text):
            self.record(ctx, 'NamedEntity', ctx.ref.text)

    def visitProcedure_call(self, ctx):
        self.visitReference_expression(ctx)
        return self.visitChildren(ctx)

    visitMethod_call = visitProcedure_call

    def visitComposite_definition(self, ctx):
        for declaration in ctx.declarations:
            with self.scope():
                self.visit(declaration)

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]

    def type_specifier(self, expr):
        if isinstance(expr, P.Primary_expressionContext):
            return self.type_specifier(expr.primary())
        if isinstance(expr, P.Parens_expressionContext):
            return self.type_specifier(expr.expr)
        if isinstance(expr, P.Reference_expressionContext):
            declaration = self.lookup(expr.ref.text)
            return getattr(getattr(declaration, 'parentCtx', None), 'type_', None)
        if isinstance(expr, (P.Procedure_callContext, P.Method_callContext)):
            # Release 2.0.21 cannot supply a member scope directly from a
            # function-call result, even when its return type is composite.
            # Preserve its linking failure before semantic call diagnostics.
            return None
        if isinstance(expr, P.Cast_expressionContext):
            return expr.type_
        if isinstance(expr, P.Slice_expressionContext):
            return self.type_specifier(expr.expr)
        if isinstance(expr, P.Deref_expressionContext):
            member = self.members(self.type_specifier(expr.expr)).get(expr.ref.text)
            return None if member is None else member.parentCtx.type_
        return None

    def members(self, type_specifier):
        if type_specifier is None:
            return {}
        reference = type_specifier.type_
        if not isinstance(reference, P.Composite_referenceContext):
            return {}
        definition = self.composites.get((reference.type_.getText(), reference.name.text))
        members = {}
        if definition is not None:
            for declaration in definition.declarations:
                for member in declaration.declarations:
                    members.setdefault(member.name.text, member)
        return members

    def visitDeref_expression(self, ctx):
        self.visit(ctx.expr)
        if ctx.ref.text not in self.members(self.type_specifier(ctx.expr)):
            self.record(ctx, 'Declarator', ctx.ref.text)

    def visitIntrinsic_expression(self, ctx):
        if ctx.ref.text in ('offsetof', 'bitoffsetof') and len(ctx.args) == 2:
            first, second = ctx.args
            self.visit(first)
            type_specifier = first.type_ if first.type_ is not None else self.type_specifier(first.expr)
            with self.only_scopes([self.members(type_specifier) if reference(second.expr) is not None else {}]):
                self.visit(second)
            return
        return self.visitChildren(ctx)

    def visitComposite_reference(self, ctx):
        if (ctx.type_.getText(), ctx.name.text) not in self.types:
            self.record(ctx, ctx.type_.getText().capitalize() + 'TypeDeclaration', ctx.name.text)

    def visitEnum_reference(self, ctx):
        if ('enum', ctx.name.text) not in self.types:
            self.record(ctx, 'EnumTypeDeclaration', ctx.name.text)

    def record(self, ctx, kind, name):
        self.missing.append(name)
        self.diagnostics.append(unresolved(ctx, kind, name))

    def validate(self, tree):
        self.visit(tree)
        self.diagnostics.raise_if_any()
