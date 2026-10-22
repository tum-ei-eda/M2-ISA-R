"""Preserve initializer types for standalone tensor conversion diagnostics."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness
from test_metamodel_collection import flatten
from m2isar.metamodel import load_model, behav, type_info
from m2isar.transforms.infer_types.visitor import InferTypesMutator
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.transforms.validate_behav.validate import ValidatorContext
from m2isar.transforms.validate_behav.validate import validate_behav
from m2isar.diagnostics import M2ValidationError


CASES = [
    ('unsigned<8> x[1]={256};', 'Cannot implicitly convert unsigned<9> to unsigned<8>'),
    ('unsigned<8> x[1]={-1};', 'Cannot implicitly convert signed<2> to unsigned<8>'),
    ('signed<8> x[1]={128};', 'Cannot implicitly convert unsigned<8> to signed<8>'),
    ('signed<8> x[1]={127};', None),
    ("signed<8> x[1]={8'd127};", None),
    ("unsigned<4> x[1]={8'd15};", None),
    ("unsigned<8> x[1]={8'sd255};", 'Cannot implicitly convert signed<8> to unsigned<8>'),
    ("unsigned<8> x[1]={-8'sd1};", 'Cannot implicitly convert signed<9> to unsigned<8>'),
    ('signed<8> x[1]={-1};', None),
    ('unsigned<8> x[1]={+1};', None),
    ('unsigned<8> x[1]={~1};', None),
    ("unsigned<4> x[1]={+8'd15};", 'Cannot implicitly convert unsigned<8> to unsigned<4>'),
]


COLLECTION = [
    ('unsigned<8> x[2]={256,257};', 2, 0),
    ('unsigned<8> x[1]={256,257};', 2, 1),
    ('signed<8> x[3]={128,127,128};', 2, 0),
    ("unsigned<8> x[3]={16'd255,256,257};", 2, 0),
]


def source(body):
    return 'Core C { functions { void f() { ' + body + ' } } }'


def lower(test, directory, body):
    path = Path(directory) / 'tensor.core_desc'
    path.write_text(source(body))
    result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    test.assertEqual(result.returncode, 0, result.stdout)
    model_path = Path(directory) / 'gen_model' / 'tensor.m2isarmodel'
    return model_path, load_model(model_path)


class TensorInitializerNativeTest(unittest.TestCase):
    def test_unknown_shape_does_not_hide_element_errors(self):
        ty = type_info.ArrayType(type_info.PrimitiveType(type_info.TypeKind.UINT, 8), None)
        element = behav.Literal(256, type_info.PrimitiveType(type_info.TypeKind.UINT, 9))
        tensor = behav.Tensor([256], ty, initializer_elements=[element])
        with self.assertRaises(M2ValidationError) as caught:
            ValidateBehavVisitor().generate(tensor, ValidatorContext(None))
        self.assertEqual(len(flatten(caught.exception)), 1)
        self.assertIn('unsigned<9> to unsigned<8>', str(caught.exception))

    def test_saved_initializer_collection(self):
        for body, conversions, shapes in COLLECTION:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                path, model = lower(self, directory, body)
                with self.assertRaises(M2ValidationError) as caught:
                    validate_behav(model, None)
                errors = flatten(caught.exception)
                self.assertEqual(len(errors), conversions + shapes)
                self.assertTrue(all(e.issue_code == 'com.minres.coredsl.InvalidAssignmentType' for e in errors))
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(result.stdout.count('Cannot implicitly convert'), conversions, result.stdout)
                self.assertEqual(result.stdout.count('List initializer size does not match LHS size'), shapes, result.stdout)
                self.assertNotIn('Traceback', result.stdout)

    def test_legacy_tensor_without_initializer_metadata(self):
        tensor = behav.Tensor([1], type_info.ArrayType(type_info.PrimitiveType(type_info.TypeKind.UINT, 8), 1))
        del tensor.initializer_elements
        InferTypesMutator().generate(tensor, ValidatorContext(None))
        ValidateBehavVisitor().generate(tensor, ValidatorContext(None))

    def test_saved_initializer_conversions(self):
        for body, error in CASES:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                path, model = lower(self, directory, body)
                tensor = model.cores['C'].functions['f'].operation.statements[0].statements[0].expr
                self.assertEqual(len(tensor.initializer_elements), 1)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, int(error is not None), result.stdout)
                if error:
                    self.assertIn(error, result.stdout)
                    self.assertIn('com.minres.coredsl.InvalidAssignmentType', result.stdout)
                self.assertNotIn('Traceback', result.stdout)

    def test_explicit_width_and_unary_type_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            _, model = lower(self, directory, "unsigned<8> x[1]={-8'sd1};")
            tensor = model.cores['C'].functions['f'].operation.statements[0].statements[0].expr
            element = tensor.initializer_elements[0]
            self.assertEqual(element.ty.size, 9)
            self.assertEqual(element.right.ty.size, 8)
            self.assertIsNotNone(element.line_info)
            with self.assertRaises(M2ValidationError) as exc:
                validate_behav(model, None)
            self.assertIs(exc.exception.line_info, element.line_info)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class TensorInitializerOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_initializer_collection(self):
        for body, conversions, shapes in COLLECTION:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                self.assertEqual(output.count('ERROR:Cannot implicitly convert'), conversions, output)
                self.assertEqual(output.count('ERROR:List initializer size does not match LHS size'), shapes, output)
                self.assertEqual(output.count('ERROR:'), conversions + shapes, output)

    def test_release_and_saved_initializer_conversions(self):
        for body, error in CASES:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                output, _ = self.probe(source(body))
                _, model = lower(self, directory, body)
                if error:
                    self.assertIn('ERROR:' + error, output, output)
                    with self.assertRaises(M2ValidationError) as exc:
                        validate_behav(model, None)
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidAssignmentType')
                    self.assertIn(error, str(exc.exception))
                else:
                    self.assertNotIn('ERROR:', output, output)
                    validate_behav(model, None)
