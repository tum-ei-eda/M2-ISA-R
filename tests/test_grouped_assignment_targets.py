"""MINRES permits grouping values, but rejects grouping assignment targets."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
import test_continue_regression as saved_helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError
from m2isar.transforms.validate_behav.validate import validate_behav


INVALID = [
    '(x)=1;', '(x)+=1;', '++(x);', '--(x);', '(x)++;', '(x)--;',
    '(x[7:4])[2:1]++;', '++(x[7:4])[2:1];',
    '(x)[3:0]=1;', '((x))=1;', '(a)[0]=1;', '(a[0])++;',
]
VALID = ['x=(x);', 'x+=(x);', 'x[7:4][2:1]++;',
         '++x[7:4][2:1];', 'a[0]=1;', 'a[0]++;', 'x=(a)[0];', 'x=((a))[0];']


def source(statement):
    return ('Core C { functions { void f() { unsigned<8> x=1; '
            'unsigned<8> a[2]; ' + statement + ' } } }')


class GroupedAssignmentTargetNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_emitted_source_preserves_grouped_array_base(self):
        from m2isar.backends.coredsl2.visitor import CDSLWriterVisitor
        class ArrayWriter(saved_helpers.CWriter):
            def write_array(self, array):
                self.write('{' + ','.join(str(value) for value in array.flat) + '}')
        with tempfile.TemporaryDirectory() as directory:
            model, _ = saved_helpers.parse_model(source('(a)[0]=1;'), directory)
            writer = ArrayWriter()
            CDSLWriterVisitor().generate(model.cores['C'].functions['f'].operation, writer)
            self.assertIn('(a)[0]', ''.join(writer.parts))

    def test_saved_grouped_targets_without_source_validation(self):
        for statement in INVALID + VALID:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as directory:
                model, saved = saved_helpers.parse_model(source(statement), directory)
                invalid = statement in INVALID
                if invalid:
                    with self.assertRaises(M2ValidationError) as caught:
                        validate_behav(model, None)
                    self.assertEqual(codes(caught.exception), ['InvalidAssignmentTarget'])
                else:
                    validate_behav(model, None)
                result = subprocess.run(
                    [sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, int(invalid), result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                if invalid:
                    self.assertIn('com.minres.coredsl.InvalidAssignmentTarget', result.stderr)

    def test_grouped_targets_rejected_but_grouped_values_accepted(self):
        for statement in INVALID:
            with self.subTest(statement=statement):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(statement))
                self.assertEqual(codes(caught.exception), ['InvalidAssignmentTarget'])
        for statement in VALID:
            with self.subTest(statement=statement):
                self.validate(source(statement))


@unittest.skipUnless(shutil.which('g++'), 'g++ required for generated-code execution')
class GroupedArrayReadExecutionTest(unittest.TestCase):
    def test_grouped_array_reads_execute(self):
        from test_increment_regression import compile_run, context
        from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
        for expression in ('(a)[0]', '((a))[0]', '(a)[0][3:0]'):
            expected = 10 if expression.endswith('[3:0]') else 42
            with self.subTest(expression=expression), tempfile.TemporaryDirectory() as directory:
                text = saved_helpers.source('unsigned<8> a[2];a[0]=42;return ' + expression + ';', 'int')
                model, _ = saved_helpers.parse_model(text, directory, validated=True)
                generated = InstructionTransformVisitor().generate(
                    model.cores['C'].functions['f'].operation, context())
                compile_run(self, 'int f(){\n' + generated.initial_required + '\n}\n'
                            'int main(){return f()==' + str(expected) + '?0:1;}', directory)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class GroupedAssignmentTargetOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_grouped_target_diagnostics(self):
        for statement in INVALID + VALID:
            with self.subTest(statement=statement):
                output, _ = self.probe(source(statement))
                expected = int(statement in INVALID)
                self.assertEqual(output.count('ERROR:Invalid assignment target'), expected, output)
                self.assertEqual(output.count('ERROR:'), expected, output)
