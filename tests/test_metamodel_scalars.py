"""Release scalar conversions and constant exceptions in saved models."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, type_info
from m2isar.transforms.validate_behav.validate import ValidatorContext
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.transforms.validate_behav.constants import constant_value, INDETERMINATE


def ty(width, signed=False):
    return type_info.PrimitiveType(type_info.TypeKind.INT if signed else type_info.TypeKind.UINT, width)


def reference(dtype):
    node = behav.NamedReference(None)
    node.ty = dtype
    return node


# text, target, source type, literal value (None means a variable), permitted
CASES = [
    ('int x; unsigned int y; x=y;', ty(32, True), ty(32), None, False),
    ('unsigned int x; int y; x=y;', ty(32), ty(32, True), None, False),
    ('unsigned<8> x; unsigned<16> y; x=y;', ty(8), ty(16), None, False),
    ('signed<16> x; unsigned<8> y; x=y;', ty(16, True), ty(8), None, True),
    ('signed<8> x; unsigned<8> y; x=y;', ty(8, True), ty(8), None, False),
    ("unsigned<8> x=8'sd1;", ty(8), ty(8, True), 1, True),
    ('unsigned<8> x=-1;', ty(8), ty(2, True), -1, False),
    ("signed<8> x=8'd127;", ty(8, True), ty(8), 127, True),
    ("signed<8> x=8'd128;", ty(8, True), ty(8), 128, False),
    ("unsigned<4> x=8'd15;", ty(4), ty(8), 15, True),
    ("unsigned<4> x=8'd16;", ty(4), ty(8), 16, False),
]


def assignment(target, source, value):
    return behav.Assignment(reference(target), reference(source) if value is None else behav.Literal(value, source))


class MetamodelScalarNativeTest(unittest.TestCase):
    def test_scalar_conversion_rules(self):
        for text, target, source, value, allowed in CASES:
            with self.subTest(source=text):
                node = assignment(target, source, value)
                if allowed:
                    ValidateBehavVisitor().generate(node, ValidatorContext(None))
                else:
                    with self.assertRaises(M2ValidationError) as exc:
                        ValidateBehavVisitor().generate(node, ValidatorContext(None))
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidAssignmentType')

    def test_constant_evaluation_and_partial_parameters(self):
        left, right = behav.Literal(-7, ty(4, True)), behav.Literal(2, ty(2))
        division = behav.BinaryOperation(left, behav.Operator('/'), right)
        division.ty = ty(4, True)
        self.assertEqual(constant_value(division), -3)
        ValidateBehavVisitor().generate(behav.Assignment(reference(ty(3, True)), division), ValidatorContext(None))
        division.right = behav.Literal(0, ty(1))
        with self.assertRaises(M2ValidationError) as exc:
            ValidateBehavVisitor().generate(behav.Assignment(reference(ty(3, True)), division), ValidatorContext(None))
        self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.DivisionByZero')
        parameter = arch.Parameter('N', None, {}, size=32, signed=True)
        node = behav.NamedReference(parameter)
        node.ty = ty(32, True)
        self.assertIs(constant_value(node), INDETERMINATE)
        with self.assertLogs('validate_behav', level='INFO') as logs:
            ValidateBehavVisitor().generate(behav.Assignment(reference(ty(8)), node), ValidatorContext(None, partial=True))
        self.assertIn('com.minres.coredsl.ValidConstantAssignment', logs.output[0])
        with self.assertRaises(M2ValidationError):
            ValidateBehavVisitor().generate(behav.Assignment(reference(ty(8)), node), ValidatorContext(None))
        parameter._value = behav.NamedReference(parameter)
        self.assertIs(constant_value(node), INDETERMINATE)

    def test_saved_scalar_models(self):
        for text, _, _, _, allowed in CASES:
            with self.subTest(source=text), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'scalar.core_desc'
                path.write_text('Core C { functions { void f() { ' + text + ' } } }')
                parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                         str(Path(directory) / 'gen_model' / 'scalar.m2isarmodel')],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, int(not allowed), result.stdout)
                if not allowed:
                    self.assertIn('com.minres.coredsl.InvalidAssignmentType', result.stdout)
                self.assertNotIn('Traceback', result.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelScalarOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_scalar_conversions(self):
        for text, target, source, value, allowed in CASES:
            with self.subTest(source=text):
                output, _ = self.probe('Core C { functions { void f() { ' + text + ' } } }')
                node = assignment(target, source, value)
                if allowed:
                    self.assertNotIn('ERROR:', output, output)
                    ValidateBehavVisitor().generate(node, ValidatorContext(None))
                else:
                    with self.assertRaises(M2ValidationError) as exc:
                        ValidateBehavVisitor().generate(node, ValidatorContext(None))
                    self.assertIn('ERROR:' + str(exc.exception).split(' [', 1)[0], output, output)
        output, _ = self.probe('InstructionSet I { architectural_state { int N; } functions { void f() { unsigned<8> x=N; } } }')
        self.assertNotIn('ERROR:', output, output)
        node = behav.NamedReference(arch.Parameter('N', None, {}, size=32, signed=True))
        node.ty = ty(32, True)
        with self.assertLogs('validate_behav', level='INFO') as logs:
            ValidateBehavVisitor().generate(behav.Assignment(reference(ty(8)), node), ValidatorContext(None, partial=True))
        self.assertIn('com.minres.coredsl.ValidConstantAssignment', logs.output[0])
