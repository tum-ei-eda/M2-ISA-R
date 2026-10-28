"""Conditions, all branches and loop bodies retain independent source errors."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


CASES = [
    ('if(g(0)) { g(1); } else { g(2); }',
     ['InvalidArgumentCount', 'NonScalarCondition'] + ['InvalidArgumentCount'] * 2),
    ('int a[2]; if(a) g(0); else g(1);',
     ['NonScalarCondition', 'InvalidArgumentCount', 'InvalidArgumentCount']),
    ('if(g(0)) g(1); else if(g(2)) g(3); else g(4);',
     ['InvalidArgumentCount', 'NonScalarCondition', 'InvalidArgumentCount',
      'InvalidArgumentCount', 'NonScalarCondition', 'InvalidArgumentCount', 'InvalidArgumentCount']),
    ('while(g(0)) { g(1); g(2); }',
     ['InvalidArgumentCount', 'NonScalarCondition'] + ['InvalidArgumentCount'] * 2),
    ('do { g(1); g(2); } while(g(0));',
     ['InvalidArgumentCount', 'NonScalarCondition'] + ['InvalidArgumentCount'] * 2),
    ('for(;g(0);) { g(1); }',
     ['InvalidArgumentCount', 'NonScalarCondition', 'InvalidArgumentCount']),
    ('if(offsetof(int)) { g(0); } else { g(1); }',
     ['UnknownIntrinsicFunction', 'InvalidArgumentCount', 'InvalidArgumentCount']),
]
PARTIAL = ('InstructionSet I { architectural_state { int N; } functions { '
           'void f() { int a[N]; if(a) {} while(a) {} do {} while(a); '
           'for(;a;) {} } } }')


def source(body):
    return 'Core C { functions { void g() {} void f() { ' + body + ' } } }'


class SourceBranchCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_condition_branch_and_loop_error_order(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_partial_array_condition_and_valid_controls(self):
        self.validate(PARTIAL)
        self.validate(source('if(0) g(); else if(1) g(); else g(); '
                             'while(0) g(); do { g(); } while(0);'))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceBranchCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_condition_branch_and_loop_counts(self):
        messages = {
            'InvalidArgumentCount': 'Incorrect argument count.',
            'NonScalarCondition': 'The condition must be a scalar type',
            'UnknownIntrinsicFunction': 'Unknown intrinsic function',
        }
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                for code, message in messages.items():
                    self.assertEqual(output.count('ERROR:' + message), expected.count(code), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_partial_array_condition_and_valid_controls(self):
        for text in (PARTIAL, source('if(0) g(); else if(1) g(); else g(); '
                                    'while(0) g(); do { g(); } while(0);')):
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertNotIn('ERROR:', output)
