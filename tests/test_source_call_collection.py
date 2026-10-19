"""Declared calls skip arguments on bad arity and recover matching arguments."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


CASES = [
    ('g(offsetof(int));', ['InvalidArgumentCount']),
    ('int x; x(offsetof(int));', ['InvalidFunction']),
    ('h(g(),g());', ['InvalidArgumentType'] * 2),
    ('h(g(0),g(0));', ['InvalidArgumentCount', 'InvalidArgumentType'] * 2),
    ('h(offsetof(int),g());', ['UnknownIntrinsicFunction', 'InvalidArgumentType']),
    ('int x=h(g(0),g(0))[0];',
     ['InvalidArgumentCount', 'InvalidArgumentType'] * 2 + ['NonIndexableExpression']),
    ('h(g(),g(),offsetof(int));', ['InvalidArgumentCount']),
    ('h(g(),offsetof(int));', ['InvalidArgumentType', 'UnknownIntrinsicFunction']),
]


def source(body):
    return ('Core C { functions { void g() {} void h(int a,int b) {} '
            'void f() { ' + body + ' } } }')


class SourceCallCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_declared_call_error_order_and_lazy_arguments(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_declared_calls(self):
        self.validate(source('int x=0; g(); h(1,x);'))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceCallCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_declared_call_diagnostic_counts(self):
        messages = {
            'InvalidArgumentCount': 'Incorrect argument count.',
            'InvalidFunction': 'Expected a function name',
            'InvalidArgumentType': 'Cannot implicitly convert',
            'UnknownIntrinsicFunction': 'Unknown intrinsic function',
            'NonIndexableExpression': 'Cannot index into void',
        }
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                for code, message in messages.items():
                    self.assertEqual(output.count('ERROR:' + message), expected.count(code), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_declared_calls(self):
        output, _ = self.probe(source('int x=0; g(); h(1,x);'))
        self.assertNotIn('ERROR:', output)
