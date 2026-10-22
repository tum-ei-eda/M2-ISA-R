"""Return context and conversion checks survive expression errors."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

C = 'InvalidArgumentCount'
R = 'ReturnTypeNotConvertible'
V = 'ReturnWithValueInVoidFunction'
O = 'ReturnStatementOutsideFunction'
CASES = [
    ('int f() { return g(0); }', [C, R]),
    ('void f() { return g(0); }', [C, V]),
    ('int f() { return (unsigned<33>)g(0); }', [C, 'InvalidCast', R]),
    ('int f() { return (unsigned<33>)offsetof(int); }', ['UnknownIntrinsicFunction', R]),
    ('int f() { return offsetof(int); }', ['UnknownIntrinsicFunction']),
    ('int f() { if(1) return g(0); else return g(1); }', [C, R, C, R]),
    ('void f() { if(1) return g(0); else return g(1); }', [C, V, C, V]),
    ('unsigned<1> f() { return 2; }', [R]),
    ('signed<1> f() { return 0; }', [R]),
    ('int f() { return; }', ['ReturnWithoutValueInNonVoidFunction']),
]


def source(function, partial=False):
    prefix = 'InstructionSet I { architectural_state { int N; }' if partial else 'Core C {'
    return prefix + ' functions { void g() {} ' + function + ' } }'


OUTSIDE = ('Core C { functions { void g() {} } instructions { I { '
           "encoding: 8'h00; behavior: { return g(0); } } } }")
PARTIAL = source('int f() { int a[N]; return a; }', partial=True)
VALID = source('int f() { return 1; } void h() { return; }')


class SourceReturnCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_return_diagnostic_order(self):
        for text, expected in [(source(body), expected) for body, expected in CASES] + [(OUTSIDE, [C, O])]:
            with self.subTest(source=text):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(text)
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_and_incomplete_return_values(self):
        self.validate(VALID)
        self.validate(PARTIAL)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceReturnCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_return_diagnostic_counts(self):
        for text, expected in [(source(body), expected) for body, expected in CASES] + [(OUTSIDE, [C, O])]:
            with self.subTest(source=text):
                output, _ = self.probe(text)
                for issue, message in (
                    (C, 'Incorrect argument count.'), (R, 'Cannot convert from'),
                    (V, 'Void functions may not return a value'), (O, 'Return statement is only valid in a function'),
                    ('ReturnWithoutValueInNonVoidFunction', 'Non-void functions must return a value'),
                    ('InvalidCast', 'Cannot cast from'), ('UnknownIntrinsicFunction', 'Unknown intrinsic function')):
                    self.assertEqual(output.count('ERROR:' + message), expected.count(issue), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_and_incomplete_returns(self):
        for text in (VALID, PARTIAL):
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertEqual(output.count('ERROR:'), 0, output)
