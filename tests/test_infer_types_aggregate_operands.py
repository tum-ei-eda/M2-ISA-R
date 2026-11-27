"""Aggregate operands of scalar operators are reported with a source location.

Type inference rejects operations whose result type cannot be computed for an
aggregate operand. Operations with a fixed unsigned<1> result (comparisons,
logical operators) are left to the behavior validator.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, load_model, type_info
from m2isar.metamodel.code_info import LineInfo
from m2isar.transforms.infer_types.visitor import InferTypesMutator
from m2isar.transforms.validate_behav.validate import validate_behav
from m2isar.warnings import WarningsManager


def source(statement):
    # The statement under test is always on line 4.
    return ('Core C {\n'
            '    functions {\n'
            '        void f(unsigned<32> x) { unsigned<32> tmp[4]; unsigned<32> other[4]; unsigned<32> short_[3];\n'
            f'            {statement}\n'
            '        }\n'
            '    }\n'
            '}\n')


INFERENCE_ERRORS = (
    ('unsigned<32> r = tmp + x;', 'Operation is only valid on integer types'),
    ('unsigned<32> r = x - tmp;', 'Operation is only valid on integer types'),
    ('unsigned<32> r = tmp << 1;', 'Operation is only valid on integer types'),
    ('unsigned<32> r = -tmp;', 'Unary operators are only valid on integer types'),
    ('unsigned<1> r = !tmp;', 'Logical not is only valid on scalar types'),
    ('unsigned<64> r = tmp :: x;', 'Concatenation is only valid on integer types'),
)

VALIDATION_ERRORS = (
    ('unsigned<1> r = tmp == x;', 'Operation is only valid on integer types'),
    ('unsigned<1> r = x != tmp;', 'Operation is only valid on integer types'),
    ('unsigned<1> r = tmp < other;', 'Operation is only valid on integer types'),
    ('unsigned<1> r = tmp == short_;', 'Operation is only valid on integer types'),
    ('unsigned<1> r = tmp && x;', 'Logical operators are only valid on scalar types'),
)

VALID = (
    'unsigned<33> r = tmp[1] + x;',
    'unsigned<1> r = tmp == other;',
    'unsigned<1> r = tmp != other;',
)


def run_parser(directory, text, *flags):
    path = Path(directory) / 'aggregate.core_desc'
    path.write_text(text)
    result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path), *flags],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result, Path(directory) / 'gen_model' / 'aggregate.m2isarmodel'


class InferTypesAggregateOperandTest(unittest.TestCase):
    def test_inference_reports_location_without_validate(self):
        # --validate is off by default, so type inference is the only check that runs.
        for statement, message in INFERENCE_ERRORS:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as directory:
                result, _ = run_parser(directory, source(statement))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn('Traceback', result.stdout)
                self.assertIn(f'{message} [com.minres.coredsl.InvalidOperationType]', result.stdout)
                self.assertIn('aggregate.core_desc:4', result.stdout)

    def test_behavior_validator_reports_location(self):
        for statement, message in VALIDATION_ERRORS:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as directory:
                result, model_path = run_parser(directory, source(statement))
                self.assertEqual(result.returncode, 0, result.stdout)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_behav(load_model(model_path), None)
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidOperationType')
                self.assertIn(message, str(exc.exception))
                self.assertEqual(exc.exception.line_info.start_line_no, 4)

    def test_validate_flag_reports_location(self):
        for statement, message in INFERENCE_ERRORS[:1] + VALIDATION_ERRORS:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as directory:
                result, _ = run_parser(directory, source(statement), '--validate')
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn('Traceback', result.stdout)
                self.assertIn(f'{message} [com.minres.coredsl.InvalidOperationType]', result.stdout)
                self.assertIn('aggregate.core_desc:4', result.stdout)

    def test_valid_aggregate_uses(self):
        for statement in VALID:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as directory:
                result, model_path = run_parser(directory, source(statement), '--validate')
                self.assertEqual(result.returncode, 0, result.stdout)
                validate_behav(load_model(model_path), None)

    def test_location_falls_back_to_operand(self):
        line_info = LineInfo('aggregate.core_desc', 0, 1, 7, 7)
        array = behav.NamedReference(arch.Variable('tmp', type_info.ArrayType(
            type_info.PrimitiveType(type_info.TypeKind.UINT, 32), 4)), line_info)
        scalar = behav.Literal(1, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
        node = behav.BinaryOperation(array, behav.Operator('+'), scalar)  # e.g. synthesized by a transform
        with self.assertRaises(M2ValidationError) as exc:
            InferTypesMutator().generate(node, WarningsManager(None))
        self.assertIs(exc.exception.line_info, line_info)
        self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidOperationType')


if __name__ == '__main__':
    unittest.main()
