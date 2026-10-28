"""The release guards end-index diagnostics with the starting index type."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as source_helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, type_info
from m2isar.transforms.validate_behav.validate import ValidatorContext
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor


CASES = [('N', '2', 0), ('2', 'N', 2), ('2', '2', 2), ('N', 'N', 0)]
BAD_CALL_ACCESS = ('Core C { functions { void g() {} void f() { '
                   'int x=g(0)[g(0):g(0)]; } } }')


class RangeIndexGuardNativeTest(unittest.TestCase):
    def test_bad_calls_retain_void_type_and_all_access_errors(self):
        with self.assertRaises(M2ValidationError) as caught:
            self.validate(BAD_CALL_ACCESS)
        errors = [caught.exception] + caught.exception.related_diagnostics
        self.assertEqual([e.issue_code.split('.')[-1] for e in errors],
                         ['InvalidArgumentCount', 'InvalidArgumentCount',
                          'NonIndexableExpression', 'InvalidIndexType',
                          'InvalidArgumentCount', 'InvalidIndexType',
                          'InvalidRangePattern'])

    def test_source_known_and_unknown_array_bounds(self):
        for start, end, count in CASES:
            with self.subTest(start=start, end=end):
                source = ('InstructionSet I { architectural_state { int N; } '
                          'functions { void f() { int x[2]; int i[' + start
                          + ']; int j[' + end + ']; x[i:j]=0; } } }')
                if count:
                    with self.assertRaises(M2ValidationError) as caught:
                        self.validate(source)
                    errors = [caught.exception] + caught.exception.related_diagnostics
                    self.assertEqual([e.issue_code.split('.')[-1] for e in errors], ['InvalidIndexType'] * count)
                else:
                    source_helpers.SourceValidatorTest.validate(self, source)

    validate = source_helpers.SourceValidatorTest.validate

    def test_source_full_range_collects_both_indices_and_pattern(self):
        source = 'Core C { functions { void f() { int x[2]; int i[2]; int j[2]; x[i:j]=0; } } }'
        with self.assertRaises(M2ValidationError) as caught:
            self.validate(source)
        errors = [caught.exception] + caught.exception.related_diagnostics
        self.assertEqual([e.issue_code.split('.')[-1] for e in errors],
                         ['InvalidIndexType', 'InvalidIndexType', 'InvalidRangePattern'])

    def test_known_and_unknown_array_bounds(self):
        integer = type_info.PrimitiveType(type_info.TypeKind.INT, 32)
        for start, end, count in CASES:
            for form in ('scalar', 'array'):
                with self.subTest(start=start, end=end, form=form):
                    first, last = behav.NamedReference(object()), behav.NamedReference(object())
                    first.ty = type_info.ArrayType(integer, None if start == 'N' else 2)
                    last.ty = type_info.ArrayType(integer, None if end == 'N' else 2)
                    if form == 'array':
                        node = behav.IndexedReference(None, first, last)
                    else:
                        target = behav.NamedReference(None)
                        target.ty = integer
                        node = behav.SliceOperation(target, first, last)
                    context = ValidatorContext(None, partial=True)
                    if count:
                        with self.assertRaises(M2ValidationError) as caught:
                            ValidateBehavVisitor().generate(node, context)
                        errors = [caught.exception] + caught.exception.related_diagnostics
                        self.assertEqual([e.issue_code.split('.')[-1] for e in errors], ['InvalidIndexType'] * count)
                    else:
                        ValidateBehavVisitor().generate(node, context)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class RangeIndexGuardOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_bad_calls_retain_void_type_and_all_access_errors(self):
        output, _ = self.probe(BAD_CALL_ACCESS)
        self.assertEqual(output.count('ERROR:Incorrect argument count.'), 3, output)
        self.assertEqual(output.count('ERROR:Cannot index into void'), 1, output)
        self.assertEqual(output.count('ERROR:Index must have an integer type'), 2, output)
        self.assertEqual(output.count('ERROR:Invalid range pattern'), 1, output)
        self.assertEqual(output.count('ERROR:'), 7, output)

    def test_release_full_range_collects_indices_and_pattern(self):
        output, _ = self.probe('Core C { functions { void f() { int x[2]; int i[2]; int j[2]; x[i:j]=0; } } }')
        self.assertEqual(output.count('ERROR:Index must have an integer type'), 2, output)
        self.assertEqual(output.count('ERROR:Invalid range pattern'), 1, output)
        self.assertEqual(output.count('ERROR:'), 3, output)

    def test_release_known_and_unknown_array_bounds(self):
        for start, end, count in CASES:
            with self.subTest(start=start, end=end):
                output, _ = self.probe('InstructionSet I { architectural_state { int N; } '
                                       'functions { void f() { int x[2]; int i[' + start
                                       + ']; int j[' + end + ']; x[i:j]=0; } } }')
                self.assertEqual(output.count('ERROR:Index must have an integer type'), count, output)
                self.assertEqual(output.count('ERROR:'), count, output)
