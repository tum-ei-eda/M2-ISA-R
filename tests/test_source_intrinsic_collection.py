"""Intrinsics eagerly retain all argument errors before their own checks."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


CASES = [
    ('int x=bitsizeof(g(0),g(1));', ['InvalidArgumentCount'] * 3),
    ('int x=sizeof(g(0),g(1));', ['InvalidArgumentCount'] * 3),
    ('int x=offsetof(sizeof(),bitsizeof());',
     ['InvalidArgumentCount'] * 2 + ['UnknownIntrinsicFunction']),
    ('int x=__encoding_size(g(0),g(1));', ['InvalidArgumentCount'] * 3),
    ('int x=bitsizeof(g(0));', ['InvalidArgumentCount']),
    ('int x=sizeof(g(0));', ['InvalidArgumentCount']),
    ('h(bitsizeof(g(0)),sizeof(g(1)));', ['InvalidArgumentCount'] * 2),
    ('int x=bitsizeof(offsetof(int));', ['UnknownIntrinsicFunction']),
    ('int x=sizeof(offsetof(int));', ['UnknownIntrinsicFunction']),
]


def source(body):
    return ('Core C { functions { void g() {} void h(int a,int b) {} '
            'void f() { ' + body + ' } } }')


class SourceIntrinsicCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_eager_intrinsic_error_order_and_size_result_recovery(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_intrinsic_sizes(self):
        self.validate(source('int x=bitsizeof(unsigned<8>); '
                             'int y=sizeof(unsigned<16>); h(x,y);'))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceIntrinsicCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_eager_intrinsic_diagnostic_counts(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                argument_errors = sum(output.count('ERROR:' + message) for message in (
                    'Incorrect argument count.', 'bitsizeof expects exactly one argument',
                    'sizeof expects exactly one argument', '__encoding_size expects no arguments'))
                self.assertEqual(argument_errors, expected.count('InvalidArgumentCount'), output)
                self.assertEqual(output.count('ERROR:Unknown intrinsic function'),
                                 expected.count('UnknownIntrinsicFunction'), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_intrinsic_sizes(self):
        output, _ = self.probe(source('int x=bitsizeof(unsigned<8>); '
                                      'int y=sizeof(unsigned<16>); h(x,y);'))
        self.assertNotIn('ERROR:', output)
