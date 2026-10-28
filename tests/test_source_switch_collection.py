"""Switches retain condition, label and body diagnostics in section order."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

C = 'InvalidArgumentCount'
S = 'SwitchConditionTypeInvalid'
R = 'SwitchCaseConditionOutOfRange'
D = 'SwitchDuplicateCaseSection'
M = 'SwitchMultipleDefaultSections'
CASES = [
    ('switch(g(0)) { case 1: g(1); break; default: g(2); }', [C, S, R, C, C]),
    ('switch(1) { case 2: g(0); break; case 2: g(1); break; default: g(2); default: g(3); }',
     [R, C, D, R, C, C, M, C]),
    ('switch(1) { case g(): g(0); break; }', ['InvalidConstantExpressionNode', C]),
    ('switch(1) { default: break; default: break; default: break; }', [M, M]),
    ('switch(1) { default: g(0); default: default: }', [C, M, M]),
    ('switch(1) { case 2: g(0); break; case 2: }', [R, C, D, R]),
    ('switch(offsetof(int)) { case 1: g(0); break; }', ['UnknownIntrinsicFunction', S, C]),
    ('switch(1) { case 1/0: g(0); break; case 1/0: g(1); }', ['DivisionByZero', C, 'DivisionByZero', C]),
    ('switch(1) { default: switch(1) { default: break; default: break; } default: break; }', [M, M]),
]


def source(body, partial=False):
    prefix = 'InstructionSet I { architectural_state { int N; }' if partial else 'Core C {'
    return prefix + ' functions { void g() {} void f() { ' + body + ' } } }'


PARTIAL = source('int a[N]; switch(a) { case 1: break; }', partial=True)
VALID = source('switch(1) { case 0: case 1: g(); break; default: g(); }')


class SourceSwitchCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_diagnostic_order_across_sections(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_partial_error_condition_does_not_invent_range_errors(self):
        with self.assertRaises(M2ValidationError) as caught:
            self.validate(PARTIAL)
        self.assertEqual(codes(caught.exception), [S])

    def test_valid_sections_and_partial_case_value(self):
        self.validate(VALID)
        self.validate(source('switch(1) { case N: break; default: g(); }', partial=True))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceSwitchCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_diagnostic_counts(self):
        for body, expected in CASES + [(None, [S])]:
            with self.subTest(body=body):
                output, _ = self.probe(PARTIAL if body is None else source(body))
                for issue, message in (
                    (C, 'Incorrect argument count.'), (S, 'The switch condition must be an integer expression'),
                    (D, 'Multiple case sections with condition'), (M, 'Multiple default sections'),
                    ('InvalidConstantExpressionNode', 'FunctionCallExpression is not allowed in constant expression'),
                    ('DivisionByZero', 'Division by zero'), ('UnknownIntrinsicFunction', 'Unknown intrinsic function')):
                    self.assertEqual(output.count('ERROR:' + message), expected.count(issue), output)
                self.assertEqual(sum('ERROR:The value ' in line and 'can not be represented' in line
                                     for line in output.splitlines()), expected.count(R), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_sections(self):
        for text in (VALID, source('switch(1) { case N: break; default: g(); }', partial=True)):
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertEqual(output.count('ERROR:'), 0, output)
