"""Unary operators preserve child, target and operator diagnostics/results."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


CASES = [('h(' + op + 'g(0),0);', ['InvalidArgumentCount', 'InvalidOperationType'])
         for op in ('!', '+', '-', '~')]
CASES += [(expr + ';', ['InvalidArgumentCount', 'InvalidAssignmentTarget', 'InvalidOperationType'])
          for expr in ('++g(0)', '--g(0)', 'g(0)++', 'g(0)--')]
CASES += [
    ('const int x=1; h(++x,0);', ['InvalidAssignmentTarget']),
    ('int x[2]; x++;', ['InvalidOperationType']),
    ('int x[2]; h(++x[g(0)],0);', ['InvalidArgumentCount', 'InvalidIndexType']),
    ('h(!offsetof(int),0);', ['UnknownIntrinsicFunction']),
    ('int x=1; h(-x,0);', ['InvalidArgumentType']),
]


def source(body):
    return ('Core C { functions { void g() {} void h(int a,int b) {} '
            'void f() { ' + body + ' } } }')


def partial(expression):
    return ('InstructionSet I { architectural_state { int N; } functions { '
            'void f() { int a[N]; ' + expression + '; } } }')


READONLY_TARGETS = [
    ('register const unsigned<8> R;', 'R'),
    ('register const unsigned<8> R;', 'R[3:0]'),
    ('register const unsigned<8> R[2];', 'R[0]'),
    ('extern const unsigned<8> M[256];', 'M[0]'),
]


def readonly_source(declaration, target, operator, postfix):
    expression = target + operator if postfix else operator + target
    return ('Core C { architectural_state { ' + declaration +
            ' } functions { void f() { ' + expression + '; } } }')


class SourceUnaryCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_unary_diagnostic_order_and_result_types(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_unary_operators(self):
        self.validate(source('signed<8> x=1; h(!x,+x); h(-x,~x); ++x; x--;'))

    def test_partial_prefix_and_postfix_guard(self):
        for expression in ('++bitsizeof(a)', 'bitsizeof(a)++'):
            with self.subTest(expression=expression):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(partial(expression))
                self.assertEqual(codes(caught.exception), ['InvalidAssignmentTarget'])

    def test_readonly_architectural_targets_for_all_increment_forms(self):
        for declaration, target in READONLY_TARGETS:
            for operator, postfix in (('++', False), ('++', True), ('--', False), ('--', True)):
                with self.subTest(target=target, operator=operator, postfix=postfix):
                    with self.assertRaises(M2ValidationError) as caught:
                        self.validate(readonly_source(declaration, target, operator, postfix))
                    self.assertEqual(codes(caught.exception), ['InvalidAssignmentTarget'])


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceUnaryCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_unary_diagnostic_counts(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                for code, message in (
                    ('InvalidArgumentCount', 'Incorrect argument count.'),
                    ('InvalidArgumentType', 'Cannot implicitly convert'),
                    ('InvalidIndexType', 'Index must have an integer type'),
                    ('UnknownIntrinsicFunction', 'Unknown intrinsic function')):
                    self.assertEqual(output.count('ERROR:' + message), expected.count(code), output)
                targets = output.count('ERROR:Invalid assignment target') + output.count('ERROR:Cannot assign to constant')
                self.assertEqual(targets, expected.count('InvalidAssignmentTarget'), output)
                operations = sum(output.count('ERROR:' + message) for message in (
                    'Logical not is only valid on scalar types', 'Unary plus is only valid on integer types',
                    'Unary minus is only valid on integer types', 'Bitwise negation is only valid on integer types',
                    'Increment and decrement operators are only valid on integer types'))
                self.assertEqual(operations, expected.count('InvalidOperationType'), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_unary_operators(self):
        output, _ = self.probe(source('signed<8> x=1; h(!x,+x); h(-x,~x); ++x; x--;'))
        self.assertNotIn('ERROR:', output)

    def test_release_readonly_architectural_targets(self):
        for (declaration, target), (operator, postfix) in zip(
                READONLY_TARGETS, (('++', False), ('++', True), ('--', False), ('--', True))):
            with self.subTest(target=target, operator=operator, postfix=postfix):
                output, _ = self.probe(readonly_source(declaration, target, operator, postfix))
                self.assertEqual(output.count('ERROR:Cannot assign to constant'), 1, output)
                self.assertEqual(output.count('ERROR:'), 1, output)

    def test_release_partial_prefix_and_postfix_guard(self):
        for expression, count in (('++bitsizeof(a)', 1), ('bitsizeof(a)++', 1)):
            with self.subTest(expression=expression):
                output, _ = self.probe(partial(expression))
                self.assertEqual(output.count('ERROR:Invalid assignment target'), count, output)
                self.assertEqual(output.count('ERROR:'), count, output)
