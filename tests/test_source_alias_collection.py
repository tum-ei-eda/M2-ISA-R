"""Alias type and source restrictions produce independent diagnostics."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError
from m2isar.warnings import WarningsInfo

A = 'InvalidAssignmentType'
S = 'InvalidAliasSource'
C = 'InvalidAliasConstness'
CASES = [
    ('register const unsigned<8> R; unsigned<16> &A=R[7:0];', [A, C]),
    ('const unsigned<8> N=1; unsigned<16> &A=N[7:0];', [A, S, C]),
    ('const unsigned<8> N=1; unsigned<8> &A=N;', [S, C]),
]
BOUNDS = [
    ('const unsigned<8> N=1; unsigned<2> &A=N[9:8];', [S, C]),
    ('register const unsigned<8> R; unsigned<2> &A=R[9:8];', [C]),
]
VALID = 'register const unsigned<8> R; const unsigned<8> &A=R[7:0];'

def source(state):
    return 'Core C { architectural_state { ' + state + ' } }'

class SourceAliasCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_independent_alias_errors(self):
        for state, expected in CASES:
            with self.subTest(state=state):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(state))
                self.assertEqual(codes(caught.exception), expected)

    def test_bounds_warnings_survive_source_errors(self):
        for state, expected in BOUNDS:
            with self.subTest(state=state), self.assertLogs('validate_source') as logs:
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(state))
                self.assertEqual(codes(caught.exception), expected)
            warnings = [line for line in logs.output if 'com.minres.coredsl.IndexOutOfRange' in line]
            self.assertEqual(len(warnings), 2)
            self.assertIn('9 >= 8', warnings[0])
            self.assertIn('8 >= 8', warnings[1])

    def test_suppressed_bounds_warnings_preserve_errors(self):
        for state, expected in BOUNDS:
            with self.subTest(state=state), self.assertNoLogs('validate_source', level='WARNING'):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(state), WarningsInfo(disabled={'index-out-of-range'}))
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_matching_const_alias(self):
        self.validate(source(VALID))

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceAliasCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_independent_alias_errors(self):
        messages = {A: 'Alias must be initialized with exactly the same type',
                    S: 'Cannot define an alias to', C: 'Cannot define a non-const alias'}
        for state, expected in CASES:
            with self.subTest(state=state):
                output, _ = self.probe(source(state))
                for issue, message in messages.items():
                    self.assertEqual(output.count('ERROR:' + message), expected.count(issue), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)
                positions = [output.index('ERROR:' + messages[issue]) for issue in expected]
                self.assertEqual(positions, sorted(positions), output)

    def test_release_bounds_warnings_and_source_errors(self):
        for state, expected in BOUNDS:
            with self.subTest(state=state):
                output, _ = self.probe(source(state))
                self.assertEqual(output.count('ERROR:Cannot define an alias to'), expected.count(S), output)
                self.assertEqual(output.count('ERROR:Cannot define a non-const alias'), expected.count(C), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)
                self.assertEqual(output.count('WARNING:Index out of range'), 2, output)
                self.assertIn('WARNING:Index out of range (9 >= 8)', output)
                self.assertIn('WARNING:Index out of range (8 >= 8)', output)

    def test_release_valid_matching_const_alias(self):
        output, _ = self.probe(source(VALID))
        self.assertNotIn('ERROR:', output)
