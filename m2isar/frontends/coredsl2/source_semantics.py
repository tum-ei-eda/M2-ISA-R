"""Source semantic validation before simplification and model lowering.

Keeps ISA parameter values separate for each root ISA and preserves block
scope. Currently models integers, arrays, address spaces and function signatures;
unknown composite/pointer/intrinsic types are explicitly deferred.
"""
import logging
from dataclasses import dataclass

from ...warnings import WarningsManager
from ...diagnostics import M2ValidationError
from .constant_expressions import constant_value, integer_literal
from .parser_gen import CoreDSL2Parser as P, CoreDSL2Visitor
from .source_types import UNKNOWN, VOID, BOOL, DslType, integer, common_integer, convertible, holds_value
from .source_validator import SourceValidator, location, statement_expression, return_terminated

logger = logging.getLogger('validate_source')


@dataclass(eq=False)
class Symbol:
    declaration: object = None
    declarator: object = None
    ty: DslType = None
    storage: str = 'local'
    const: bool = False
    value_expression: object = None
    function: object = None
    known_value: int = None
    enum_predecessor: object = None
    enum_offset: int = 0
    enum_definition: object = None


def reference(ctx):
    if isinstance(ctx, P.Primary_expressionContext):
        ctx = ctx.primary()
    return ctx if isinstance(ctx, P.Reference_expressionContext) else None


