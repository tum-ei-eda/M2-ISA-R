"""Assignments retain child, target, conversion and compound-operation errors."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


CASES = [
    ('Core', 'int x; x=g(0);', ['InvalidArgumentCount', 'InvalidAssignmentType']),
    ('Core', 'const int x=1; x=g(0);',
     ['InvalidArgumentCount', 'InvalidAssignmentTarget', 'InvalidAssignmentType']),
    ('Core', 'g(0)=g(1);', ['InvalidArgumentCount'] * 2 + ['InvalidAssignmentTarget']),
    ('Core', 'g(0)+=g(1);',
     ['InvalidArgumentCount'] * 2 + ['InvalidAssignmentTarget', 'InvalidOperationType']),
    ('Core', 'int x; x+=offsetof(int);', ['UnknownIntrinsicFunction', 'InvalidOperationType']),
    ('Core', 'int x; h((x=g(0)),0);', ['InvalidArgumentCount', 'InvalidAssignmentType']),
    ('Core', 'int x[2]; x[g(0)]=g(1);',
     ['InvalidArgumentCount', 'InvalidIndexType', 'InvalidArgumentCount', 'InvalidAssignmentType']),
    ('Core', 'int a[2]; int b[2]; a+=b;', ['InvalidOperationType']),
    ('InstructionSet', 'int a[2]; int b[2]; a+=b;', []),
    ('InstructionSet', 'int x; x+=g(0);', ['InvalidArgumentCount', 'InvalidAssignmentType']),
    ('InstructionSet', 'int x[2][N]; x[g(0)]=g(1);',
     ['InvalidArgumentCount', 'InvalidIndexType', 'InvalidArgumentCount']),
]


def source(kind, body):
    state = 'architectural_state { int N; } ' if kind == 'InstructionSet' else ''
    return (kind + ' C { ' + state + 'functions { void g() {} void h(int a,int b) {} '
            'void f() { ' + body + ' } } }')


class SourceAssignmentCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_assignment_diagnostic_order_and_partial_compounds(self):
        for kind, body, expected in CASES:
            with self.subTest(kind=kind, body=body):
                if expected:
                    with self.assertRaises(M2ValidationError) as caught:
                        self.validate(source(kind, body))
                    self.assertEqual(codes(caught.exception), expected)
                else:
                    self.validate(source(kind, body))

    def test_valid_assignment_results(self):
        self.validate(source('Core', 'int x; x=1; x+=2; h((x=3),0);'))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceAssignmentCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_assignment_diagnostic_counts(self):
        for kind, body, expected in CASES:
            with self.subTest(kind=kind, body=body):
                output, _ = self.probe(source(kind, body))
                for code, message in (
                    ('InvalidArgumentCount', 'Incorrect argument count.'),
                    ('InvalidAssignmentType', 'Cannot implicitly convert'),
                    ('InvalidIndexType', 'Index must have an integer type'),
                    ('InvalidOperationType', 'Cannot combine'),
                    ('UnknownIntrinsicFunction', 'Unknown intrinsic function')):
                    self.assertEqual(output.count('ERROR:' + message), expected.count(code), output)
                target_errors = output.count('ERROR:Invalid assignment target') + output.count('ERROR:Cannot assign to constant')
                self.assertEqual(target_errors, expected.count('InvalidAssignmentTarget'), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_assignment_results(self):
        output, _ = self.probe(source('Core', 'int x; x=1; x+=2; h((x=3),0);'))
        self.assertNotIn('ERROR:', output)
