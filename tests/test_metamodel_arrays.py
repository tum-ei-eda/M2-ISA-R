"""Standalone array assignments, tensor shapes and saved-model validation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, type_info
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsManager


def integer(width=32):
    return type_info.PrimitiveType(type_info.TypeKind.INT, width)


def array(count, width=32):
    return type_info.ArrayType(integer(width), count)


def reference(ty):
    node = behav.NamedReference(None)
    node.ty = ty
    return node


CASES = [
    ('int x[2]; int y[2]; x=y;', array(2), array(2), None),
    ('int x[2]; int y[3]; x=y;', array(2), array(3), 'Cannot implicitly convert signed<32>[3] to signed<32>[2]'),
    ('int x[2]; signed<16> y[2]; x=y;', array(2), array(2, 16), 'Cannot implicitly convert signed<16>[2] to signed<32>[2]'),
    ('int x[2]; int y; x=y;', array(2), integer(), 'Cannot implicitly convert signed<32> to signed<32>[2]'),
    ('int x; int y[2]; x=y;', integer(), array(2), 'Cannot implicitly convert signed<32>[2] to signed<32>'),
]


class MetamodelArrayNativeTest(unittest.TestCase):
    def test_array_assignment_types(self):
        for text, target, source, error in CASES:
            with self.subTest(source=text):
                node = behav.Assignment(reference(target), reference(source))
                if error is None:
                    ValidateBehavVisitor().generate(node, WarningsManager(None))
                else:
                    with self.assertRaises(M2ValidationError) as exc:
                        ValidateBehavVisitor().generate(node, WarningsManager(None))
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidAssignmentType')
                    self.assertIn(error, str(exc.exception))

    def test_tensor_shapes(self):
        for values, ty, valid in (([1, 2], array(2), True), ([1], array(2), False),
                                  ([[1, 2], [3, 4]], type_info.ArrayType(array(2), 2), True),
                                  ([[1, 2]], type_info.ArrayType(array(2), 2), False)):
            with self.subTest(values=values, valid=valid):
                node = behav.Tensor(values, ty)
                if valid:
                    ValidateBehavVisitor().generate(node, WarningsManager(None))
                else:
                    with self.assertRaises(M2ValidationError) as exc:
                        ValidateBehavVisitor().generate(node, WarningsManager(None))
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidAssignmentType')
                    self.assertIn('List initializer size does not match LHS size', str(exc.exception))

    def test_saved_array_models(self):
        for body, issue in (('int x[2]; int y[2]; x=y;', None),
                            ('int x[2]; if (x) {}', 'NonScalarCondition'),
                            ('int x[2]; int y[3]; x=y;', 'InvalidAssignmentType')):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'array.core_desc'
                path.write_text('Core C { functions { void f() { ' + body + ' } } }')
                parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                         str(Path(directory) / 'gen_model' / 'array.m2isarmodel')],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, int(issue is not None), result.stdout)
                if issue:
                    self.assertIn('com.minres.coredsl.' + issue, result.stdout)
                else:
                    result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser',
                                             str(path), '--validate'], text=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('Traceback', result.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelArrayOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_array_assignment_types(self):
        for text, target, source, error in CASES:
            with self.subTest(source=text):
                output, _ = self.probe('Core C { functions { void f() { ' + text + ' } } }')
                node = behav.Assignment(reference(target), reference(source))
                if error is None:
                    self.assertNotIn('ERROR:', output, output)
                    ValidateBehavVisitor().generate(node, WarningsManager(None))
                else:
                    self.assertIn('ERROR:' + error, output, output)
                    with self.assertRaises(M2ValidationError):
                        ValidateBehavVisitor().generate(node, WarningsManager(None))