class SemanticValidator(CoreDSL2Visitor, WarningsManager):
    error = staticmethod(SourceValidator.error)

    def __init__(self, tree, warnings_info, parameter_values=None):
        CoreDSL2Visitor.__init__(self)
        WarningsManager.__init__(self, warnings_info)
        self.parameter_values = parameter_values or {}
        self.definitions = {ctx.name.text: ctx for ctx in tree.definitions}
        self.scopes = []
        self.symbols = {}
        self.reference_symbols = {}
        self.values_in_progress = set()
        self.types_in_progress = set()
        self.function = None
        self.partial = False
        self.checked = set()
        self.elaborating = False
        self.enum_definitions = {}
        self.enum_members = {}
        self.enum_types = {}
        self.enum_named_types = {}
        self.composite_definitions = {}
        self.composite_members = {}
        self.composite_types = {}

    def warning(self, ctx, name, message):
        # SourceValidator already handles literal-only sizes. Emit only new,
        # parameter-dependent diagnostics here to avoid duplicates.
        key = (id(ctx), name)
        if key not in self.checked:
            self.checked.add(key)
            self.emit_warning(message, name, logger, location(ctx))

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return self.reference_symbols.get(name, self.symbols.get(name))

    def evaluate(self, ctx, required=False):
        def resolve(node):
            symbol = self.lookup(node.ref.text)
            if (symbol is self.reference_symbols.get(node.ref.text)
                    and symbol is not None and symbol.storage == 'param'):
                # Constant values come from elaboration; lexical declarations
                # still determine the type and qualifiers of a reference.
                symbol = self.symbols.get(node.ref.text, symbol)
            if symbol is None:
                if required:
                    self.error(node, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking',
                               f"Couldn't resolve reference to NamedEntity '{node.ref.text}'.")
                return None  # Linking diagnostics still belong to the frontend.
            if symbol.storage not in ('param', 'enum'):
                if required:
                    self.error(node, 'InvalidConstantExpressionIdentifier',
                               'Identifiers in constant expressions may only refer to ISA parameters or enum constants')
                return None
            if symbol.known_value is not None:
                return symbol.known_value
            if symbol.storage == 'enum' and symbol.enum_predecessor is not None:
                if symbol in self.values_in_progress:
                    return None
                self.values_in_progress.add(symbol)
                try:
                    value = self.evaluate(symbol.enum_predecessor.value_expression, required)
                    return None if value is None else value + symbol.enum_offset
                finally:
                    self.values_in_progress.remove(symbol)
            if symbol in self.values_in_progress or symbol.value_expression is None:
                return None
            self.values_in_progress.add(symbol)
            try:
                return self.evaluate(symbol.value_expression, required)
            finally:
                self.values_in_progress.remove(symbol)
        def unsupported(node):
            if isinstance(node, P.Intrinsic_expressionContext):
                return self.intrinsic_value(node, constant=True)
            if not required:
                return None
            if isinstance(node, P.Binary_expressionContext):
                self.error(node, 'UnsupportedLanguageFeature',
                           f'Infix expression {node.bop.text} is currently unsupported in constant expressions')
            if isinstance(node, P.Prefix_expressionContext):
                message = f'prefix operator {node.prefix.text} is not allowed in constant expression'
            else:
                message = f'{type(node).__name__.replace("Context", "")} is not allowed in constant expression'
            self.error(node, 'InvalidConstantExpressionNode', message)
        try:
            return constant_value(ctx, resolve, unsupported)
        except ZeroDivisionError:
            self.error(ctx, 'DivisionByZero', 'Division by zero')
        except ValueError as exc:
            self.error(ctx, 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax', str(exc))

    def specified_type(self, ctx):
        if ctx.ptr is not None and ctx.ptr.text == '*':
            return UNKNOWN
        value_type = ctx.type_
        if isinstance(value_type, P.Integer_typeContext):
            signed = value_type.signed is None or value_type.signed.getText() != 'unsigned'
            width = (self.evaluate(value_type.size, True) if value_type.size is not None else
                     {'char': 8, 'short': 16, 'int': 32, 'long': 64}[value_type.shorthand.getText()])
            if width is not None and width <= 0:
                self.error(ctx, 'InvalidIntegerTypeSize', 'Integer type size must be greater than 0')
            if width is not None and width > 2147483647:
                self.error(ctx, 'InvalidIntegerTypeSize', 'Integer type size must not exceed Integer.MAX_VALUE')
            return integer(width, signed)
        if isinstance(value_type, P.Bool_typeContext):
            return BOOL
        if isinstance(value_type, P.Void_typeContext):
            return VOID
        if isinstance(value_type, P.Enum_referenceContext):
            if value_type.name.text in self.enum_named_types:
                return self.enum_named_types[value_type.name.text]
            definition = self.enum_definitions.get(value_type.name.text)
            if definition is None:
                self.error(ctx, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking',
                           f"Couldn't resolve reference to EnumTypeDeclaration '{value_type.name.text}'.")
            return self.enum_type(definition)
        if isinstance(value_type, P.Composite_referenceContext):
            definition = self.composite_definitions.get((value_type.type_.getText(), value_type.name.text))
            if definition is None:
                kind = value_type.type_.getText().capitalize()
                self.error(ctx, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking',
                           f"Couldn't resolve reference to {kind}TypeDeclaration '{value_type.name.text}'.")
            return self.composite_type(definition)
        # User types, floats and pointer forms need a dedicated type provider.
        return UNKNOWN

    def symbol_type(self, symbol):
        if symbol.enum_definition is not None:
            return self.enum_type(symbol.enum_definition)
        if symbol.ty is not None:
            return symbol.ty
        if symbol in self.types_in_progress or symbol.declaration is None:
            return UNKNOWN
        self.types_in_progress.add(symbol)
        try:
            ty = self.specified_type(symbol.declaration.type_)
            dimensions = symbol.declarator.size
            for dimension in reversed(dimensions):
                size = self.evaluate(dimension, True)
                if size is not None and size < 0:
                    self.error(dimension, 'InvalidArraySize', 'Negative array size is invalid')
                literal = constant_value(dimension)
                if literal is None and size == 0:
                    self.warning(dimension, 'array-size-zero', 'Array size is zero')
                if literal is None and size is not None and size > 2147483647 and symbol.storage != 'extern':
                    self.warning(dimension, 'invalid-array-size', 'Array size is greater than Integer.MAX_VALUE')
                ty = DslType('address' if any(s.getText() == 'extern' for s in getattr(symbol.declaration, 'storage', [])) else 'array',
                             element=ty, count=size)
            symbol.ty = ty
            return ty
        finally:
            self.types_in_progress.remove(symbol)

    def enum_type(self, definition):
        identity = id(definition)
        if identity in self.enum_types:
            return self.enum_types[identity]
        if identity in self.types_in_progress:
            return UNKNOWN
        self.types_in_progress.add(identity)
        try:
            base = integer(1)
            for symbol in self.enum_members[identity]:
                if symbol.known_value is not None:
                    value = symbol.known_value
                elif symbol.enum_predecessor is not None:
                    value = self.evaluate(symbol.enum_predecessor.value_expression, True)
                    if value is not None:
                        value += symbol.enum_offset
                else:
                    value = self.evaluate(symbol.value_expression, True)
                if value is None:
                    return UNKNOWN
                smallest = integer(max(1, (~value).bit_length() + 1 if value < 0 else value.bit_length()), value < 0)
                base = common_integer(base, smallest)
            result = DslType('enum', width=base.width, element=base, identity=identity, name=definition.name.text)
            self.enum_types[identity] = result
            return result
        finally:
            self.types_in_progress.remove(identity)

    def contributors(self, root):
        result, seen = [], set()
        def visit(ctx):
            if ctx.name.text in seen:
                return
            seen.add(ctx.name.text)
            names = ([*ctx.extension, *ctx.combines] if isinstance(ctx, P.Instruction_setContext)
                     else ctx.contributing_types)
            for name in names:
                if name.text in self.definitions:
                    visit(self.definitions[name.text])
            result.append(ctx)
        visit(root)
        return result

    def composite_type(self, definition):
        identity = id(definition)
        if identity in self.composite_types:
            return self.composite_types[identity]
        if identity in self.types_in_progress:
            return UNKNOWN
        self.types_in_progress.add(identity)
        try:
            sizes = [self.bit_size(self.symbol_type(member)) for member in self.composite_members[identity]]
            if any(size is None for size in sizes):
                return UNKNOWN
            kind = definition.type_.getText()
            width = sum(sizes) if kind == 'struct' else max(sizes, default=0)
            result = DslType(kind, width=width, identity=identity, name=definition.name.text)
            self.composite_types[identity] = result
            return result
        finally:
            self.types_in_progress.remove(identity)

    def reference_scope(self, root):
        """Resolve references in their defining ISA, independently of values."""
        result, seen = {}, set()
        def visit(isa):
            if isa.name.text in seen:
                return
            seen.add(isa.name.text)
            for name, symbol in self.owner_symbols.get(isa.name.text, {}).items():
                result.setdefault(name, symbol)
            dependencies = ([*isa.extension, *isa.combines] if isinstance(isa, P.Instruction_setContext)
                            else isa.contributing_types)
            for dependency in dependencies:
                if dependency.text in self.definitions:
                    visit(self.definitions[dependency.text])
        visit(root)
        return result

    def build_symbols(self, contributors):
        self.owner_symbols = {}
        self.symbols = {}
        self.reference_symbols = {}
        self.declarations = {}
        self.signatures = {}
        self.enum_definitions = {}
        self.enum_members = {}
        self.enum_types = {}
        self.composite_definitions = {}
        self.composite_members = {}
        self.composite_types = {}
        for isa in contributors:
            owner_symbols = self.owner_symbols.setdefault(isa.name.text, {})
            for section in isa.sections:
                if isinstance(section, P.Section_arch_stateContext):
                    for composite in section.composite_types:
                        self.composite_definitions.setdefault(
                            (composite.type_.getText(), composite.name.text), composite)
                        members = []
                        for declaration in composite.declarations:
                            for member in declaration.declarations:
                                members.append(Symbol(declaration, member, storage='field',
                                                      const=any(q.getText() == 'const' for q in declaration.qualifiers)))
                        self.composite_members[id(composite)] = members
                    for enum in section.enum_types:
                        self.enum_definitions.setdefault(enum.name.text, enum)
                        self.enum_members[id(enum)] = []
                        predecessor = None
                        predecessor_index = 0
                        for index, member in enumerate(enum.enumerator_list().enumerators):
                            symbol = Symbol(declarator=member, storage='enum', const=True, enum_definition=enum,
                                            value_expression=None if member.init is None else member.init.expr)
                            if symbol.value_expression is not None:
                                predecessor, predecessor_index = symbol, index
                            elif predecessor is None:
                                symbol.known_value = index
                            else:
                                symbol.enum_predecessor = predecessor
                                symbol.enum_offset = index - predecessor_index
                            self.symbols[member.name.text] = symbol
                            owner_symbols[member.name.text] = symbol
                            self.enum_members[id(enum)].append(symbol)
                    for declaration in section.declarations:
                        storage = [item.getText() for item in declaration.storage]
                        alias = declaration.type_.ptr is not None and declaration.type_.ptr.text == '&'
                        kind = 'alias' if alias else storage[0] if storage else 'param'
                        for declarator in declaration.declarations:
                            initializer = declarator.init
                            symbol = Symbol(
                                declaration, declarator, storage=kind,
                                const=any(q.getText() == 'const' for q in declaration.qualifiers),
                                value_expression=None if initializer is None else initializer.expr)
                            self.declarations.setdefault(declarator.name.text, []).append((isa, symbol))
                            self.symbols[declarator.name.text] = symbol
                            owner_symbols[declarator.name.text] = symbol
                elif isinstance(section, P.Section_functionsContext):
                    for function in section.functions:
                        symbol = Symbol(function=function, storage='function')
                        self.symbols[function.name.text] = symbol
                        owner_symbols[function.name.text] = symbol
        self.reference_symbols = self.reference_scope(contributors[-1]) if contributors else {}
        enum_names = {}
        for members in self.enum_members.values():
            for symbol in members:
                name = symbol.declarator.name.text
                if name in enum_names or name in self.declarations:
                    # Release duplicate signature analysis crashes on enum
                    # members' absent type specifiers. Report the collision
                    # directly rather than silently overwriting a constant.
                    self.error(symbol.declarator, 'DuplicateIsaStateElement',
                               f'ISA state element {name} has been declared multiple times')
                enum_names[name] = symbol
        # Root parameter assignments override inherited defaults before evaluating
        # any dependent type. Register/memory initialization is not a parameter.
        for isa in contributors:
            for section in isa.sections:
                if isinstance(section, P.Section_arch_stateContext):
                    for expression in section.expressions:
                        if isinstance(expression, P.Assignment_expressionContext):
                            target = reference(expression.left)
                            symbol = None if target is None else self.symbols.get(target.ref.text)
                            if symbol is not None and symbol.storage == 'param' and expression.bop.text == '=':
                                symbol.value_expression = expression.right

    def visitDescription_content(self, ctx):
        errors = []
        for root in ctx.definitions:
            try:
                self.validate_root(root, errors)
            except M2ValidationError as error:
                errors.append(error)
            finally:
                self.scopes = []
                self.function = None
                self.elaborating = False
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def validate_root(self, root, errors):
        self.partial = isinstance(root, P.Instruction_setContext)
        contributors = self.contributors(root)
        self.build_symbols(contributors)
        for name, value in self.parameter_values.items():
            symbol = self.symbols.get(name)
            if symbol is not None and symbol.storage == 'param':
                symbol.known_value = value
        self.scopes = []
        self.checked.clear()
        self.elaborating = True
        self.validate_isa_assignments(contributors)
        for symbol in self.symbols.values():
            if symbol.function is None:
                self.symbol_type(symbol)
        try:
            self.validate_duplicates(root, contributors)
        except M2ValidationError as error:
            # Duplicate/signature errors leave reference and value bindings available.
            # Keep checking independent initializers and behavior diagnostics.
            if error.issue_code not in {'com.minres.coredsl.DuplicateIsaStateElement',
                                        'com.minres.coredsl.MismatchingIsaStateElementSignatures'}:
                raise
            errors.append(error)
        try:
            self.validate_parameter_results(root)
        except M2ValidationError as error:
            # Completion diagnostics leave a usable symbol table. Evaluation
            # failures still require the ordinary elaboration failure path.
            if error.issue_code not in {
                    'com.minres.coredsl.UnassignedIsaParameter',
                    'com.minres.coredsl.IndeterminableIsaStateElementValue',
                    'com.minres.coredsl.IndeterminableIsaStateElementType'}:
                raise
            errors.append(error)
        for members in self.composite_members.values():
            for symbol in members:
                ty = self.symbol_type(symbol)
                if symbol.declarator.init is not None:
                    try:
                        self.validate_initializer(symbol.declarator.init, ty)
                    except M2ValidationError as error:
                        errors.append(error)
        for symbol in self.symbols.values():
            if symbol.function is None:
                try:
                    if symbol.storage == 'alias':
                        self.validate_alias(symbol)
                    elif symbol.declarator.init is not None:
                        self.validate_initializer(symbol.declarator.init, self.symbol_type(symbol), isa=True)
                except M2ValidationError as error:
                    errors.append(error)
        self.elaborating = False
        root_scope = self.reference_symbols
        try:
            for isa in contributors:
                self.reference_symbols = self.reference_scope(isa)
                # The release groups definitions by kind, independent of the
                # textual order of sections within an ISA.
                for kind in (P.Section_functionsContext, P.Section_instructionsContext,
                             P.Section_alwaysContext):
                    for section in isa.sections:
                        if isinstance(section, kind):
                            try:
                                self.visit(section)
                            except M2ValidationError as error:
                                errors.append(error)
        finally:
            self.reference_symbols = root_scope

    def visitSection_functions(self, ctx):
        self.check_statement_parts((self.visit, function) for function in ctx.functions)

    def visitSection_instructions(self, ctx):
        self.check_statement_parts((self.visit, child)
                                   for child in list(ctx.attributes) + list(ctx.instructions))

    def visitSection_always(self, ctx):
        self.check_statement_parts((self.visit, child)
                                   for child in list(ctx.attributes) + list(ctx.always_blocks))

    def validate_isa_assignments(self, contributors):
        for isa in contributors:
            dependencies = isa.combines if isinstance(isa, P.Instruction_setContext) else isa.contributing_types
            names = [dependency.text for dependency in dependencies]
            if len(names) != len(set(names)):
                self.error(isa, 'MultipleIdenticalProvides', 'Core provides the instruction set multiple times')
            for section in isa.sections:
                if not isinstance(section, P.Section_arch_stateContext):
                    continue
                for expression in section.expressions:
                    if not isinstance(expression, P.Assignment_expressionContext):
                        self.error(expression, 'InvalidIsaParameterAssignmentExpression',
                                   'Only assignment expressions are allowed in ISA level expression statements')
                    if expression.bop.text != '=':
                        self.error(expression, 'InvalidIsaParameterAssignmentOperator',
                                   'Only regular assignments (=) are allowed in ISA level expression statements')
                    target = reference(expression.left)
                    symbol = None if target is None else self.symbols.get(target.ref.text)
                    if target is not None and symbol is None:
                        self.error(target, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking',
                                   f"Couldn't resolve reference to NamedEntity '{target.ref.text}'.")
                    if target is None or (symbol is not None and (symbol.storage != 'param' or symbol.const)):
                        self.error(expression, 'InvalidIsaParameterAssignmentTarget',
                                   'ISA level assignment must assign to a non-constant ISA parameter')

    def validate_duplicates(self, root, contributors):
        # MINRES first reports declarations that collide with names already
        # exposed by the same ISA or its dependencies. Independent provides can
        # still contribute equal parameter declarations with a warning.
        exposed = {}
        errors = []
        for isa in contributors:
            dependencies = ([*isa.extension, *isa.combines] if isinstance(isa, P.Instruction_setContext)
                            else isa.contributing_types)
            names = set().union(*(exposed.get(dep.text, set()) for dep in dependencies))
            for name, records in self.declarations.items():
                for owner, symbol in records:
                    if owner is isa:
                        if name in names:
                            errors.append(M2ValidationError(
                                f'An identifier with the name {name} has already been declared',
                                'DuplicateIsaStateElement', location(symbol.declarator)))
                        names.add(name)
            exposed[isa.name.text] = names
        for name, records in self.declarations.items():
            if len(records) < 2:
                continue
            signatures = []
            for owner, symbol in records:
                declaration = symbol.declaration
                signatures.append((symbol.const,
                                   any(q.getText() == 'volatile' for q in declaration.qualifiers),
                                   tuple(s.getText() for s in declaration.storage),
                                   self.specified_type(declaration.type_), symbol.storage == 'alias'))
            if any(signature != signatures[0] for signature in signatures[1:]):
                errors.append(M2ValidationError(
                    f'ISA state element {name} has been declared multiple times with mismatching signatures',
                    'MismatchingIsaStateElementSignatures', location(root)))
                continue
            if records[0][1].storage == 'param':
                self.warning(root, 'duplicate-isa-state-element',
                             f'ISA parameter {name} has been declared multiple times')
            else:
                errors.append(M2ValidationError(
                    f'ISA state element {name} has been declared multiple times',
                    'DuplicateIsaStateElement', location(root)))
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def validate_parameter_results(self, root):
        if self.partial:
            return
        unassigned, indeterminate = [], []
        for name, symbol in self.symbols.items():
            if symbol.storage != 'param' or symbol.known_value is not None:
                continue
            if symbol.value_expression is None and symbol.declarator.init is None:
                unassigned.append(name)
            elif (symbol.value_expression is not None
                  and self.evaluate(symbol.value_expression, True) is None
                  and self.parameter_cycle(symbol, set())):
                indeterminate.append(name)
        if unassigned:
            self.error(root, 'UnassignedIsaParameter',
                       'The following ISA parameters are never assigned: ' + ', '.join(unassigned))
        if indeterminate:
            self.error(root, 'IndeterminableIsaStateElementValue',
                       'The values of the following state elements could not be determined because they depend on other indeterminable values: ' + ', '.join(indeterminate))
        indeterminate_types = [name for name, symbol in self.symbols.items()
                               if self.composite_type_cycle(symbol, set())]
        if indeterminate_types:
            self.error(root, 'IndeterminableIsaStateElementType',
                       'The types of the following state elements could not be determined because they depend on other indeterminable values: '
                       + ', '.join(indeterminate_types))

    def composite_type_cycle(self, symbol, active):
        if symbol.declaration is None or symbol.declaration.type_.ptr is not None:
            return False
        specified = symbol.declaration.type_.type_
        if not isinstance(specified, P.Composite_referenceContext):
            return False
        definition = self.composite_definitions.get((specified.type_.getText(), specified.name.text))
        if definition is None:
            return False  # Missing names have separate linking diagnostics.
        identity = id(definition)
        if identity in active:
            return True
        return any(self.composite_type_cycle(member, active | {identity})
                   for member in self.composite_members[identity])

    def parameter_cycle(self, symbol, active):
        # Deferred intrinsic/type providers are not proof of an invalid value.
        identity = id(symbol)
        if identity in active:
            return True
        if symbol.value_expression is None:
            return False
        active = active | {identity}
        return any(self.parameter_cycle(dependency, active)
                   for dependency in self.parameter_references(symbol.value_expression))

    def validate_initializer(self, initializer, target, isa=False):
        if initializer.expr is not None:
            expression = initializer.expr
            errors = []
            source = self.recover_expression_type(expression, errors)
            try:
                self.check_conversion(expression, source, target, 'InvalidAssignmentType')
            except M2ValidationError as error:
                errors.append(error)
            if isa:
                try:
                    self.evaluate(expression, True)
                except M2ValidationError as error:
                    errors.append(error)
            if errors:
                errors[0].related_diagnostics.extend(errors[1:])
                raise errors[0]
            return
        if target == UNKNOWN:
            return
        if target.kind not in ('array', 'address'):
            self.error(initializer, 'InvalidListInitializer', f'Cannot use list initializer to initialize value of type {target}')
        elements = initializer.initializerList().initializer()
        errors = []
        if target.count is not None and target.count != len(elements):
            errors.append(M2ValidationError(
                'List initializer size does not match LHS size',
                'InvalidAssignmentType', location(initializer)))
        for element in elements:
            if element.expr is None:
                # Unsupported nested lists do not analyze their children.
                errors.append(M2ValidationError(
                    'Nested list initializers are unsupported',
                    'UnsupportedLanguageFeature', location(initializer)))
                continue
            try:
                self.validate_initializer(element, target.element, isa=isa)
            except M2ValidationError as error:
                errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def validate_alias(self, symbol):
        expression = symbol.value_expression
        if expression is None:
            return  # Structural checks already diagnose missing/list initializers.
        errors = []
        target = self.symbol_type(symbol)
        source = self.expression_type(expression)
        if UNKNOWN not in (target, source) and source != target:
            allowed_range = False
            if isinstance(expression, P.Slice_expressionContext) and expression.right is not None and target.kind in ('array', 'address'):
                base = self.expression_type(expression.expr)
                if (base.kind in ('array', 'address') and base.element == target.element
                        and target.count is not None and target.element.integer and source.integer):
                    allowed_range = target.count * target.element.width == source.width
            if not allowed_range:
                errors.append(M2ValidationError(
                    f'Alias must be initialized with exactly the same type it is declared as ({target}), but got {source}',
                    'InvalidAssignmentType', location(symbol.declarator)))
        try:
            self.alias_source(symbol, expression)
        except M2ValidationError as error:
            errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def alias_source(self, alias, expression):
        if isinstance(expression, P.Primary_expressionContext):
            return self.alias_source(alias, expression.primary())
        if isinstance(expression, P.Reference_expressionContext):
            source = self.lookup(expression.ref.text)
            if source is None:
                return  # Linking still owns unresolved names.
            errors = []
            if source.storage not in ('alias', 'extern', 'register'):
                errors.append(M2ValidationError(
                    f'Cannot define an alias to {expression.ref.text} because it has storage class {source.storage}',
                    'InvalidAliasSource', location(expression)))
            if source.const and not alias.const:
                errors.append(M2ValidationError(
                    f'Cannot define a non-const alias to const item {expression.ref.text}',
                    'InvalidAliasConstness', location(expression)))
            if errors:
                errors[0].related_diagnostics.extend(errors[1:])
                raise errors[0]
            return
        if isinstance(expression, P.Slice_expressionContext):
            errors = []
            try:
                self.alias_source(alias, expression.expr)
            except M2ValidationError as error:
                errors.append(error)
            base = self.expression_type(expression.expr)
            count = base.width if base.integer else base.count
            for index in (expression.left, expression.right):
                if index is None:
                    continue
                try:
                    value = self.evaluate(index, True)
                except M2ValidationError as error:
                    errors.append(error)
                    continue
                if value is not None and count is not None and (value < 0 or value >= count):
                    relation = f'{value} < 0' if value < 0 else f'{value} >= {count}'
                    # Both range endpoints can independently be outside bounds.
                    self.warning(index, 'index-out-of-range', f'Index out of range ({relation})')
            if errors:
                errors[0].related_diagnostics.extend(errors[1:])
                raise errors[0]
            return
        self.error(expression, 'InvalidAliasSource',
                   'Alias source must be an identifier followed by any number of index or range accesses')

    def check_conversion(self, ctx, source, target, issue):
        # If an enum's common type is indeterminate, an independently known
        # member value must still fit its integer target.
        node = reference(ctx)
        symbol = None if node is None else self.lookup(node.ref.text)
        if source == UNKNOWN and target.integer and symbol is not None and symbol.storage == 'enum':
            value = self.evaluate(ctx)
            if value is not None and not holds_value(target, value):
                self.error(ctx, issue, f'Enum constant value {value} cannot be represented by {target}')
        source_size, target_size = self.bit_size(source), self.bit_size(target)
        if source_size is None or target_size is None or source_size < 0 or target_size < 0:
            return  # Release conversions involving error types avoid cascades.
        if convertible(source, target):
            return
        value = self.evaluate(ctx)
        if value is not None and holds_value(target, value):
            logger.info('Assignment is allowed despite type incompatibility, because the right hand side is a constant [com.minres.coredsl.ValidConstantAssignment]')
            return
        if value is None and self.partial:
            # Do not exempt known locals: only truly unresolved parameter values
            # may receive the release's partial-analysis exception.
            refs = self.parameter_references(ctx)
            if refs and any(symbol.value_expression is None for symbol in refs):
                return
        self.error(ctx, issue, f'Cannot implicitly convert {source} to {target}')

    def parameter_references(self, ctx):
        result = []
        node = reference(ctx)
        if node is not None:
            symbol = self.lookup(node.ref.text)
            if symbol is not None and symbol.storage == 'param':
                result.append(symbol)
        for child in getattr(ctx, 'children', None) or []:
            if hasattr(child, 'children'):
                result.extend(self.parameter_references(child))
        return result

    def function_signature(self, function):
        if function not in self.signatures:
            # A caller's local variables must not change the callee's signature.
            scopes = self.scopes
            self.scopes = []
            try:
                parameters = [] if function.params is None else function.params.params
                types = [self.specified_type(param.type_) if param.decl is None else
                         self.symbol_type(Symbol(declaration=param, declarator=param.decl))
                         for param in parameters]
                self.signatures[function] = self.specified_type(function.type_), types
            finally:
                self.scopes = scopes
        return self.signatures[function]

    def visitFunction_definition(self, ctx):
        _, types = self.function_signature(ctx)
        previous = self.function
        self.function = ctx
        parameters = {} if ctx.params is None else {
            param.decl.name.text: Symbol(ty=ty)
            for param, ty in zip(ctx.params.params, types) if param.decl is not None}
        self.scopes.append(parameters)
        try:
            for attribute in ctx.attributes:
                self.visit(attribute)
            if ctx.behavior is not None:
                errors = []
                try:
                    self.visit(ctx.behavior)
                except M2ValidationError as error:
                    errors.append(error)
                if ctx.type_.getText() != 'void' and not return_terminated(ctx.behavior):
                    errors.append(M2ValidationError(
                        'Not all execution paths return a value',
                        'MissingReturnStatement', location(ctx)))
                if errors:
                    errors[0].related_diagnostics.extend(errors[1:])
                    raise errors[0]
        finally:
            self.scopes.pop()
            self.function = previous

    def visitBlock(self, ctx):
        self.scopes.append({})
        errors = []
        try:
            for item in ctx.items:
                try:
                    self.visit(item)
                except M2ValidationError as error:
                    errors.append(error)
        finally:
            self.scopes.pop()
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def visitDeclaration(self, ctx):
        errors = []
        if ctx.type_.getText() == 'void':
            errors.append(M2ValidationError(
                'Declarations may not use type void', 'VoidDeclaration', location(ctx.type_)))
        seen = set()
        for qualifier in ctx.qualifiers:
            name = qualifier.getText()
            if name in seen:
                errors.append(M2ValidationError(
                    'Duplicate qualifier ' + name, 'DuplicateQualifier', location(qualifier)))
            seen.add(name)
        if len(ctx.storage) > 1:
            errors.append(M2ValidationError(
                'A declaration may not specify more than one storage class',
                'MultipleStorageClassSpecifiers', location(ctx.storage[1])))
        alias = ctx.type_.ptr is not None and ctx.type_.ptr.text == '&'
        for declarator in ctx.declarations:
            symbol = Symbol(ctx, declarator, storage='alias' if alias else 'local', const=any(q.getText() == 'const' for q in ctx.qualifiers))
            try:
                target = self.symbol_type(symbol)
                if declarator.init is not None and not alias:
                    self.validate_initializer(declarator.init, target)
            except M2ValidationError as error:
                errors.append(error)
                if symbol.ty is None:
                    symbol.ty = UNKNOWN
            if (symbol.const and declarator.init is None
                    and not any(item.getText() in ('extern', 'register') for item in ctx.storage)):
                errors.append(M2ValidationError(
                    'An identifier declared as const must be initialized',
                    'UninitializedConstant', location(declarator)))
            if alias:
                errors.append(M2ValidationError(
                    'A local variable may not be declared as alias',
                    'AliasLocalVariable', location(declarator)))
                if declarator.init is None:
                    errors.append(M2ValidationError(
                        'An identifier declared as alias must be initialized',
                        'UninitializedAlias', location(declarator)))
                elif declarator.init.expr is None:
                    errors.append(M2ValidationError(
                        'An identifier declared as alias must not use a list initializer',
                        'InvalidListInitializer', location(declarator)))
                else:
                    symbol.value_expression = declarator.init.expr
                    try:
                        self.validate_alias(symbol)
                    except M2ValidationError as error:
                        errors.append(error)
            # An invalid initializer does not erase a declaration or its type.
            # Keep binding after initializer analysis to preserve lexical lookup.
            self.scopes[-1][declarator.name.text] = symbol
        if ctx.storage:
            errors.append(M2ValidationError(
                'Storage class specifiers are only allowed on ISA level declarations',
                'StorageClassSpecifierOnLocalVariable', location(ctx)))
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def visitInstruction(self, ctx):
        fields = {}
        for entry in ctx.encoding:
            if isinstance(entry, P.Bit_fieldContext):
                highest = max(integer_literal(entry.left.getText())[0], integer_literal(entry.right.getText())[0])
                old = fields.get(entry.name.text)
                fields[entry.name.text] = Symbol(ty=integer(max(highest + 1, 0 if old is None else old.ty.width)), storage='encoding')
        self.scopes.append(fields)
        try:
            for attribute in ctx.attributes:
                self.visit(attribute)
            self.visit(ctx.behavior)
        finally:
            self.scopes.pop()

    def visitAttribute(self, ctx):
        for expression in ctx.params:
            self.expression_type(expression)
        if ctx.name.text != 'expected_encoding_size' or not ctx.params:
            return
        if constant_value(ctx.params[0]) is not None:
            return  # Already checked by the structural source pass.
        expected = self.evaluate(ctx.params[0], True)
        if expected is None:
            return
        owner = ctx.parentCtx
        instructions = [owner] if isinstance(owner, P.InstructionContext) else [
            instruction for instruction in owner.instructions
            if not any(attribute.name.text == ctx.name.text for attribute in instruction.attributes)]
        for instruction in instructions:
            actual = SourceValidator._encoding_size(self, instruction)
            if expected != actual:
                self.warning(instruction, 'unexpected-instruction-size',
                             f'Expected an encoding size of {expected}, but got {actual}')

    def visitExpression_statement(self, ctx):
        self.check_statement_expression(ctx.expr, ctx)

    def check_statement_expression(self, expression, report_context):
        error = None
        try:
            self.expression_type(expression)
        except M2ValidationError as caught:
            error = caught
        if not statement_expression(expression):
            diagnostic = M2ValidationError(
                'Invalid expression in expression statement',
                'InvalidStatementExpression', location(report_context))
            if error is None:
                error = diagnostic
            else:
                error.related_diagnostics.append(diagnostic)
        if error is not None:
            raise error

    def visitProcedure_call(self, ctx):
        self.call_type(ctx)

    def visitReturn_statement(self, ctx):
        errors = []
        target = None if self.function is None else self.function_signature(self.function)[0]
        source = None if ctx.expr is None else self.recover_expression_type(ctx.expr, errors)
        if self.function is None:
            errors.append(M2ValidationError('Return statement is only valid in a function',
                                            'ReturnStatementOutsideFunction', location(ctx)))
        elif target == VOID and ctx.expr is not None:
            errors.append(M2ValidationError('Void functions may not return a value',
                                            'ReturnWithValueInVoidFunction', location(ctx)))
        elif target != VOID and ctx.expr is None:
            errors.append(M2ValidationError('Non-void functions must return a value',
                                            'ReturnWithoutValueInNonVoidFunction', location(ctx)))
        elif source is not None:
            source_size, target_size = self.bit_size(source), self.bit_size(target)
            # Error/incomplete types suppress conversion errors. Unlike ordinary
            # assignments, return conversion has no constant-value exception.
            if (source_size is not None and source_size >= 0
                    and target_size is not None and target_size >= 0
                    and not convertible(source, target)):
                errors.append(M2ValidationError(f'Cannot convert from {source} to {target}',
                                                'ReturnTypeNotConvertible', location(ctx)))
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def scalar_condition(self, expression):
        errors = []
        ty = self.recover_expression_type(expression, errors)
        size = self.bit_size(ty)
        if size is not None and size >= 0 and not ty.scalar:
            errors.append(M2ValidationError(
                f'The condition must be a scalar type, but was {ty}',
                'NonScalarCondition', location(expression)))
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def check_statement_parts(self, parts):
        errors = []
        for action, child in parts:
            try:
                action(child)
            except M2ValidationError as error:
                errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def visitIf_statement(self, ctx):
        # Else-if chains represent nested release IfStatements: visit each
        # condition and its then branch before continuing into its else branch.
        parts = []
        for condition, statement in zip(ctx.cond, ctx.stmt):
            parts.extend(((self.scalar_condition, condition), (self.visit, statement)))
        if len(ctx.stmt) > len(ctx.cond):
            parts.append((self.visit, ctx.stmt[-1]))
        self.check_statement_parts(parts)

    def visitWhile_statement(self, ctx):
        self.check_statement_parts(((self.scalar_condition, ctx.cond),
                                    (self.visit, ctx.stmt)))

    visitDo_statement = visitWhile_statement

    def visitFor_statement(self, ctx):
        self.scopes.append({})
        errors = []
        try:
            for child in (ctx.cond, ctx.stmt):
                try:
                    self.visit(child)
                except M2ValidationError as error:
                    errors.append(error)
        finally:
            self.scopes.pop()
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def visitFor_condition(self, ctx):
        errors = []

        def check(action, *arguments):
            try:
                action(*arguments)
            except M2ValidationError as error:
                errors.append(error)

        if ctx.start_decl is not None:
            check(self.visit, ctx.start_decl)
        if ctx.start_expr is not None:
            check(self.check_statement_expression, ctx.start_expr, ctx.start_expr)
        if ctx.end_expr is not None:
            check(self.scalar_condition, ctx.end_expr)
        for expression in ctx.loop_exprs:
            check(self.check_statement_expression, expression, expression)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def visitSwitch_statement(self, ctx):
        errors = []
        ty = self.recover_expression_type(ctx.cond, errors)
        if not ty.integer:
            errors.append(M2ValidationError('The switch condition must be an integer expression',
                                            'SwitchConditionTypeInvalid', location(ctx)))
        seen = set()
        default_found = False
        size = self.bit_size(ty)
        condition_error = size is None or size < 0

        def check_label(label):
            nonlocal default_found
            if label.const_expr is None:
                if default_found:
                    errors.append(M2ValidationError('Multiple default sections',
                                                    'SwitchMultipleDefaultSections', location(label)))
                default_found = True
            else:
                try:
                    value = self.evaluate(label.const_expr, True)
                except M2ValidationError as error:
                    errors.append(error)
                    return
                if value is not None:
                    if value in seen:
                        errors.append(M2ValidationError(f'Multiple case sections with condition {value}',
                                                        'SwitchDuplicateCaseSection', location(label)))
                    seen.add(value)
                    if not condition_error and not holds_value(ty, value):
                        errors.append(M2ValidationError(
                            f'The value {value} can not be represented by condition type {ty}',
                            'SwitchCaseConditionOutOfRange', location(label)))

        # Grouped labels represent empty sections followed by a section body.
        for group in ctx.items:
            for label in group.labels:
                check_label(label)
            for statement in group.statements:
                try:
                    self.visit(statement)
                except M2ValidationError as error:
                    errors.append(error)
        for label in ctx.switch_label():
            check_label(label)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    @staticmethod
    def bit_size(ty):
        if ty.kind in ('struct', 'union'):
            return ty.width
        if ty.kind == 'enum':
            return ty.width
        if ty.integer:
            return ty.width
        if ty == VOID:
            return 0
        if ty.kind in ('array', 'address'):
            element = SemanticValidator.bit_size(ty.element)
            if element is None or ty.count is None:
                return None
            # Release address-space size is its element width, not its capacity.
            return element if ty.kind == 'address' else element * ty.count
        return None

    def intrinsic_value(self, ctx, constant=False, argument_type=None):
        name = ctx.ref.text
        if name in ('offsetof', 'bitoffsetof'):
            if constant:
                self.error(ctx, 'InvalidConstantExpressionNode',
                           'Intrinsic function ' + name + ' is not allowed in constant expression')
            self.error(ctx, 'UnknownIntrinsicFunction', 'Unknown intrinsic function ' + name)
        expected = 0 if name == '__encoding_size' else 1
        if len(ctx.args) != expected:
            count = 'no arguments' if expected == 0 else 'exactly one argument'
            self.error(ctx, 'InvalidArgumentCount', name + ' expects ' + count)
        if name == '__encoding_size':
            node = ctx
            while node is not None:
                parent = node.parentCtx
                if isinstance(parent, P.Always_blockContext) and node is parent.behavior:
                    return None  # Runtime instruction width in an always block.
                if isinstance(parent, P.InstructionContext) and node is parent.behavior:
                    return SourceValidator._encoding_size(self, parent)
                node = parent
            self.error(ctx, 'InvalidIntrinsicFunction',
                       name + ' can only be used within an instruction behavior')
        argument = ctx.args[0]
        if argument.type_ is not None:
            ty = self.specified_type(argument.type_) if argument_type is None else argument_type
        else:
            target = reference(argument.expr)
            symbol = None if target is None else self.lookup(target.ref.text)
            if symbol is not None and symbol.function is None:
                # Release EntityReference queries use tryGetDeclaratorType:
                # the declaration's specified type, without array dimensions.
                # Parenthesized/indexed expressions take the expression path.
                if symbol.declaration is not None:
                    ty = self.specified_type(symbol.declaration.type_)
                else:
                    # Model lowering supplies resolved symbols without an AST
                    # declaration. Remove only declarator-derived dimensions.
                    ty = self.symbol_type(symbol)
                    while ty.kind in ('array', 'address'):
                        ty = ty.element
            else:
                if self.elaborating:
                    self.error(ctx, 'UnsupportedSizeOfDuringElaboration',
                               'Size of expression can not be determined during elaboration')
                ty = self.expression_type(argument.expr) if argument_type is None else argument_type
        size = self.bit_size(ty)
        if size is None:
            return None
        if name == 'sizeof':
            if size % 8:
                self.warning(ctx, 'size-of-not-exact',
                             f'The size ({size} bits) is not an exact multiple of 8')
            return (size + 7) // 8
        return size

    def intrinsic_type(self, ctx):
        # The analyzer visits every argument, even with an invalid arity/name.
        ctx._diagnostic_result_type = UNKNOWN
        errors, argument_types = [], []
        for argument in ctx.args:
            if argument.type_ is not None:
                try:
                    ty = self.specified_type(argument.type_)
                except M2ValidationError as error:
                    errors.append(error)
                    ty = UNKNOWN
            else:
                ty = self.recover_expression_type(argument.expr, errors)
            argument_types.append(ty)
        try:
            value = self.intrinsic_value(
                ctx, argument_type=argument_types[0] if len(argument_types) == 1 else None)
        except M2ValidationError as error:
            errors.append(error)
            value = None
        if value is None:
            # __encoding_size in always blocks has the release's fixed type.
            result = integer(16) if ctx.ref.text == '__encoding_size' and not errors else UNKNOWN
        else:
            result = integer(max(1, value.bit_length()))
        ctx._diagnostic_result_type = result
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]
        return result

    def cast_type(self, ctx):
        """Retain explicit target types and independent errors after child failures."""
        ctx._diagnostic_result_type = UNKNOWN
        errors = []
        source = self.recover_expression_type(ctx.right, errors)
        source_size = self.bit_size(source)
        source_error = source_size is None or source_size < 0
        if ctx.type_ is not None:
            try:
                result = self.specified_type(ctx.type_)
            except M2ValidationError as error:
                errors.append(error)
                result = UNKNOWN
            target_size = self.bit_size(result)
            target_error = target_size is None or target_size < 0
            if not source_error and not target_error and not (source.integer and result.integer):
                errors.append(M2ValidationError(f'Cannot cast from {source} to {result}',
                                               'InvalidCast', location(ctx)))
        elif source_error:
            # Release signedness casts propagate the operand's error type.
            result = source
        elif source.integer:
            result = integer(source.width, ctx.sign.getText() == 'signed')
        else:
            result = UNKNOWN
            errors.append(M2ValidationError('Cannot apply signedness cast to non-integer value',
                                           'InvalidCast', location(ctx)))
        if not source_error and result == source:
            self.warning(ctx, 'identity-cast', 'Identity cast does nothing')
        ctx._diagnostic_result_type = result
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]
        return result

    def call_type(self, ctx):
        ctx._diagnostic_result_type = UNKNOWN
        name = ctx.ref.text
        symbol = self.lookup(name)
        if symbol is None:
            self.error(ctx, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking',
                       f"Couldn't resolve reference to NamedEntity '{name}'.")
        if symbol.function is None:
            self.error(ctx, 'InvalidFunction', 'Expected a function name')
        function = symbol.function
        parameters = [] if function.params is None else function.params.params
        return_type, parameter_types = self.function_signature(function)
        # The release retains the declared result even when call validation fails.
        ctx._diagnostic_result_type = return_type
        if len(parameters) != len(ctx.args):
            # Xtend's mapped argument list is lazy: size does not visit children.
            self.error(ctx, 'InvalidArgumentCount', f'Incorrect argument count. Expected {len(parameters)}, got {len(ctx.args)}')
        errors = []
        for argument, target in zip(ctx.args, parameter_types):
            source = self.recover_expression_type(argument, errors)
            try:
                self.check_conversion(argument, source, target, 'InvalidArgumentType')
            except M2ValidationError as error:
                errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]
        return return_type

    def recover_expression_type(self, expression, errors):
        try:
            return self.expression_type(expression)
        except M2ValidationError as error:
            errors.append(error)
            while isinstance(expression, (P.Primary_expressionContext,
                                          P.Parens_expressionContext)):
                expression = (expression.primary()
                              if isinstance(expression, P.Primary_expressionContext)
                              else expression.expr)
            return getattr(expression, '_diagnostic_result_type', UNKNOWN)

    def expression_type(self, ctx):
        if isinstance(ctx, P.Primary_expressionContext):
            return self.expression_type(ctx.primary())
        if isinstance(ctx, P.Parens_expressionContext):
            return self.expression_type(ctx.expr)
        if isinstance(ctx, P.Constant_expressionContext):
            return self.expression_type(ctx.const_expr)
        if isinstance(ctx, P.ConstantContext):
            return self.expression_type(ctx.getChild(0))
        if isinstance(ctx, P.Integer_constantContext):
            _, width, signed = integer_literal(ctx.value.text)
            return integer(width, signed)
        if isinstance(ctx, P.Bool_constantContext):
            return BOOL
        if isinstance(ctx, P.Reference_expressionContext):
            symbol = self.lookup(ctx.ref.text)
            if symbol is None:
                self.error(ctx, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking',
                           f"Couldn't resolve reference to NamedEntity '{ctx.ref.text}'.")
            if symbol.function is not None:
                self.error(ctx, 'ReferenceToFunction', 'Function used like a variable')
            return self.symbol_type(symbol)
        if isinstance(ctx, P.Intrinsic_expressionContext):
            return self.intrinsic_type(ctx)
        if isinstance(ctx, P.Deref_expressionContext):
            base = self.expression_type(ctx.expr)
            if base.kind in ('struct', 'union'):
                for member in self.composite_members[base.identity]:
                    if member.declarator.name.text == ctx.ref.text:
                        return self.symbol_type(member)
            if base != UNKNOWN:
                # Release member scoping fails before its analyzer reaches
                # InvalidMemberAccessTarget for a known non-composite base.
                self.error(ctx, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking',
                           f"Couldn't resolve reference to Declarator '{ctx.ref.text}'.")
            return UNKNOWN  # Composite member provider remains deferred.
        if isinstance(ctx, P.Method_callContext):
            return self.call_type(ctx)
        if isinstance(ctx, P.Assignment_expressionContext):
            ctx._diagnostic_result_type = UNKNOWN
            errors = []
            target = self.recover_expression_type(ctx.left, errors)
            source = self.recover_expression_type(ctx.right, errors)
            try:
                self.assignment_target(ctx.left)
            except M2ValidationError as error:
                errors.append(error)
            try:
                self.check_conversion(ctx.right, source, target, 'InvalidAssignmentType')
            except M2ValidationError as error:
                errors.append(error)
            if ctx.bop.text != '=' and not self.partial and not (source.integer and target.integer):
                errors.append(M2ValidationError(
                    f'Cannot combine {source} and {target} with the {ctx.bop.text[0]} operator',
                    'InvalidOperationType', location(ctx)))
            ctx._diagnostic_result_type = target
            if errors:
                errors[0].related_diagnostics.extend(errors[1:])
                raise errors[0]
            return target
        if isinstance(ctx, P.Cast_expressionContext):
            return self.cast_type(ctx)
        if isinstance(ctx, P.Conditional_expressionContext):
            return self.conditional_type(ctx)
        if isinstance(ctx, P.Binary_expressionContext):
            ctx._diagnostic_result_type = UNKNOWN
            errors = []
            left = self.recover_expression_type(ctx.left, errors)
            right = self.recover_expression_type(ctx.right, errors)
            try:
                result = self.binary_type(ctx, left, right)
            except M2ValidationError as error:
                errors.append(error)
                # The release preserves bool for logical/comparison operators,
                # even when their known operands have incompatible types.
                result = BOOL if ctx.bop.text in ('&&', '||', '==', '!=', '<', '<=', '>', '>=') else UNKNOWN
            ctx._diagnostic_result_type = result
            if errors:
                errors[0].related_diagnostics.extend(errors[1:])
                raise errors[0]
            return result
        if isinstance(ctx, P.Concat_expressionContext):
            left, right = self.expression_type(ctx.left), self.expression_type(ctx.right)
            return integer(left.width + right.width) if left.integer and right.integer else UNKNOWN
        if isinstance(ctx, P.Slice_expressionContext):
            return self.index_type(ctx)
        if isinstance(ctx, P.Prefix_expressionContext):
            return self.unary_type(ctx, ctx.right, ctx.prefix.text)
        if isinstance(ctx, (P.Preinc_expressionContext, P.Postinc_expressionContext)):
            operand = ctx.right if isinstance(ctx, P.Preinc_expressionContext) else ctx.left
            return self.unary_type(ctx, operand, ctx.op.text, modifying=True)
        return UNKNOWN

    def unary_type(self, ctx, operand, op, modifying=False):
        ctx._diagnostic_result_type = UNKNOWN
        errors = []
        ty = self.recover_expression_type(operand, errors)
        size = self.bit_size(ty)
        known = size is not None and size >= 0
        if modifying:
            try:
                self.assignment_target(operand)
            except M2ValidationError as error:
                errors.append(error)
        valid = ty.scalar if op == '!' else ty.integer
        if known and not valid:
            message = ('Logical not is only valid on scalar types' if op == '!' else
                       'Increment and decrement operators are only valid on integer types'
                       if modifying else 'Unary operators are only valid on integer types')
            errors.append(M2ValidationError(message, 'InvalidOperationType', location(ctx)))
            result = BOOL if op == '!' else UNKNOWN
        elif op == '!':
            result = UNKNOWN if self.partial and ty == UNKNOWN and not errors else BOOL
        elif op == '-':
            result = integer(ty.width + 1, True) if ty.integer else UNKNOWN
        else:
            result = ty
        ctx._diagnostic_result_type = result
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]
        return result

    def conditional_type(self, ctx):
        ctx._diagnostic_result_type = UNKNOWN
        errors = []
        condition = self.recover_expression_type(ctx.cond, errors)
        left = self.recover_expression_type(ctx.then_expr, errors)
        right = self.recover_expression_type(ctx.else_expr, errors)
        size = self.bit_size(condition)
        if size is not None and size >= 0 and not condition.scalar:
            errors.append(M2ValidationError(
                f'The condition must be a scalar type, but was {condition}',
                'NonScalarCondition', location(ctx.cond)))
        left_size, right_size = self.bit_size(left), self.bit_size(right)
        if left_size is None or right_size is None or left_size < 0 or right_size < 0:
            result = UNKNOWN
        elif left == right:
            result = left
        elif left.integer and right.integer:
            result = common_integer(left, right)
        else:
            errors.append(M2ValidationError(
                f'Incompatible option types: {left} and {right}',
                'IncompatibleOptionTypes', location(ctx)))
            result = UNKNOWN
        ctx._diagnostic_result_type = result
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]
        return result

    def assignment_target(self, ctx):
        if isinstance(ctx, P.Deref_expressionContext):
            errors = []
            try:
                self.assignment_target(ctx.expr)
            except M2ValidationError as error:
                errors.append(error)
            base = self.expression_type(ctx.expr)
            if base.kind in ('struct', 'union'):
                for member in self.composite_members[base.identity]:
                    if member.declarator.name.text == ctx.ref.text:
                        if member.const:
                            errors.append(M2ValidationError(
                                f"Cannot assign constant field '{ctx.ref.text}'",
                                'InvalidAssignmentTarget', location(ctx)))
                        break  # First declared member controls lookup.
            if errors:
                errors[0].related_diagnostics.extend(errors[1:])
                raise errors[0]
            return
        if isinstance(ctx, P.Primary_expressionContext):
            return self.assignment_target(ctx.primary())
        if isinstance(ctx, P.Slice_expressionContext):
            return self.assignment_target(ctx.expr)
        if isinstance(ctx, P.Reference_expressionContext):
            symbol = self.lookup(ctx.ref.text)
            if symbol is not None:
                if symbol.function is not None or symbol.const or symbol.storage in ('encoding', 'param'):
                    self.error(ctx, 'InvalidAssignmentTarget', 'Cannot assign to constant, function or encoding parameter')
            return
        self.error(ctx, 'InvalidAssignmentTarget', 'Invalid assignment target')

    def binary_type(self, ctx, left, right):
        if UNKNOWN in (left, right):
            return UNKNOWN
        op = ctx.bop.text
        if op in ('&&', '||'):
            if not (left.scalar and right.scalar):
                self.error(ctx, 'InvalidOperationType', 'Logical operators are only valid on scalar types')
            return BOOL
        if op in ('==', '!=') and left == right and left.kind != 'address':
            return BOOL
        if not (left.integer and right.integer):
            self.error(ctx, 'InvalidOperationType', 'Operation is only valid on integer types')
        if op in ('==', '!=', '<', '<=', '>', '>='):
            return BOOL
        if op in ('<<', '>>'):
            shift = self.evaluate(ctx.right)
            if shift is not None and shift >= left.width:
                self.warning(ctx, 'shift-overflow', 'Shift expression always evaluates to zero; Please cast the left operand to a wider type before shifting')
            return left
        signed = left.signed or right.signed
        if op in ('&', '|', '^'):
            return integer(max(left.width, right.width), signed)
        if op in ('+', '-'):
            width = (max(left.width, right.width) if left.signed == right.signed else
                     max(left.width + int(right.signed), right.width + int(left.signed))) + 1
            return integer(width, signed or op == '-')
        if op == '*':
            return integer(left.width + right.width, signed)
        if op == '/':
            return integer(left.width + int(right.signed), signed)
        if op == '%':
            width = min(left.width, right.width) if left.signed == right.signed else (
                min(left.width, right.width + 1) if left.signed else min(left.width, right.width - 1))
            return integer(width, left.signed)
        return UNKNOWN

    def index_type(self, ctx):
        ctx._diagnostic_result_type = UNKNOWN
        errors = []

        def report(issue, message):
            errors.append(M2ValidationError(message, issue, location(ctx)))

        def finish(result):
            ctx._diagnostic_result_type = result
            if errors:
                errors[0].related_diagnostics.extend(errors[1:])
                raise errors[0]
            return result

        def child_type(child):
            return self.recover_expression_type(child, errors)

        base = child_type(ctx.expr)
        index = child_type(ctx.left)
        if base == UNKNOWN:
            element, count = UNKNOWN, None
        elif base.integer:
            element, count = BOOL, base.width
        elif base.kind in ('array', 'address'):
            element, count = base.element, base.count
        else:
            report('NonIndexableExpression', f'Cannot index into {base}')
            element, count = UNKNOWN, None
        index_bits = self.bit_size(index)
        index_error = index_bits is None or index_bits < 0
        if not index_error and not index.integer:
            report('InvalidIndexType', 'Index must have an integer type')
        if ctx.right is None:
            return finish(element)
        end = child_type(ctx.right)
        if not index_error and not end.integer:
            report('InvalidIndexType', 'Index must have an integer type')
        start_value, end_value = self.evaluate(ctx.left), self.evaluate(ctx.right)
        size = None
        start_ref, end_ref = reference(ctx.left), reference(ctx.right)
        if start_ref is not None and end_ref is not None:
            if self.lookup(start_ref.ref.text) is self.lookup(end_ref.ref.text) and self.lookup(start_ref.ref.text) is not None:
                size = 1
        elif start_ref is not None or end_ref is not None:
            ref = start_ref or end_ref
            other = ctx.right if start_ref is not None else ctx.left
            if isinstance(other, P.Binary_expressionContext) and other.bop.text in ('+', '-'):
                other_ref = reference(other.left)
                if other_ref is not None and self.lookup(other_ref.ref.text) is self.lookup(ref.ref.text):
                    difference = self.evaluate(other.right)
                    if difference is not None:
                        size = abs(difference) + 1
        elif start_value is not None and end_value is not None:
            size = abs(end_value - start_value) + 1
        if size is None:
            if not self.partial:
                report('InvalidRangePattern', 'Invalid range pattern')
            return finish(UNKNOWN)
        if not element.integer:
            return finish(UNKNOWN)
        width = size * element.width
        if width > 2147483647:
            report('InvalidIntegerTypeSize', 'The combined size of the selected elements must not exceed Integer.MAX_VALUE')
            return finish(UNKNOWN)
        return finish(integer(width))


