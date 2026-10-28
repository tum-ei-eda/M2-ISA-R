"""Ternaries analyze all children before checking condition and option types."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


CASES = [
    ('h(g(0)?g(1):g(2),0);',
     ['InvalidArgumentCount'] * 3 + ['NonScalarCondition', 'InvalidArgumentType']),
    ('int x=g(0)?g(1):1;',
     ['InvalidArgumentCount'] * 2 + ['NonScalarCondition', 'IncompatibleOptionTypes']),
    ('int x=g()?g(0):1;',
     ['InvalidArgumentCount', 'NonScalarCondition', 'IncompatibleOptionTypes']),
    ('int x=offsetof(int)?g(0):g(1);',
     ['UnknownIntrinsicFunction'] + ['InvalidArgumentCount'] * 2 + ['InvalidAssignmentType']),
    ('int x=g()?offsetof(int):g(0);',
     ['UnknownIntrinsicFunction', 'InvalidArgumentCount', 'NonScalarCondition']),
    ('if(g(0)?g(1):g(2)) { g(3); }',
     ['InvalidArgumentCount'] * 3 + ['NonScalarCondition'] * 2 + ['InvalidArgumentCount']),
    ('int x=g(0);', ['InvalidArgumentCount', 'InvalidAssignmentType']),
]
PARTIAL = ('InstructionSet I { architectural_state { int N; } functions { '
           'void f() { int a[N]; int x=a?1:2; int y=1?a:2; } } }')


def source(body):
    return ('Core C { functions { void g() {} void h(int a,int b) {} '
            'void f() { ' + body + ' } } }')


class SourceTernaryCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_ternary_child_and_own_error_order(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_partial_and_valid_ternaries(self):
        self.validate(PARTIAL)
        self.validate(source('int x=1?2:3; h(0?1:2,x);'))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceTernaryCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_ternary_diagnostic_counts(self):
        messages = {
            'InvalidArgumentCount': 'Incorrect argument count.',
            'NonScalarCondition': 'The condition must be a scalar type',
            'IncompatibleOptionTypes': 'Incompatible option types:',
            'UnknownIntrinsicFunction': 'Unknown intrinsic function',
        }
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                for code, message in messages.items():
                    self.assertEqual(output.count('ERROR:' + message), expected.count(code), output)
                self.assertEqual(output.count('ERROR:Cannot implicitly convert'),
                                 expected.count('InvalidArgumentType') + expected.count('InvalidAssignmentType'), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_partial_and_valid_ternaries(self):
        for text in (PARTIAL, source('int x=1?2:3; h(0?1:2,x);')):
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertNotIn('ERROR:', output)
