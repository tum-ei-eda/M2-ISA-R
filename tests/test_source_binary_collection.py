"""Binary expressions recover both operands and retain boolean operator results."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


CASES = [
    ('int x=g(0)+g(1);', ['InvalidArgumentCount'] * 2 + ['InvalidOperationType']),
    ('int x=g(0)*g(1);', ['InvalidArgumentCount'] * 2 + ['InvalidOperationType']),
    ('int x=offsetof(int)+g(0);', ['UnknownIntrinsicFunction', 'InvalidArgumentCount']),
    ('int x=g(0)+offsetof(int);', ['InvalidArgumentCount', 'UnknownIntrinsicFunction']),
    ('h(g(0)==g(1),0);', ['InvalidArgumentCount'] * 2),
    ('h(g(0)==1,0);', ['InvalidArgumentCount', 'InvalidOperationType']),
    ('h(g(0)!=1,0);', ['InvalidArgumentCount', 'InvalidOperationType']),
] + [('h(g(0)' + op + 'g(1),0);', ['InvalidArgumentCount'] * 2 + ['InvalidOperationType'])
     for op in ('&&', '||', '<', '<=', '>', '>=')]



def source(body):
    return ('Core C { functions { void g() {} void h(int a,int b) {} '
            'void f() { ' + body + ' } } }')


class SourceBinaryCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_binary_operand_and_operator_error_order(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_binary_expressions(self):
        self.validate(source('int x=1+2; h(x<4,1&&1);'))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceBinaryCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_binary_diagnostic_counts(self):
        messages = {
            'InvalidArgumentCount': 'Incorrect argument count.',
            'InvalidFunction': 'Expected a function name',
            'InvalidArgumentType': 'Cannot implicitly convert',
            'UnknownIntrinsicFunction': 'Unknown intrinsic function',
        }
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                for code, message in messages.items():
                    self.assertEqual(output.count('ERROR:' + message), expected.count(code), output)
                operation_errors = sum(output.count('ERROR:' + message) for message in (
                    'Addition is only valid on integer types',
                    'Multiplication is only valid on integer types',
                    'Logical operators are only valid on scalar types',
                    'Magnitude comparisons are only valid on integer types',
                    'Equality comparisons are only valid on integer types or two operands of the same type'))
                self.assertEqual(operation_errors, expected.count('InvalidOperationType'), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_binary_expressions(self):
        output, _ = self.probe(source('int x=1+2; h(x<4,1&&1);'))
        self.assertNotIn('ERROR:', output)
