

# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich


import logging
from copy import copy
from functools import singledispatchmethod

from m2isar.metamodel import arch, behav, type_info
from ...diagnostics import M2ValidationError
from ...metamodel.utils.ExprVisitor import ExprVisitor
from .constants import constant_value, holds_value, INDETERMINATE, range_size

logger = logging.getLogger("validate_behav")

# pylint: disable=unused-argument

class ValidateBehavVisitor(ExprVisitor):
    """Visitor to validate a metamodel."""

    @staticmethod
    def _validate_assignment_target(target, line_info):
        # Index accesses recurse to their base. Parentheses are not lvalues
        # in MINRES 2.0.21, even when they contain a writable reference.
        while isinstance(target, behav.SliceOperation):
            target = target.expr
        reference = getattr(target, 'reference', None)
        invalid = not isinstance(target, (behav.NamedReference, behav.IndexedReference))
        invalid = invalid or bool(getattr(target, 'grouped_base', False))
        invalid = invalid or isinstance(reference, (arch.Parameter, arch.BitFieldDescr, arch.Function))
        invalid = invalid or bool(getattr(reference, 'attributes', {}).get('const'))
        invalid = invalid or bool(getattr(reference, 'coredsl_const', False))
        if invalid:
            raise M2ValidationError('Invalid assignment target', 'InvalidAssignmentTarget', line_info)

    def _validate_statements(self, operation, context):
        locations = getattr(operation, '_stray_control_flow_locations', None)
        if locations is None:
            locations = [('break', location) for location in
                         (getattr(operation, '_stray_break_locations', None) or [])]
            locations.extend(('continue', location) for location in
                             (getattr(operation, '_stray_continue_locations', None) or []))
        errors = [M2ValidationError(f'Unexpected {kind} statement',
                                    'StrayControlFlowStatement', location)
                  for kind, location in locations]
        previous_breaks = getattr(self, '_preserved_breaks_active', False)
        previous_continues = getattr(self, '_preserved_continues_active', False)
        self._preserved_breaks_active = previous_breaks or any(kind == 'break' for kind, _ in locations)
        self._preserved_continues_active = previous_continues or any(kind == 'continue' for kind, _ in locations)
        try:
            for statement in operation.statements:
                try:
                    self.generate(statement, context)
                except M2ValidationError as error:
                    errors.append(error)
        finally:
            self._preserved_breaks_active = previous_breaks
            self._preserved_continues_active = previous_continues
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def _validate_children(self, children, context):
        errors = []
        for child in children:
            try:
                self.generate(child, context)
            except M2ValidationError as error:
                errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    _range_size = staticmethod(range_size)

    @staticmethod
    def _range_overflows(target_type, bounds):
        count = ValidateBehavVisitor._range_size(*bounds)
        if count is None:
            return False
        if isinstance(target_type, type_info.PrimitiveType) and target_type.kind.is_int:
            element_bits = 1
        elif isinstance(target_type, type_info.ArrayType):
            element = target_type.element_type
            element_bits = 1
            while isinstance(element, type_info.ArrayType):
                length = arch.get_const_or_val(element.length)
                if not isinstance(length, int) or length < 0:
                    return False
                element_bits *= length
                element = element.element_type
            if not isinstance(element, type_info.PrimitiveType) or not element.kind.is_int:
                return False
            width = arch.get_const_or_val(element.size)
            if not isinstance(width, int) or width <= 0:
                return False
            element_bits *= width
        else:
            return False
        return element_bits * count > 2147483647

    def _validate_access(self, children, indices, context, target_type=None, target_line_info=None, range_bounds=None):
        errors = []
        try:
            self._validate_children(children, context)
        except M2ValidationError as error:
            errors.append(error)
        if isinstance(target_type, type_info.PrimitiveType) and target_type.kind.is_void:
            errors.append(M2ValidationError('Cannot index into void', 'NonIndexableExpression',
                                            target_line_info))
        first_error = bool(indices) and self._has_invalid_type(indices[0])
        first_type = getattr(indices[0], 'ty', None) if indices else None
        while isinstance(first_type, type_info.ArrayType):
            length = arch.get_const_or_val(first_type.length)
            if not isinstance(length, int) or length < 0:
                first_error = True
                break
            first_type = first_type.element_type
        for position, index in enumerate(indices):
            ty = getattr(index, 'ty', None)
            if position:
                # The release deliberately guards the end index with the start type.
                invalid_index = not first_error and (
                    self._has_invalid_type(index) or isinstance(ty, type_info.ArrayType)
                    or isinstance(ty, type_info.PrimitiveType) and ty.kind.is_void)
            else:
                invalid_index = not self._has_invalid_type(index) and self._known_type_name(ty) is not None and (
                    isinstance(ty, type_info.ArrayType)
                    or isinstance(ty, type_info.PrimitiveType) and ty.kind.is_void)
            if invalid_index:
                errors.append(M2ValidationError('Index must have an integer type',
                                                'InvalidIndexType', index.line_info))
        if range_bounds is not None:
            def report_constant_error(node, error):
                errors.append(M2ValidationError('Division by zero', 'DivisionByZero',
                                                node.line_info or target_line_info))
            count = range_size(*range_bounds, on_error=report_constant_error)
            if count is None:
                if not getattr(context, 'partial', False):
                    errors.append(M2ValidationError('Invalid range pattern', 'InvalidRangePattern', target_line_info))
            elif self._range_overflows(target_type, range_bounds):
                errors.append(M2ValidationError(
                    'The combined size of the selected elements must not exceed Integer.MAX_VALUE',
                    'InvalidIntegerTypeSize', target_line_info))
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    @staticmethod
    def is_return_terminated(statement):
        if isinstance(statement, behav.Return):
            return True
        if isinstance(statement, behav.Operation):
            return bool(statement.statements) and ValidateBehavVisitor.is_return_terminated(statement.statements[-1])
        if isinstance(statement, behav.Conditional):
            return (bool(statement.conds) and len(statement.stmts) == len(statement.conds) + 1
                    and all(ValidateBehavVisitor.is_return_terminated(branch) for branch in statement.stmts))
        return False

    @staticmethod
    def _declared_size(value, line_info):
        try:
            return value if isinstance(value, int) else constant_value(value)
        except ZeroDivisionError:
            raise M2ValidationError('Division by zero', 'DivisionByZero', line_info)

    @staticmethod
    def _validate_declared_sizes(ty, line_info):
        while isinstance(ty, type_info.ArrayType):
            count = ValidateBehavVisitor._declared_size(ty.length, line_info)
            if isinstance(count, int) and count < 0:
                raise M2ValidationError('Negative array size is invalid', 'InvalidArraySize', line_info)
            ty = ty.element_type
        if isinstance(ty, type_info.PrimitiveType) and ty.kind.is_int:
            width = ValidateBehavVisitor._declared_size(ty.size, line_info)
            if isinstance(width, int):
                if width <= 0:
                    raise M2ValidationError('Integer type size must be greater than 0',
                                            'InvalidIntegerTypeSize', line_info)
                if width > 2147483647:
                    raise M2ValidationError('Integer type size must not exceed Integer.MAX_VALUE',
                                            'InvalidIntegerTypeSize', line_info)

    @staticmethod
    def _known_type_name(ty):
        if isinstance(ty, type_info.PrimitiveType):
            if ty.kind == type_info.TypeKind.VOID:
                return 'void'
            if ty.kind.is_int:
                width = arch.get_const_or_val(ty.size)
                if isinstance(width, int) and width > 0:
                    return f'{"signed" if ty.kind == type_info.TypeKind.INT else "unsigned"}<{width}>'
        if isinstance(ty, type_info.ArrayType):
            element = ValidateBehavVisitor._known_type_name(ty.element_type)
            count = arch.get_const_or_val(ty.length)
            if element is not None and isinstance(count, int) and count >= 0:
                return f'{element}[{count}]'
        return None

    @staticmethod
    def _has_invalid_type(expr):
        """Recognize invalid target/range results without mutating execution types."""
        invalid = ValidateBehavVisitor._has_invalid_type
        if isinstance(expr, behav.SliceOperation):
            ty = getattr(expr.expr, 'ty', None)
            return (isinstance(ty, type_info.PrimitiveType) and ty.kind.is_void
                    or invalid(expr.expr)
                    or expr.left is not expr.right
                    and (ValidateBehavVisitor._range_size(expr.left, expr.right) is None
                         or ValidateBehavVisitor._range_overflows(ty, (expr.left, expr.right))))
        if isinstance(expr, behav.IndexedReference):
            ty = getattr(expr.reference, 'ty', None)
            return (isinstance(ty, type_info.PrimitiveType) and ty.kind.is_void
                    or expr.right is not None
                    and (ValidateBehavVisitor._range_size(expr.index, expr.right) is None
                         or ValidateBehavVisitor._range_overflows(ty, (expr.index, expr.right))))
        if isinstance(expr, behav.Group):
            return invalid(expr.expr)
        if isinstance(expr, (behav.BinaryOperation, behav.ConcatOperation)):
            return invalid(expr.left) or invalid(expr.right)
        if isinstance(expr, behav.Ternary):
            return invalid(expr.then_expr) or invalid(expr.else_expr)
        if isinstance(expr, behav.TypeConv) and expr.size is None:
            return invalid(expr.expr)
        if isinstance(expr, behav.UnaryOperation) and expr.op.value in ('+', '~', '++', '--'):
            return invalid(expr.right)
        return False

    def _validate_condition(self, condition):
        if self._has_invalid_type(condition):
            return
        ty = condition.ty
        name = self._known_type_name(ty)
        if name is not None and (isinstance(ty, type_info.ArrayType)
                                 or isinstance(ty, type_info.PrimitiveType) and ty.kind.is_void):
            raise M2ValidationError('The condition must be a scalar type, but was ' + name,
                                    'NonScalarCondition', condition.line_info)

    def _implicitly_convertible(self, source_type, target_type):
        source, target = self._known_type_name(source_type), self._known_type_name(target_type)
        if source is None or target is None:
            return None
        if (isinstance(source_type, type_info.PrimitiveType) and source_type.kind.is_int
                and isinstance(target_type, type_info.PrimitiveType) and target_type.kind.is_int):
            source_width = arch.get_const_or_val(source_type.size)
            target_width = arch.get_const_or_val(target_type.size)
            return (source_width <= target_width
                    and not (source_type.kind == type_info.TypeKind.INT and target_type.kind == type_info.TypeKind.UINT)
                    and not (source_type.kind == type_info.TypeKind.UINT and target_type.kind == type_info.TypeKind.INT
                             and source_width == target_width))
        return source == target

    def _validate_scalar_conversion(self, target_type, value_node, context, line_info,
                                    issue_code='InvalidAssignmentType'):
        if self._has_invalid_type(value_node):
            return
        target, source = self._known_type_name(target_type), self._known_type_name(value_node.ty)
        if target is not None and source is not None:
            compatible = self._implicitly_convertible(value_node.ty, target_type)
            target_integer = isinstance(target_type, type_info.PrimitiveType) and target_type.kind.is_int
            if not compatible:
                try:
                    value = constant_value(value_node)
                except ZeroDivisionError:
                    raise M2ValidationError('Division by zero', 'DivisionByZero', value_node.line_info)
                allowed = (target_integer and value is not None and value is not INDETERMINATE
                           and holds_value(target_type, value))
                if allowed or value is INDETERMINATE and getattr(context, 'partial', False):
                    logger.info('Assignment is allowed despite type incompatibility, because the right hand side is a constant '
                                '[com.minres.coredsl.ValidConstantAssignment]')
                else:
                    raise M2ValidationError(f'Cannot implicitly convert {source} to {target}',
                                            issue_code, line_info)

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context):
        raise NotImplementedError(f"No visit method implemented for type {type(expr).__name__} in {type(self).__name__}")

    @generate.register
    def _(self, expr: behav.Operation, context):
        self._validate_statements(expr, context)

    @generate.register
    def _(self, expr: behav.Block, context):
        self._validate_statements(expr, context)

    @generate.register
    def _(self, expr: behav.BinaryOperation, context):
        errors = []
        for operand in (expr.left, expr.right):
            try:
                self.generate(operand, context)
            except M2ValidationError as error:
                errors.append(error)
        op = expr.op

        if not self._has_invalid_type(expr):
            if expr.left.ty is None:
                context.emit_warning("Missing infered LHS binop type.", "incomplete-type-info", logger=logger, line_info=expr.left.line_info)
            if expr.right.ty is None:
                context.emit_warning("Missing infered RHS binop type.", "incomplete-type-info", logger=logger, line_info=expr.right.line_info)
            assert expr.left.ty is not None
            assert expr.right.ty is not None
            if op.value in ["|", "&", "^"] and expr.left.ty.size != expr.right.ty.size:
                context.emit_warning("Bitwise operations with differently size operands are discouraged.", "bit-op-missmatch", logger=logger, line_info=expr.line_info)
            if op.value in ["<<", ">>", ">>>"] and expr.right.ty.kind == type_info.TypeKind.INT:
                context.emit_warning("Shift by signed amount", "shift-signed", logger=logger, line_info=expr.line_info)
            if op.value in ["<", "<=", ">", ">=", "==", "!="] and expr.left.ty.kind != expr.right.ty.kind:
                assert(expr.left.ty.kind.is_int and expr.right.ty.kind.is_int)
                if isinstance(expr.left, behav.Literal) and expr.left.value == 0:
                    pass
                elif isinstance(expr.right, behav.Literal) and expr.right.value == 0:
                    pass
                else:
                    context.emit_warning(f"Signed vs. unsigned comparison", "sign-compare", logger=logger, line_info=expr.line_info)
            # TODO: also check possible range of non-literal rhs?
            if op.value in ("<<", ">>") and isinstance(expr.right, behav.Literal) and arch.get_const_or_val(expr.left.ty.size) <= expr.right.value:
                context.emit_warning(f"Shift count overflow for {op.value} operation ({expr.left.ty.size} vs. {expr.right.value})", "shift-overflow", logger=logger, line_info=expr.line_info)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]


    @generate.register
    def _(self, expr: behav.SliceOperation, context):
        children = [expr.expr, expr.left]
        if expr.right is not expr.left:
            children.append(expr.right)
        self._validate_access(children, children[1:], context,
                              getattr(expr.expr, "ty", None), expr.expr.line_info,
                              (expr.left, expr.right) if expr.left is not expr.right else None)

    @generate.register
    def _(self, expr: behav.ConcatOperation, context):
        if self._has_invalid_type(expr.left):
            self.generate(expr.left, context)
            return
        self._validate_children((expr.left, expr.right), context)

    @generate.register
    def _(self, expr: behav.Literal, context):
        pass

    @generate.register
    def _(self, expr: behav.Tensor, context):
        ty = expr.ty
        self._validate_declared_sizes(ty, expr.line_info)
        shape = []
        shape_known = True
        while isinstance(ty, type_info.ArrayType):
            count = self._declared_size(ty.length, expr.line_info)
            if not isinstance(count, int):
                shape_known = False
            else:
                shape.append(count)
            ty = ty.element_type
        errors = []
        if shape_known and shape and tuple(shape) != expr.value.shape:
            errors.append(M2ValidationError('List initializer size does not match LHS size',
                                            'InvalidAssignmentType', expr.line_info))
        for element in getattr(expr, 'initializer_elements', None) or ():
            try:
                self.generate(element, context)
            except M2ValidationError as error:
                errors.append(error)
            if isinstance(ty, type_info.PrimitiveType):
                try:
                    self._validate_scalar_conversion(ty, element, context, element.line_info or expr.line_info)
                except M2ValidationError as error:
                    errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    @staticmethod
    def _assignment_value(expr):
        if getattr(expr, 'compound_operator', None) and isinstance(expr.expr, behav.BinaryOperation):
            return expr.expr.right
        return expr.expr

    @generate.register
    def _(self, expr: behav.Assignment, context):
        errors = []
        for child in (expr.target, self._assignment_value(expr)):
            try:
                self.generate(child, context)
            except M2ValidationError as error:
                errors.append(error)
        try:
            if not isinstance(expr.target, behav.VarDefinition):
                self._validate_assignment_target(expr.target, expr.line_info)
        except M2ValidationError as error:
            errors.append(error)
        try:
            self._validate_assignment_types(expr, context)
        except M2ValidationError as error:
            errors.append(error)
        operator = getattr(expr, 'compound_operator', None)
        value = self._assignment_value(expr)
        target_name = self._known_type_name(expr.target.ty)
        value_name = self._known_type_name(value.ty)
        if operator and not getattr(context, 'partial', False) and target_name is not None and value_name is not None:
            integer_types = all(isinstance(ty, type_info.PrimitiveType) and ty.kind.is_int
                                for ty in (expr.target.ty, value.ty))
            if not integer_types:
                errors.append(M2ValidationError(
                    f'Cannot combine {value_name} and {target_name} with the {operator[0]} operator',
                    'InvalidOperationType', expr.line_info))
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    def _validate_assignment_types(self, expr, context):
        value = self._assignment_value(expr)
        if self._has_invalid_type(expr.target) or self._has_invalid_type(value):
            return
        if expr.target.ty is None:
            context.emit_warning("Missing infered assignment target type.", "incomplete-type-info", logger=logger, line_info=expr.target.line_info)
        if value.ty is None:
            context.emit_warning("Missing infered assignment expr type.", "incomplete-type-info", logger=logger, line_info=value.line_info)
        assert expr.target.ty is not None
        assert value.ty is not None
        if isinstance(expr.target.ty, type_info.ArrayType) or isinstance(value.ty, type_info.ArrayType):
            target = self._known_type_name(expr.target.ty)
            source = self._known_type_name(value.ty)
            if target is not None and source is not None and target != source:
                raise M2ValidationError(f'Cannot implicitly convert {source} to {target}',
                                        'InvalidAssignmentType', expr.line_info)
            return
        assert isinstance(expr.target.ty, type_info.PrimitiveType)
        self._validate_scalar_conversion(expr.target.ty, value, context, expr.line_info)
        if arch.get_const_or_val(expr.target.ty.size) < arch.get_const_or_val(value.ty.size):
            context.emit_warning(f"Implicit truncation {value.ty.size} -> {expr.target.ty.size} found", "implicit-trunc", logger=logger, line_info=expr.line_info)
        if arch.get_const_or_val(expr.target.ty.size) > arch.get_const_or_val(value.ty.size):
            context.emit_warning(f"Implicit extend {value.ty.size} -> {expr.target.ty.size} found", "implicit-extend", logger=logger, line_info=expr.line_info)

    @generate.register
    def _(self, expr: behav.Conditional, context):
        errors = []
        for cond in expr.conds:
            try:
                self.generate(cond, context)
                self._validate_condition(cond)
            except M2ValidationError as error:
                errors.append(error)
        for stmt in expr.stmts:
            try:
                self.generate(stmt, context)
            except M2ValidationError as error:
                errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    @generate.register
    def _(self, expr: behav.Loop, context):
        errors = []
        try:
            self.generate(expr.cond, context)
            self._validate_condition(expr.cond)
        except M2ValidationError as error:
            errors.append(error)
        previous_depth = getattr(self, '_loop_depth', 0)
        self._loop_depth = previous_depth + 1
        try:
            for stmt in expr.stmts:
                try:
                    self.generate(stmt, context)
                except M2ValidationError as error:
                    errors.append(error)
        finally:
            self._loop_depth = previous_depth
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    @generate.register
    def _(self, expr: behav.Ternary, context):
        errors = []
        for child in (expr.cond, expr.then_expr, expr.else_expr):
            try:
                self.generate(child, context)
            except M2ValidationError as error:
                errors.append(error)
        try:
            self._validate_condition(expr.cond)
        except M2ValidationError as error:
            errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    @generate.register
    def _(self, expr: behav.Return, context):
        errors = []
        if expr.expr is not None:
            try:
                self.generate(expr.expr, context)
            except M2ValidationError as error:
                errors.append(error)
        try:
            function = getattr(context, 'function', None)
            if function is None:
                raise M2ValidationError('Return statement is only valid in a function',
                                        'ReturnStatementOutsideFunction', expr.line_info)
            target_type = type_info.PrimitiveType(function.ty.kind, function.ty.size)
            if target_type.kind.is_void and expr.expr is not None:
                raise M2ValidationError('Void functions may not return a value',
                                        'ReturnWithValueInVoidFunction', expr.line_info)
            if not target_type.kind.is_void and expr.expr is None:
                raise M2ValidationError('Non-void functions must return a value',
                                        'ReturnWithoutValueInNonVoidFunction', expr.line_info)
            if expr.expr is not None and not self._has_invalid_type(expr.expr):
                target, source = self._known_type_name(target_type), self._known_type_name(expr.expr.ty)
                if target is not None and source is not None:
                    compatible = self._implicitly_convertible(expr.expr.ty, target_type)
                    if not compatible:
                        raise M2ValidationError(f'Cannot convert from {source} to {target}',
                                                'ReturnTypeNotConvertible', expr.line_info)
        except M2ValidationError as error:
            errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]
        return expr

    @generate.register
    def _(self, expr: behav.UnaryOperation, context):
        errors = []
        try:
            self.generate(expr.right, context)
        except M2ValidationError as error:
            errors.append(error)
        if expr.op.value in ('++', '--'):
            try:
                self._validate_assignment_target(expr.right, expr.line_info)
            except M2ValidationError as error:
                errors.append(error)
            ty = getattr(expr.right, 'ty', None)
            if self._known_type_name(ty) is not None and not (
                    isinstance(ty, type_info.PrimitiveType) and ty.kind.is_int):
                errors.append(M2ValidationError('Increment and decrement operators are only valid on integer types',
                                                'InvalidOperationType', expr.line_info))
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]
        return expr

    @generate.register
    def _(self, expr: behav.VarDefinition, context):
        self._validate_declared_sizes(expr.var.ty, expr.line_info)

    @generate.register
    def _(self, expr: behav.Break, context):
        if not getattr(self, '_loop_depth', 0) and not getattr(self, '_preserved_breaks_active', False):
            raise M2ValidationError('Unexpected break statement', 'StrayControlFlowStatement', expr.line_info)

    @generate.register
    def _(self, expr: behav.Continue, context):
        if not getattr(self, '_loop_depth', 0) and not getattr(self, '_preserved_continues_active', False):
            raise M2ValidationError('Unexpected continue statement', 'StrayControlFlowStatement', expr.line_info)

    @generate.register
    def _(self, expr: behav.NamedReference, context):
        pass

    @generate.register
    def _(self, expr: behav.IndexedReference, context):
        children = [expr.index]
        if expr.right is not None and expr.right is not expr.index:
            children.append(expr.right)
        self._validate_access(children, children, context,
                              getattr(expr.reference, "ty", None), expr.line_info,
                              (expr.index, expr.right) if expr.right is not None else None)

    @generate.register
    def _(self, expr: behav.TypeConv, context):
        self.generate(expr.expr, context)

    @generate.register
    def _(self, expr: behav.Callable, context):
        parameters = None
        if isinstance(expr.ref_or_name, arch.Function):
            parameters = list(expr.ref_or_name.args.values())
            if len(parameters) != len(expr.args):
                raise M2ValidationError(
                    f'Incorrect argument count. Expected {len(parameters)}, got {len(expr.args)}',
                    'InvalidArgumentCount', expr.line_info)
        errors = []
        for index, argument in enumerate(expr.args):
            try:
                self.generate(argument, context)
            except M2ValidationError as error:
                errors.append(error)
            if parameters is not None:
                try:
                    self._validate_scalar_conversion(parameters[index].ty, argument, context,
                                                      argument.line_info or expr.line_info, 'InvalidArgumentType')
                except M2ValidationError as error:
                    errors.append(error)
        if errors:
            errors[0].related_diagnostics.extend(errors[1:])
            raise errors[0]

    @generate.register
    def _(self, expr: behav.Group, context):
        self.generate(expr.expr, context)
