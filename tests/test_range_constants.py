"""Constant range failures retain release diagnostics without model mutation."""
import os
import unittest

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, type_info
from m2isar.transforms.validate_behav.constants import range_size
from m2isar.transforms.validate_behav.validate import ValidatorContext
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor


def access(array=False):
    integer = type_info.PrimitiveType(type_info.TypeKind.INT, 32)
    index = arch.Variable('i', integer)
    target = arch.Variable('x', type_info.ArrayType(integer, 4) if array else integer)
    division = behav.BinaryOperation(behav.Literal(1, integer), behav.Operator('/'),
                                    behav.Literal(0, integer))
    division.ty = integer
    end = behav.BinaryOperation(behav.NamedReference(index), behav.Operator('+'), division)
    end.left.ty = integer
    end.ty = integer
    start = behav.NamedReference(index)
    start.ty = integer
    if array:
        return behav.IndexedReference(target, start, end)
    base = behav.NamedReference(target)
    base.ty = integer
    return behav.SliceOperation(base, start, end)


class RangeConstantNativeTest(unittest.TestCase):
    def test_independent_failures_inside_one_constant_bound(self):
        for array in (False, True):
            for partial in (False, True):
                for operator in ('+', '%'):
                    with self.subTest(array=array, partial=partial, operator=operator):
                        node = access(array)
                        first = node.right.right
                        second = behav.BinaryOperation(first.left, first.op, first.right)
                        second.ty = first.ty
                        pair = behav.BinaryOperation(first, behav.Operator(operator), second)
                        pair.ty = first.ty
                        node.right.right = pair
                        with self.assertRaises(M2ValidationError) as caught:
                            ValidateBehavVisitor().generate(node, ValidatorContext(None, partial=partial))
                        errors = [caught.exception] + caught.exception.related_diagnostics
                        expected = ['DivisionByZero'] * 2 + ([] if partial else ['InvalidRangePattern'])
                        self.assertEqual([e.issue_code.split('.')[-1] for e in errors], expected)

    def test_both_constant_bounds_fail_independently(self):
        for array in (False, True):
            for partial in (False, True):
                with self.subTest(array=array, partial=partial):
                    node = access(array)
                    division = node.right.right
                    if array:
                        node.index = division
                    else:
                        node.left = division
                    node.right = behav.BinaryOperation(division.left, division.op, division.right)
                    node.right.ty = division.ty
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(node, ValidatorContext(None, partial=partial))
                    errors = [caught.exception] + caught.exception.related_diagnostics
                    expected = ['DivisionByZero'] * 2 + ([] if partial else ['InvalidRangePattern'])
                    self.assertEqual([e.issue_code.split('.')[-1] for e in errors], expected)

    def test_division_failure_full_and_partial_for_both_access_forms(self):
        for array in (False, True):
            for partial in (False, True):
                with self.subTest(array=array, partial=partial):
                    node = access(array)
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(node, ValidatorContext(None, partial=partial))
                    errors = [caught.exception] + caught.exception.related_diagnostics
                    expected = ['DivisionByZero'] + ([] if partial else ['InvalidRangePattern'])
                    self.assertEqual([e.issue_code.split('.')[-1] for e in errors], expected)
                    self.assertIsNone(node.ty)

    def test_pure_range_probe_and_reporting_evaluation(self):
        node = access()
        self.assertIsNone(range_size(node.left, node.right))
        with self.assertRaises(ZeroDivisionError):
            range_size(node.left, node.right, suppress_errors=False)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class RangeConstantOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_independent_failures_inside_one_bound(self):
        for owner in ('Core', 'InstructionSet'):
            for declaration in ('unsigned<32> x;', 'unsigned<8> x[4];'):
                for operator in ('+', '%'):
                    with self.subTest(owner=owner, declaration=declaration, operator=operator):
                        output, _ = self.probe(owner + ' C { functions { unsigned<32> f(int i) { '
                                               + declaration + ' return x[i:i+((1/0)'
                                               + operator + '(2/0))]; } } }')
                        self.assertEqual(output.count('ERROR:Division by zero'), 2, output)
                        self.assertEqual(output.count('ERROR:Invalid range pattern'), int(owner == 'Core'), output)
                        self.assertEqual(output.count('ERROR:'), 2 + int(owner == 'Core'), output)

    def test_release_both_constant_bounds_fail(self):
        for owner in ('Core', 'InstructionSet'):
            for declaration in ('unsigned<32> x;', 'unsigned<8> x[4];'):
                with self.subTest(owner=owner, declaration=declaration):
                    output, _ = self.probe(owner + ' C { functions { unsigned<32> f() { '
                                           + declaration + ' return x[(1/0):(2/0)]; } } }')
                    self.assertEqual(output.count('ERROR:Division by zero'), 2, output)
                    self.assertEqual(output.count('ERROR:Invalid range pattern'), int(owner == 'Core'), output)
                    self.assertEqual(output.count('ERROR:'), 2 + int(owner == 'Core'), output)

    def test_release_division_failure_full_and_partial(self):
        for owner in ('Core', 'InstructionSet'):
            for declaration in ('unsigned<32> x;', 'unsigned<8> x[4];'):
                with self.subTest(owner=owner, declaration=declaration):
                    output, _ = self.probe(owner + ' C { functions { unsigned<32> f(int i) { '
                                           + declaration + ' return x[i:i+(1/0)]; } } }')
                    self.assertEqual(output.count('ERROR:Division by zero'), 1, output)
                    self.assertEqual(output.count('ERROR:Invalid range pattern'), int(owner == 'Core'), output)
                    self.assertEqual(output.count('ERROR:'), 1 + int(owner == 'Core'), output)
                    self.assertNotIn('internal error', output.lower(), output)
