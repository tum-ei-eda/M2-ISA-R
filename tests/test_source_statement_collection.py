"""Expression diagnostics precede statement checks; for parts are independent."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as source_helpers
from m2isar.diagnostics import M2ValidationError


ACCESS = 'g(0)[g(0):g(0)]'
ACCESS_CODES = ['InvalidArgumentCount', 'InvalidArgumentCount',
                'NonIndexableExpression', 'InvalidIndexType',
                'InvalidArgumentCount', 'InvalidIndexType',
                'InvalidRangePattern', 'InvalidStatementExpression']
CASES = [
    (ACCESS + ';', ACCESS_CODES),
    ('for(' + ACCESS + ';1;' + ACCESS + ') { g(0); }',
     ACCESS_CODES * 2 + ['InvalidArgumentCount']),
    ('for(1;g();2,3) {}', ['InvalidStatementExpression', 'NonScalarCondition',
                         'InvalidStatementExpression', 'InvalidStatementExpression']),
    ('g(0); g(1);', ['InvalidArgumentCount'] * 2),
    ('{ int x[2]; g(0); } int x; x=0; g(1);', ['InvalidArgumentCount'] * 2),
    ('int x=g(); x=0; g(0);', ['InvalidAssignmentType', 'InvalidArgumentCount']),
    ('int x=g(),y=g(); x=y; g(0);',
     ['InvalidAssignmentType', 'InvalidAssignmentType', 'InvalidArgumentCount']),
    ('for(int x=g(),y=g();g();g(0),g(1)) { g(2); g(3); } g(4);',
     ['InvalidAssignmentType', 'InvalidAssignmentType', 'NonScalarCondition']
     + ['InvalidArgumentCount'] * 5),
]


def source(body):
    return 'Core C { functions { void g() {} void f() { ' + body + ' } } }'


def codes(error):
    return [error.issue_code.split('.')[-1]] + [
        code for child in error.related_diagnostics for code in codes(child)]


class SourceStatementCollectionNativeTest(unittest.TestCase):
    validate = source_helpers.SourceValidatorTest.validate

    def test_expression_and_for_errors_are_collected_in_order(self):
        for body, expected in CASES:
            with self.subTest(body=body), self.assertRaises(M2ValidationError) as caught:
                self.validate(source(body))
            self.assertEqual(codes(caught.exception), expected)

    def test_valid_statements_and_for_loops(self):
        for body in ('g();', 'int x; for(x=0;x<3;x++,g()) { g(); }',
                     'for(int x=0;x<3;x++) { g(); }'):
            with self.subTest(body=body):
                self.validate(source(body))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceStatementCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_expression_and_for_diagnostic_counts(self):
        messages = {
            'InvalidArgumentCount': 'Incorrect argument count.',
            'NonIndexableExpression': 'Cannot index into void',
            'InvalidIndexType': 'Index must have an integer type',
            'InvalidRangePattern': 'Invalid range pattern',
            'InvalidStatementExpression': 'Invalid expression in expression statement',
            'NonScalarCondition': 'The condition must be a scalar type',
            'InvalidAssignmentType': 'Cannot implicitly convert',
        }
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                for code, message in messages.items():
                    self.assertEqual(output.count('ERROR:' + message), expected.count(code), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_statements_and_for_loops(self):
        output, _ = self.probe(source('int x; g(); for(x=0;x<3;x++,g()) { g(); } '
                                      'for(int y=0;y<3;y++) { g(); }'))
        self.assertNotIn('ERROR:', output)
