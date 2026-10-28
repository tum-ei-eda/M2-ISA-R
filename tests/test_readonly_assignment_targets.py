"""Readonly writes fail through source and saved-model validation alike."""
import os
import subprocess
import sys
import tempfile
import unittest

import test_continue_regression as saved_helpers
import test_isa_alias_parity as harness
import test_source_unary_collection as unary_helpers
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError
from m2isar.transforms.validate_behav.validate import validate_behav


TARGETS = [(declaration, '', target) for declaration, target in unary_helpers.READONLY_TARGETS]
TARGETS += [('', 'const unsigned<8> x=1;', target) for target in ('x', 'x[3:0]')]


def cases():
    for declaration, local, target in TARGETS:
        for operator in ('=', '+='):
            for readonly in (True, False):
                state_declaration = declaration if readonly else declaration.replace('const ', '')
                local_declaration = local if readonly else local.replace('const ', '')
                state = 'architectural_state { ' + state_declaration + ' } ' if state_declaration else ''
                yield readonly, ('Core C { ' + state + 'functions { void f() { ' + local_declaration +
                                 target + operator + '1; } } }')


class ReadonlyAssignmentNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_source_readonly_writes_and_writable_controls(self):
        for readonly, text in cases():
            with self.subTest(source=text):
                if readonly:
                    with self.assertRaises(M2ValidationError) as caught:
                        self.validate(text)
                    self.assertEqual(codes(caught.exception), ['InvalidAssignmentTarget'])
                else:
                    self.validate(text)

    def test_saved_readonly_writes_without_source_validation(self):
        for readonly, text in cases():
            with self.subTest(source=text), tempfile.TemporaryDirectory() as directory:
                model, saved = saved_helpers.parse_model(text, directory)
                if readonly:
                    with self.assertRaises(M2ValidationError) as caught:
                        validate_behav(model, None)
                    self.assertEqual(codes(caught.exception), ['InvalidAssignmentTarget'])
                else:
                    validate_behav(model, None)
                result = subprocess.run(
                    [sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, int(readonly), result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                if readonly:
                    self.assertIn('com.minres.coredsl.InvalidAssignmentTarget', result.stderr)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class ReadonlyAssignmentOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_readonly_diagnostic_counts(self):
        for readonly, text in cases():
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertEqual(output.count('ERROR:Cannot assign to constant'), int(readonly), output)
                self.assertEqual(output.count('ERROR:'), int(readonly), output)
