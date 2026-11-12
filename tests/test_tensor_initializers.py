"""Preserve initializer types for standalone tensor conversion diagnostics."""
import os
from pathlib import Path
import shutil
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
from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
from m2isar.backends.etiss.instruction_utils import TransformerContext


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
    def test_constant_expressions_in_array_initializers(self):
        body = ("unsigned<64> x[8]={(unsigned<64>)(signed<64>)(-1), "
                "(unsigned<64>)(2+3), (unsigned<64>)W, (unsigned<64>)(~8'h0), (unsigned<64>)(!0), "
                "(unsigned<64>)(7%4), (unsigned<64>)(0 && (1/0)), (unsigned<64>)(1 ? 2 : 3)};")
        for frontend, kind in (('coredsl2', 'Core'), ('coredsl2_set', 'InstructionSet')):
            for validate in (False, True):
                with self.subTest(frontend=frontend, validate=validate), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'tensor.core_desc'
                    path.write_text(f'{kind} C {{ architectural_state {{ int W=8; }} functions {{ void f() {{ {body} }} }} }}')
                    command = [sys.executable, '-m', f'm2isar.frontends.{frontend}.parser', str(path)]
                    if validate:
                        command.append('--validate')
                    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertEqual(result.returncode, 0, result.stdout)
                    model_path = Path(directory) / 'gen_model' / 'tensor.m2isarmodel'
                    model = load_model(model_path)
                    definition = model.cores['C'] if frontend == 'coredsl2' else model.sets['C']
                    tensor = definition.functions['f'].operation.statements[0].statements[0].expr
                    self.assertEqual(tensor.value.tolist(), [(1 << 64) - 1, 5, 8, 255, 1, 3, 0, 2])
                    self.assertEqual(len(tensor.initializer_elements), 8)
                    checked = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                              str(model_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertEqual(checked.returncode, 0, checked.stdout)
                    context = TransformerContext({}, {}, {}, {}, {}, {}, [], {}, 32, 64,
                                                 'C', False, {}, False)
                    code = InstructionTransformVisitor().generate(tensor, context).code
                    self.assertIn('18446744073709551615ULL', code)
                    self.assertIn('255ULL', code)

    def test_expression_initializer_diagnostics(self):
        for body, error in (("unsigned<8> x[1]={(signed<8>)(-1)};", 'Cannot implicitly convert'),
                            ("unsigned<8> x[1]={(unsigned<16>)1};", 'Cannot implicitly convert'),
                            ("unsigned<8> x[1]={1+2, (unsigned<8>)3};", 'List initializer size does not match')):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                path, _ = lower(self, directory, body)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                         str(path), '-Wno-error=implicit-trunc'],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(error, result.stdout)
                self.assertNotIn('Traceback', result.stdout)

    def test_nested_or_nonconstant_initializer_fails_cleanly(self):
        for body in ('int x[1]={{1}};', 'int a=1; int x[1]={a};',
                     'int a[1]={1}; int x[1]={a[0]};'):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'tensor.core_desc'
                path.write_text(source(body))
                result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stdout)

    def test_indexed_register_is_not_folded_to_reset_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tensor.core_desc'
            path.write_text('Core C { architectural_state { register unsigned<8> R[1]={42}; } '
                            'functions { void f() { unsigned<8> x[1]={R[0]}; } } }')
            result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('constant expressions', result.stdout)
            self.assertNotIn('Traceback', result.stdout)

    def test_shift_initializer_obeys_operand_width(self):
        with tempfile.TemporaryDirectory() as directory:
            _, model = lower(self, directory, "unsigned<8> x[2]={8'h80 << 1, 8'hff >> 8};")
            tensor = model.cores['C'].functions['f'].operation.statements[0].statements[0].expr
            self.assertEqual(tensor.value.tolist(), [0, 0])

    @unittest.skipUnless(shutil.which('c++'), 'C++ compiler required')
    def test_signed_wide_initializer_compiles_without_narrowing(self):
        with tempfile.TemporaryDirectory() as directory:
            _, model = lower(self, directory, "signed<128> x[1]={(signed<128>)(-64'h8000000000000000)};")
            tensor = model.cores['C'].functions['f'].operation.statements[0].statements[0].expr
            context = TransformerContext({}, {}, {}, {}, {}, {}, [], {}, 32, 64, 'C', False, {}, False)
            code = InstructionTransformVisitor().generate(tensor, context).code
            path = Path(directory) / 'initializer.cpp'
            path.write_text('typedef __int128 etiss_int128; typedef unsigned __int128 etiss_uint128;\n'
                            f'int main() {{ etiss_int128 a[1]={code}; return a[0] != -((etiss_int128)1 << 63); }}\n')
            executable = Path(directory) / 'initializer'
            result = subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', '-Werror', str(path), '-o', str(executable)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(subprocess.run([str(executable)]).returncode, 0)

    def test_etiss_cli_generates_expression_initializer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tensor.core_desc'
            path.write_text('''Core C {
                architectural_state {
                    int XLEN=64; register unsigned<64> X[2]; register unsigned<64> PC [[is_pc]];
                }
                functions {
                    unsigned<64> f() {
                        unsigned<64> a[2]={(unsigned<64>)(signed<64>)(-1), (unsigned<64>)(2+3)};
                        return a[1];
                    }
                }
            }''')
            parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path), '--validate'],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(parsed.returncode, 0, parsed.stdout)
            result = subprocess.run([sys.executable, '-m', 'm2isar.backends.etiss.writer',
                                     str(Path(directory) / 'gen_model' / 'tensor.m2isarmodel')],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            output = '\n'.join(file.read_text() for file in (Path(directory) / 'gen_output').rglob('*Funcs.c'))
            self.assertIn('18446744073709551615ULL', output)
            self.assertIn('5ULL', output)

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