def invalid_elaboration_summaries(tree, parameter_values=None):
    """Collect proven invalid values/types without replacing the primary error.

    Unknown and indeterminate results are deliberately distinct from exceptions
    proving an invalid elaboration. Warnings are disabled during this collection.
    """
    from ...diagnostics import M2ValidationError
    invalid_constants = {'com.minres.coredsl.' + issue for issue in (
        'DivisionByZero', 'InvalidConstantExpressionNode',
        'InvalidConstantExpressionIdentifier', 'UnsupportedLanguageFeature')}
    invalid_types = invalid_constants | {'com.minres.coredsl.InvalidIntegerTypeSize'}
    summaries = []
    primary_errors, seen_errors = [], set()
    def record_error(error):
        info = error.line_info
        key = (error.issue_code, error.args[0],
               None if info is None else (info.file_path, info.start_chr, info.stop_chr))
        if key not in seen_errors:
            seen_errors.add(key)
            primary_errors.append(error)
    def incomplete_type(ty):
        if ty.kind in ('integer', 'struct', 'union', 'enum'):
            return ty.width is None
        if ty.kind in ('array', 'address'):
            return ty.count is None or incomplete_type(ty.element)
        return False  # Unsupported providers are not proven incomplete types.
    def unresolved_source_type(validator, symbol, active):
        if symbol.declaration is None or symbol.declaration.type_.ptr is not None:
            return False
        specified = symbol.declaration.type_.type_
        if isinstance(specified, P.Integer_typeContext):
            return specified.size is not None and validator.evaluate(specified.size, True) is None
        if isinstance(specified, P.Enum_referenceContext):
            definition = validator.enum_definitions.get(specified.name.text)
            return definition is not None and validator.enum_type(definition) == UNKNOWN
        if isinstance(specified, P.Composite_referenceContext):
            definition = validator.composite_definitions.get((specified.type_.getText(), specified.name.text))
            if definition is None:
                return False
            identity = id(definition)
            if identity in active:
                return True
            return any(unresolved_source_type(validator, member, active | {identity})
                       for member in validator.composite_members[identity])
        return False
    for root in tree.definitions:
        if not isinstance(root, P.Core_defContext):
            continue
        validator = SemanticValidator(tree, None, parameter_values)
        try:
            validator.build_symbols(validator.contributors(root))
        except M2ValidationError:
            continue  # A separate linking/duplicate failure prevents elaboration.
        validator.elaborating = True
        for name, value in (parameter_values or {}).items():
            symbol = validator.symbols.get(name)
            if symbol is not None and symbol.storage == 'param':
                symbol.known_value = value
        values, types, incomplete_arrays, array_diagnostics = [], [], [], []
        incomplete_values = []
        for name, symbol in validator.symbols.items():
            if symbol.function is not None:
                continue
            if (symbol.declaration is not None and len(symbol.declarator.size) > 1
                    and any(item.getText() in ('extern', 'register')
                            for item in symbol.declaration.storage)):
                record_error(M2ValidationError(
                    'Multidimensional address spaces are not allowed',
                    'MultidimensionalAddressSpace', location(symbol.declarator.size[-2])))
            value_expression = symbol.value_expression
            # Release summaries contain explicit enum assignments only.
            # Automatic members are derived, but have no assignment entry.
            if (symbol.storage in ('param', 'enum') and symbol.known_value is None
                    and value_expression is not None):
                try:
                    if validator.evaluate(value_expression, True) is None:
                        incomplete_values.append(name)
                except M2ValidationError as error:
                    if error.issue_code in invalid_constants:
                        record_error(error)
                        values.append(name)
            if symbol.storage == 'enum':
                continue  # Enum member failures are value errors, not state type errors.
            try:
                ty = validator.symbol_type(symbol)
            except M2ValidationError as error:
                if error.issue_code in invalid_types | {'com.minres.coredsl.InvalidArraySize'}:
                    record_error(error)
                if (symbol.declaration is not None and symbol.declarator.size
                        and error.issue_code in invalid_constants | {'com.minres.coredsl.InvalidArraySize'}):
                    try:
                        validator.specified_type(symbol.declaration.type_)
                    except M2ValidationError:
                        pass  # The element type is itself invalid.
                    else:
                        incomplete_arrays.append(name)
                        for dimension in symbol.declarator.size:
                            try:
                                size = validator.evaluate(dimension, True)
                                if size is not None and size < 0:
                                    record_error(M2ValidationError(
                                        'Negative array size is invalid', 'InvalidArraySize', location(dimension)))
                            except M2ValidationError as dimension_error:
                                if dimension_error.issue_code in invalid_constants:
                                    record_error(dimension_error)
                                    array_diagnostics.append(M2ValidationError(
                                        'Unable to determine array size', 'InvalidArraySize', location(dimension)))
                        continue
                named_type_reference = (symbol.declaration is not None and isinstance(
                    symbol.declaration.type_.type_, (P.Composite_referenceContext, P.Enum_referenceContext)))
                if error.issue_code in invalid_types and not named_type_reference:
                    types.append(name)
            else:
                if incomplete_type(ty) or unresolved_source_type(validator, symbol, set()):
                    incomplete_arrays.append(name)
                if symbol.declaration is not None:
                    for dimension in symbol.declarator.size:
                        if validator.evaluate(dimension, True) is None:
                            array_diagnostics.append(M2ValidationError(
                                'Unable to determine array size', 'InvalidArraySize', location(dimension)))
        if incomplete_values:
            summaries.append(M2ValidationError(
                'The values of the following state elements could not be determined because they depend on other indeterminable values: '
                + ', '.join(incomplete_values), 'IndeterminableIsaStateElementValue', location(root)))
        if values:
            summaries.append(M2ValidationError(
                'The values of the following state elements could not be determined: ' + ', '.join(values),
                'InvalidIsaStateElementValue', location(root)))
        if incomplete_arrays:
            summaries.append(M2ValidationError(
                'The types of the following state elements could not be determined because they depend on other indeterminable values: '
                + ', '.join(incomplete_arrays), 'IndeterminableIsaStateElementType', location(root)))
        if types:
            summaries.append(M2ValidationError(
                'The types of the following state elements could not be determined: ' + ', '.join(types),
                'InvalidIsaStateElementType', location(root)))
        summaries.extend(array_diagnostics)
    return primary_errors + summaries


def validate_semantics(tree, warnings_info, parameter_values=None):
    SemanticValidator(tree, warnings_info, parameter_values).visit(tree)
