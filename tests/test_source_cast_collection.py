"""Source casts retain child diagnostics and explicit result types."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError
from m2isar.warnings import WarningsInfo
import test_semantic_parity as semantic_harness

CASES = [
    ('h((int)g(0));', ['InvalidArgumentCount', 'InvalidCast']),
    ('h((signed)g(0));', ['InvalidArgumentCount', 'InvalidCast']),
    ('h((unsigned<33>)g(0));', ['InvalidArgumentCount', 'InvalidCast', 'InvalidArgumentType']),
    ('h((unsigned<33>)offsetof(int));', ['UnknownIntrinsicFunction', 'InvalidArgumentType']),
    ('h((int)offsetof(int));', ['UnknownIntrinsicFunction']),
    ('h((unsigned)(unsigned<33>)g(0));', ['InvalidArgumentCount', 'InvalidCast', 'InvalidArgumentType']),
    ('unsigned<8> x=1; h((signed)(x=g(0)));', ['InvalidArgumentCount', 'InvalidAssignmentType']),
    ('h((unsigned<33>)g());', ['InvalidCast', 'InvalidArgumentType']),
]

IDENTITY = ('Core C { functions { int k() { return 1; } void h(int x) {} '
            'void f() { h((signed)k(0)); } } }')


def source(body, partial=False):
    prefix = 'InstructionSet I { architectural_state { int N; }' if partial else 'Core C {'
    return prefix + ' functions { void g() {} void h(int x) {} void f() { ' + body + ' } } }'


class SourceCastCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_diagnostic_order_and_retained_types(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_partial_incomplete_array_casts(self):
        for cast in ('signed', 'int'):
            with self.subTest(cast=cast):
                self.validate(source('int a[N]; int x=(' + cast + ')a;', partial=True))

    def test_valid_integer_casts(self):
        self.validate(source('signed<8> x=1; h((unsigned)x); h((int)x);'))

    def test_identity_warning_retained_after_child_error(self):
        with self.assertLogs('validate_source') as logs:
            with self.assertRaises(M2ValidationError) as caught:
                self.validate(IDENTITY, WarningsInfo(enabled={'identity-cast'}))
        self.assertEqual(codes(caught.exception), ['InvalidArgumentCount'])
        self.assertEqual(sum('com.minres.coredsl.IdentityCast' in line for line in logs.output), 1)
        with self.assertNoLogs('validate_source', level='WARNING'):
            with self.assertRaises(M2ValidationError):
                self.validate(IDENTITY)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceCastCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_diagnostic_counts(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                self.assertEqual(output.count('ERROR:Incorrect argument count.'),
                                 expected.count('InvalidArgumentCount'), output)
                cast_errors = output.count('ERROR:Cannot cast from') + output.count('ERROR:Cannot apply signedness cast')
                self.assertEqual(cast_errors, expected.count('InvalidCast'), output)
                self.assertEqual(output.count('ERROR:Cannot implicitly convert'),
                                 expected.count('InvalidArgumentType') + expected.count('InvalidAssignmentType'), output)
                self.assertEqual(output.count('ERROR:Unknown intrinsic function'),
                                 expected.count('UnknownIntrinsicFunction'), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_and_partial_casts(self):
        texts = [source('signed<8> x=1; h((unsigned)x); h((int)x);')]
        texts += [source('int a[N]; int x=(' + cast + ')a;', partial=True) for cast in ('signed', 'int')]
        for text in texts:
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertEqual(output.count('ERROR:'), 0, output)

    def test_release_identity_warning_retained_after_child_error(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                output, _ = semantic_harness.SemanticParityTest().probe(IDENTITY, strict=strict)
                self.assertEqual(output.count('ERROR:Incorrect argument count.'), 1, output)
                self.assertEqual(output.count('ERROR:'), 1, output)
                self.assertEqual(output.count('WARNING:Identity cast does nothing'), int(strict), output)
