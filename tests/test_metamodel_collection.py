"""Independent behavior bodies retain their diagnostics after another body fails."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, type_info, load_model
from m2isar.transforms.infer_types.visitor import InferTypesMutator
from m2isar.transforms.validate_behav.validate import validate_behav, ValidatorContext
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsManager


SOURCE = '''Core C { functions {
 void f() { if (0) break; }
 void g() { if (0) break; if (0) break; }
 int h() {}
} }'''

SIBLINGS = [('void f() { g(); g(); }', ['InvalidArgumentCount'] * 2),
            ('void f() { { g(); } g(); }', ['InvalidArgumentCount'] * 2),
            ('int f() { g(); }', ['InvalidArgumentCount', 'MissingReturnStatement'])]


CONTROL_FLOW = [
    ('void f(bool c) { if (c) g(); else g(); }', ['InvalidArgumentCount'] * 2),
    ('void f(bool c) { while (c) { g(); g(); } }', ['InvalidArgumentCount'] * 2),
    ('void f() { int x[2]; if (x) g(); else g(); }',
     ['NonScalarCondition', 'InvalidArgumentCount', 'InvalidArgumentCount']),
    ('void f() { int x[2]; while (x) { g(); g(); } }',
     ['NonScalarCondition', 'InvalidArgumentCount', 'InvalidArgumentCount']),
]


TERNARIES = [
    ('int f(bool c) { return c ? g() : g(); }', ['InvalidArgumentCount'] * 2),
    ('int f() { int x[2]; return x ? g() : g(); }',
     ['InvalidArgumentCount', 'InvalidArgumentCount', 'NonScalarCondition']),
    ('int f() { return g() ? g() : g(); }', ['InvalidArgumentCount'] * 3),
    ('extern void v(int a); int f() { return v() ? g() : g(); }',
     ['InvalidArgumentCount'] * 3 + ['NonScalarCondition']),
]


CALLS = [
    ('extern void h(int a, int b); void f() { h(g(), g()); }',
     ['InvalidArgumentCount'] * 2),
    ('extern void h(int a); void f() { h(g(), g()); }',
     ['InvalidArgumentCount']),
    ('extern void h(unsigned<8> a, unsigned<8> b); void f() { h(16\'d256, 16\'d256); }',
     ['InvalidArgumentType'] * 2),
    ('extern unsigned<16> k(int a); extern void h(unsigned<8> a, unsigned<8> b); '
     'void f() { h(k(), k()); }',
     ['InvalidArgumentCount', 'InvalidArgumentType'] * 2),
]


BINARIES = [('signed<64> f() { return g() ' + op + ' g(); }',
             ['InvalidArgumentCount'] * 2) for op in ('+', '*', '==', '&&', '<<')]
BINARIES.append(('signed<64> f() { return (g() + g()) + (g() + g()); }',
                 ['InvalidArgumentCount'] * 4))


RETURNS = [
    ('void f() { return g(); }', ['InvalidArgumentCount', 'ReturnWithValueInVoidFunction']),
    ('unsigned<8> f() { return g(); }', ['InvalidArgumentCount', 'ReturnTypeNotConvertible']),
    ('int f() { return g() + g(); }', ['InvalidArgumentCount'] * 2 + ['ReturnTypeNotConvertible']),
    ('int f() { return g(); }', ['InvalidArgumentCount']),
]


ASSIGNMENTS = [
    ('void f() { int x; x = g(); }', ['InvalidArgumentCount']),
    ('void f() { unsigned<8> x; x = g(); }', ['InvalidArgumentCount', 'InvalidAssignmentType']),
    ('void f() { int x; x = g() + g(); }', ['InvalidArgumentCount'] * 2 + ['InvalidAssignmentType']),
    ('void f() { signed<64> x; x = g() + g(); }', ['InvalidArgumentCount'] * 2),
    ('void f() { int x[2]; x[g()] = g(); }', ['InvalidArgumentCount'] * 2),
]


ACCESS = [
    ('void f() { int x[2]; int i[2]; x[i] = 0; }', ['InvalidIndexType']),
    ('extern void v(); void f() { int x[2]; x[v()] = 0; }', ['InvalidIndexType']),
    ('extern void v(int a); void f() { int x[2]; x[v()] = 0; }',
     ['InvalidArgumentCount', 'InvalidIndexType']),
    ('bool f() { return g()[g()]; }', ['InvalidArgumentCount'] * 2),
    ('unsigned<64> f() { return g() :: g(); }', ['InvalidArgumentCount'] * 2),
]


TARGETS = [
    ('extern void v(); void f() { return v()[0]; }',
     ['NonIndexableExpression', 'ReturnWithValueInVoidFunction']),
    ('extern void v(int a); void f() { return v()[0]; }',
     ['InvalidArgumentCount', 'NonIndexableExpression', 'ReturnWithValueInVoidFunction']),
    ('extern void v(); void f() { return v()[v()]; }',
     ['NonIndexableExpression', 'InvalidIndexType', 'ReturnWithValueInVoidFunction']),
]


INVALID_RESULTS = [
    ('void f() { int x = v()[0]; }', ['NonIndexableExpression']),
    ('int f() { return (v()[0]); }', ['NonIndexableExpression']),
    ('int f() { return ~v()[0]; }', ['NonIndexableExpression']),
    ('signed<8> f() { return (signed<16>)v()[0]; }',
     ['NonIndexableExpression', 'ReturnTypeNotConvertible']),
    ('void f() { unsigned<64> x = g() :: v()[0]; }',
     ['InvalidArgumentCount', 'NonIndexableExpression']),
    ('int f() { return v()[0]; }', ['NonIndexableExpression']),
    ('extern void h(int a); void f() { h(v()[0]); }', ['NonIndexableExpression']),
    ('void f() { if (v()[0]) {} }', ['NonIndexableExpression']),
    ('void f() { int x = v()[0] + g(); }', ['NonIndexableExpression', 'InvalidArgumentCount']),
    ('void f(bool c) { int x = c ? v()[0] : 1; }', ['NonIndexableExpression']),
    ('void f() { unsigned<64> x = v()[0] :: g(); }', ['NonIndexableExpression']),
]


RANGES = [
    ('unsigned<32> f() { unsigned<32> x; return x[0:2147483647]; }', ['InvalidIntegerTypeSize']),
    ('void f() { unsigned<32> x; int y = x[2147483647:0]; }', ['InvalidIntegerTypeSize']),
    ('unsigned<32> f(int i, int j) { unsigned<32> x; return x[i:j]; }', ['InvalidRangePattern']),
    ('unsigned<32> f(int i) { unsigned<32> x; return x[i:g()]; }',
     ['InvalidArgumentCount', 'InvalidRangePattern']),
    ('void f(int i, int j) { unsigned<32> x; int y = x[i:j]; }', ['InvalidRangePattern']),
    ('void f(int i, int j) { unsigned<32> x; if (x[i:j]) {} }', ['InvalidRangePattern']),
    ('extern void h(int a); void f(int i, int j) { unsigned<32> x; h(x[i:j]); }',
     ['InvalidRangePattern']),
    ('void f(int i, int j) { unsigned<32> x; int y = x[i:j] + g(); }',
     ['InvalidRangePattern', 'InvalidArgumentCount']),
    ('void f(int i, int j) { unsigned<32> x; unsigned<64> y = x[i:j] :: g(); }',
     ['InvalidRangePattern']),
]


VALID_RANGES = [
    'unsigned<4> f(int i) { signed<32> x; return x[i:i+(-3)]; }',
    'unsigned<4> f(int i) { signed<32> x; return x[i-(-3):i]; }',
    'unsigned<4> f() { signed<32> x; return x[0:3]; }',
    'bool f(int i) { signed<32> x; return x[i]; }',
    'unsigned<16> f() { signed<8> x[4]; return x[0:1]; }',
    'unsigned<16> f() { signed<8> x[4]; return x[1:0]; }',
    'unsigned<16> f(int i) { signed<8> x[4]; return x[i:i+1]; }',
    'unsigned<16> f(int i) { signed<8> x[4]; return x[i-1:i]; }',
    'unsigned<32> f(int i) { unsigned<32> x; return x[i:i]; }',
    'unsigned<32> f(int i) { unsigned<32> x; return x[i:i+3]; }',
    'unsigned<32> f(int i) { unsigned<32> x; return x[i-3:i]; }',
    'unsigned<32> f() { unsigned<32> x; return x[0:3]; }',
]


def flatten(error):
    return [error] + [item for related in error.related_diagnostics for item in flatten(related)]


class MetamodelCollectionNativeTest(unittest.TestCase):
    def test_scalar_slice_inference_unsigned_and_entity_identity(self):
        signed = type_info.PrimitiveType(type_info.TypeKind.INT, 32)
        target = arch.Variable('x', signed)
        index = arch.Variable('i', signed)
        other = arch.Variable('i', signed)
        context = WarningsManager(None)
        for first, last, width in (
                (behav.Literal(0, signed), behav.Literal(3, signed), 4),
                (behav.NamedReference(index), behav.NamedReference(index), 1),
                (behav.NamedReference(index),
                 behav.BinaryOperation(behav.NamedReference(index), behav.Operator('+'),
                                       behav.Literal(-3, signed)), 4)):
            node = behav.SliceOperation(behav.NamedReference(target), first, last)
            result = InferTypesMutator().generate(node, context)
            self.assertEqual(result.ty.kind, type_info.TypeKind.UINT)
            self.assertEqual(result.ty.size, width)
        self.assertEqual(target.ty.kind, type_info.TypeKind.INT)
        node = behav.SliceOperation(behav.NamedReference(target),
                                   behav.NamedReference(index), behav.NamedReference(other))
        result = InferTypesMutator().generate(node, context)
        self.assertIsNone(result.ty)

    def test_array_range_inference_types_and_single_index(self):
        element = type_info.PrimitiveType(type_info.TypeKind.INT, 8)
        array = arch.Variable('x', type_info.ArrayType(element, 4))
        for first, last, width in ((0, 1, 16), (1, 0, 16), (2, 2, 8)):
            with self.subTest(first=first, last=last):
                node = behav.IndexedReference(array, behav.Literal(first, element),
                                             behav.Literal(last, element))
                result = InferTypesMutator().generate(node, WarningsManager(None))
                self.assertEqual(result.ty.kind, type_info.TypeKind.UINT)
                self.assertEqual(result.ty.size, width)
        single = InferTypesMutator().generate(
            behav.IndexedReference(array, behav.Literal(0, element)), WarningsManager(None))
        self.assertEqual(single.ty.kind, type_info.TypeKind.INT)
        self.assertEqual(single.ty.size, 8)
        self.assertEqual(array.ty.element_type.kind, type_info.TypeKind.INT)

    def test_loop_statement_recovery_restores_scope(self):
        visitor, context = ValidateBehavVisitor(), WarningsManager(None)
        condition = behav.Literal(1, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
        with self.assertRaises(M2ValidationError) as caught:
            visitor.generate(behav.Loop(condition, [behav.Return(None), behav.Break(),
                                                   behav.Return(None)], False), context)
        self.assertEqual([e.issue_code.split('.')[-1] for e in flatten(caught.exception)],
                         ['ReturnStatementOutsideFunction'] * 2)
        with self.assertRaises(M2ValidationError) as caught:
            visitor.generate(behav.Break(), context)
        self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.StrayControlFlowStatement')

    def test_return_context_error_after_child_error(self):
        with self.assertRaises(M2ValidationError) as caught:
            ValidateBehavVisitor().generate(behav.Return(behav.Return(None)), WarningsManager(None))
        self.assertEqual([e.issue_code.split('.')[-1] for e in flatten(caught.exception)],
                         ['ReturnStatementOutsideFunction'] * 2)

    def test_range_children_and_shared_single_index(self):
        for node, count in [
            (behav.SliceOperation(behav.Return(None), behav.Return(None), behav.Return(None)), 3),
            (behav.IndexedReference(None, behav.Return(None), behav.Return(None)), 2),
        ]:
            with self.subTest(node=type(node)):
                with self.assertRaises(M2ValidationError) as caught:
                    ValidateBehavVisitor().generate(node, ValidatorContext(None, partial=True))
                self.assertEqual(len(flatten(caught.exception)), count)
        index = behav.Return(None)
        with self.assertRaises(M2ValidationError) as caught:
            ValidateBehavVisitor().generate(behav.SliceOperation(behav.Literal(1), index, index),
                                            ValidatorContext(None, partial=True))
        self.assertEqual(len(flatten(caught.exception)), 1)

    def test_index_types_and_deferred_providers(self):
        integer = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
        array = type_info.ArrayType(integer, 2)
        for ty, invalid in ((array, True),
                            (type_info.PrimitiveType(type_info.TypeKind.VOID, 0), True),
                            (integer, False), (None, False),
                            (type_info.ArrayType(integer, None), False),
                            (type_info.PointerType(integer), False),
                            (type_info.FloatType(8, 23, 32), False)):
            with self.subTest(type=ty):
                start, end = behav.NamedReference(None), behav.NamedReference(None)
                start.ty = end.ty = ty
                node = behav.IndexedReference(None, start, end)
                if invalid:
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(node, WarningsManager(None))
                    self.assertEqual([e.issue_code.split('.')[-1] for e in flatten(caught.exception)],
                                     ['InvalidIndexType'] * 2)
                else:
                    ValidateBehavVisitor().generate(node, WarningsManager(None))

    def test_invalid_range_result_in_partial_analysis(self):
        integer = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
        target = behav.NamedReference(None)
        target.ty = integer
        start, end = behav.NamedReference(object()), behav.NamedReference(object())
        start.ty = end.ty = integer
        visitor = ValidateBehavVisitor()
        for node in (behav.SliceOperation(target, start, end),
                     behav.IndexedReference(target.reference, start, end)):
            with self.subTest(node=type(node).__name__):
                self.assertTrue(visitor._has_invalid_type(node))
                visitor.generate(node, ValidatorContext(None, partial=True))
                with self.assertRaises(M2ValidationError) as caught:
                    visitor.generate(node, ValidatorContext(None, partial=False))
                self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.InvalidRangePattern')
        single = behav.SliceOperation(target, start, start)
        self.assertFalse(visitor._has_invalid_type(single))

    def test_range_size_boundaries_and_array_elements(self):
        integer = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
        # Cover the exact limit without allocating arrays or giant literals.
        for target_type, end, overflow in (
                (integer, 2147483646, False), (integer, 2147483647, True),
                (type_info.ArrayType(integer, 1), 268435454, False),
                (type_info.ArrayType(integer, 1), 268435455, True),
                (type_info.ArrayType(type_info.ArrayType(integer, 2), 1), 134217727, True),
                (type_info.ArrayType(type_info.ArrayType(integer, None), 1), 2147483647, False)):
            with self.subTest(target_type=target_type, end=end):
                target = behav.NamedReference(None)
                target.ty = target_type
                start = behav.Literal(0, integer)
                last = behav.Literal(end, integer)
                node = behav.IndexedReference(target.reference, start, last)
                # IndexedReference obtains the target type from its entity.
                node.reference = SimpleNamespace(ty=target_type)
                visitor = ValidateBehavVisitor()
                self.assertEqual(visitor._has_invalid_type(node), overflow)
                for partial in (False, True):
                    context = ValidatorContext(None, partial=partial)
                    if overflow:
                        with self.assertRaises(M2ValidationError) as caught:
                            visitor.generate(node, context)
                        self.assertEqual(caught.exception.issue_code,
                                         'com.minres.coredsl.InvalidIntegerTypeSize')
                    else:
                        visitor.generate(node, context)

    def test_known_void_target_and_deferred_targets(self):
        for ty, invalid in ((type_info.PrimitiveType(type_info.TypeKind.VOID, 0), True),
                            (type_info.PrimitiveType(type_info.TypeKind.UINT, 8), False),
                            (None, False),
                            (type_info.PointerType(type_info.PrimitiveType(type_info.TypeKind.UINT, 8)), False)):
            target = behav.NamedReference(None)
            target.ty = ty
            index = behav.Literal(0, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
            node = behav.SliceOperation(target, index, index)
            if invalid:
                with self.assertRaises(M2ValidationError) as caught:
                    ValidateBehavVisitor().generate(node, WarningsManager(None))
                self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.NonIndexableExpression')
            else:
                ValidateBehavVisitor().generate(node, WarningsManager(None))

    def test_saved_invalid_result_errors(self):
        self.check_saved_errors(INVALID_RESULTS, "int", "extern void v(); ")

    def test_saved_range_errors(self):
        self.check_saved_errors(RANGES, "int")
        for function in VALID_RANGES:
            with self.subTest(function=function), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'valid.core_desc'
                path.write_text('Core C { functions { ' + function + ' } }')
                result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 0, result.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                         str(Path(directory) / 'gen_model' / 'valid.m2isarmodel')],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_saved_target_errors(self):
        self.check_saved_errors(TARGETS)

    def test_saved_access_errors(self):
        self.check_saved_errors(ACCESS, "int")

    def test_saved_assignment_errors(self):
        self.check_saved_errors(ASSIGNMENTS, "int")

    def test_saved_return_errors(self):
        self.check_saved_errors(RETURNS, "int")

    def test_saved_binary_errors(self):
        self.check_saved_errors(BINARIES, "int")

    def test_saved_call_errors(self):
        self.check_saved_errors(CALLS, "int")

    def test_saved_ternary_errors(self):
        self.check_saved_errors(TERNARIES, "int")

    def test_saved_control_flow_errors(self):
        self.check_saved_errors(CONTROL_FLOW)

    def test_saved_sibling_statement_errors(self):
        self.check_saved_errors(SIBLINGS)

    def check_saved_errors(self, cases, return_type="void", declarations=""):
        for function, issues in cases:
            with self.subTest(function=function), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'siblings.core_desc'
                source.write_text('Core C { functions { extern ' + return_type + ' g(int a); ' + declarations + function + ' } }')
                result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(source)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 0, result.stdout)
                saved = Path(directory) / 'gen_model' / 'siblings.m2isarmodel'
                with self.assertRaises(M2ValidationError) as caught:
                    validate_behav(load_model(saved), None)
                self.assertEqual([e.issue_code.split('.')[-1] for e in flatten(caught.exception)], issues)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(sum(line.count('com.minres.coredsl.') for line in result.stdout.splitlines()
                                     if not line.startswith('INFO:')), len(issues), result.stdout)
                self.assertNotIn('Traceback', result.stdout)

    def test_saved_independent_functions(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'collection.core_desc'
            source.write_text(SOURCE)
            result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(source)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            saved = Path(directory) / 'gen_model' / 'collection.m2isarmodel'
            with self.assertRaises(M2ValidationError) as caught:
                validate_behav(load_model(saved), None)
            errors = flatten(caught.exception)
            self.assertEqual([e.issue_code.split('.')[-1] for e in errors],
                             ['StrayControlFlowStatement'] * 3 + ['MissingReturnStatement'])
            self.assertEqual([e.line_info.start_line_no for e in errors[:3]], [2, 3, 3])
            self.assertNotIn('\n', caught.exception.args[0])
            result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertEqual(result.stdout.count('Unexpected break statement'), 3, result.stdout)
            self.assertEqual(result.stdout.count('Not all execution paths return a value'), 1, result.stdout)
            self.assertNotIn('Traceback', result.stdout)

    def test_all_body_owners_and_scopes(self):
        model = SimpleNamespace(cores={}, sets={})
        for scope in ('cores', 'sets'):
            definition = SimpleNamespace(name='C', functions={}, instructions={}, always_blocks={})
            getattr(model, scope)['C'] = definition
            for owner in ('functions', 'instructions', 'always_blocks'):
                member = SimpleNamespace(name=owner, operation=behav.Operation([behav.Break()]),
                                         extern=False, ty=type_info.FunctionType(0, type_info.TypeKind.VOID))
                getattr(definition, owner)[owner] = member
        with self.assertRaises(M2ValidationError) as caught:
            validate_behav(model, None)
        self.assertEqual(len(flatten(caught.exception)), 6)
        self.assertTrue(all(e.issue_code == 'com.minres.coredsl.StrayControlFlowStatement'
                            for e in flatten(caught.exception)))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_invalid_result_errors(self):
        self.check_release_errors(INVALID_RESULTS, "int", "extern void v(); ")

    def test_release_range_errors(self):
        self.check_release_errors(RANGES, "int")
        for function in VALID_RANGES:
            output, _ = self.probe('Core C { functions { ' + function + ' } }')
            self.assertNotIn('ERROR:', output, output)

    def test_release_target_errors(self):
        self.check_release_errors(TARGETS)

    def test_release_access_errors(self):
        self.check_release_errors(ACCESS, "int")

    def test_release_assignment_errors(self):
        self.check_release_errors(ASSIGNMENTS, "int")

    def test_release_return_errors(self):
        self.check_release_errors(RETURNS, "int")

    def test_release_binary_errors(self):
        self.check_release_errors(BINARIES, "int")

    def test_release_call_errors(self):
        self.check_release_errors(CALLS, "int")

    def test_release_ternary_errors(self):
        self.check_release_errors(TERNARIES, "int")

    def test_release_control_flow_errors(self):
        self.check_release_errors(CONTROL_FLOW)

    def test_release_sibling_errors(self):
        self.check_release_errors(SIBLINGS)

    def check_release_errors(self, cases, return_type="void", declarations=""):
        for function, issues in cases:
            with self.subTest(function=function):
                output, _ = self.probe('Core C { functions { extern ' + return_type + ' g(int a); ' + declarations + function + ' } }')
                self.assertEqual(output.count('ERROR:Incorrect argument count.'),
                                 issues.count('InvalidArgumentCount'), output)
                self.assertEqual(output.count('ERROR:Cannot implicitly convert'),
                                 issues.count('InvalidArgumentType') + issues.count('InvalidAssignmentType'), output)
                self.assertEqual(output.count('ERROR:Cannot implicitly convert unsigned<16> to unsigned<8>'),
                                 issues.count('InvalidArgumentType'), output)
                self.assertEqual(output.count('ERROR:The condition must be a scalar type'),
                                 issues.count('NonScalarCondition'), output)
                self.assertEqual(output.count('ERROR:Invalid range pattern'),
                                 issues.count('InvalidRangePattern'), output)
                self.assertEqual(output.count('ERROR:The combined size of the selected elements must not exceed Integer.MAX_VALUE'),
                                 issues.count('InvalidIntegerTypeSize'), output)
                self.assertEqual(output.count('ERROR:Cannot index into void'),
                                 issues.count('NonIndexableExpression'), output)
                self.assertEqual(output.count('ERROR:Index must have an integer type'),
                                 issues.count('InvalidIndexType'), output)
                self.assertEqual(output.count('ERROR:Void functions may not return a value'),
                                 issues.count('ReturnWithValueInVoidFunction'), output)
                self.assertEqual(output.count('ERROR:Cannot convert from'),
                                 issues.count('ReturnTypeNotConvertible'), output)
                self.assertEqual(output.count('ERROR:'), len(issues), output)
                self.assertEqual(output.count('ERROR:Not all execution paths return a value'),
                                 issues.count('MissingReturnStatement'), output)

    def test_release_independent_functions(self):
        output, _ = self.probe(SOURCE)
        self.assertEqual(output.count('ERROR:Unexpected break statement'), 3, output)
        self.assertEqual(output.count('ERROR:Not all execution paths return a value'), 1, output)
