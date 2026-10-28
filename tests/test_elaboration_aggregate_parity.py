"""Compare release aggregate diagnostics and native primary/related errors."""
import os
import unittest
from collections import Counter

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo


VALUE = 'The values of the following state elements could not be determined: N'
TYPE = 'The types of the following state elements could not be determined: R'
INCOMPLETE = 'The types of the following state elements could not be determined because they depend on other indeterminable values: R'
UNABLE = 'Unable to determine array size'
DEPENDENT = 'The values of the following state elements could not be determined because they depend on other indeterminable values: M'
ENUM_VALUE = VALUE[:-1] + 'A'
ENUM_DEPENDENT = DEPENDENT[:-1] + 'A'
ENUM_D = VALUE[:-1] + 'D'
VALUE_BOTH = VALUE + ', M'
INCOMPLETE_BOTH = INCOMPLETE + ', S'
CASES = [
    ('register int R[2][3];', 'MultidimensionalAddressSpace',
     'Multidimensional address spaces are not allowed', []),
    ('register int R[-1][-2];', 'InvalidArraySize',
     'Negative array size is invalid',
     ['Multidimensional address spaces are not allowed', 'Negative array size is invalid', INCOMPLETE]),
    ('extern int R[1/0][2/0];', 'DivisionByZero', 'Division by zero',
     ['Multidimensional address spaces are not allowed', 'Division by zero', INCOMPLETE, UNABLE, UNABLE]),
    ('register int R[-1]; register int S[-2];', 'InvalidArraySize',
     'Negative array size is invalid', ['Negative array size is invalid', INCOMPLETE_BOTH]),
    ('int N=1/0; int M=2/0;', 'DivisionByZero', 'Division by zero', ['Division by zero', VALUE_BOTH]),
    ('enum E { A=1/0, B, D=3, F } register enum E R;', 'DivisionByZero',
     'Division by zero', [ENUM_VALUE]),
    ('int N; enum E { A=N, B, D=3, F } register enum E R;', 'UnassignedIsaParameter',
     'The following ISA parameters are never assigned: N', [ENUM_DEPENDENT, INCOMPLETE]),
    ('int N; enum E { A=N, B, D=1/0, F } register enum E R;', 'UnassignedIsaParameter',
     'The following ISA parameters are never assigned: N', ['Division by zero', ENUM_DEPENDENT, ENUM_D, INCOMPLETE]),
    ('enum E { A=1/0 } register enum E R;', 'DivisionByZero', 'Division by zero', [ENUM_VALUE]),
    ('enum E { A=~1 } register enum E R;', 'InvalidConstantExpressionNode',
     'prefix operator ~ is not allowed in constant expression', [ENUM_VALUE]),
    ('int N; enum E { A=N } register enum E R;', 'UnassignedIsaParameter',
     'The following ISA parameters are never assigned: N', [ENUM_DEPENDENT, INCOMPLETE]),
    ('struct S { unsigned<0> x; } register struct S R;', 'InvalidIntegerTypeSize',
     'Integer type size must be greater than 0', []),
    ('int N; struct S { unsigned<N> x; } register struct S R;', 'UnassignedIsaParameter',
     'The following ISA parameters are never assigned: N', [INCOMPLETE]),
    ('int N; register int R[N];', 'UnassignedIsaParameter',
     'The following ISA parameters are never assigned: N', [INCOMPLETE, UNABLE]),
    ('int N; register unsigned<N> R;', 'UnassignedIsaParameter',
     'The following ISA parameters are never assigned: N', [INCOMPLETE]),
    ('int N; int M=N; register unsigned<M> R;', 'UnassignedIsaParameter',
     'The following ISA parameters are never assigned: N', [DEPENDENT, INCOMPLETE]),
    ('register int R[-1];', 'InvalidArraySize', 'Negative array size is invalid', [INCOMPLETE]),
    ('int N=-1; register int R[N];', 'InvalidArraySize', 'Negative array size is invalid', [INCOMPLETE]),
    ('register int R[1/0];', 'DivisionByZero', 'Division by zero', [INCOMPLETE, UNABLE]),
    ('int N=~1;', 'InvalidConstantExpressionNode',
     'prefix operator ~ is not allowed in constant expression', [VALUE]),
    ('register int R; int N=R;', 'InvalidConstantExpressionIdentifier',
     'Identifiers in constant expressions may only refer to ISA parameters or enum constants', [VALUE]),
    ('int N=5%2;', 'UnsupportedLanguageFeature',
     'Infix expression % is currently unsupported in constant expressions', [VALUE]),
    ('int N=~1; register unsigned<N> R;', 'InvalidConstantExpressionNode',
     'prefix operator ~ is not allowed in constant expression', [VALUE, TYPE]),
    ('int N=1/0;', 'DivisionByZero', 'Division by zero', [VALUE]),
    ('register unsigned<0> R;', 'InvalidIntegerTypeSize',
     'Integer type size must be greater than 0', [TYPE]),
    ('int N=1/0; register unsigned<N> R;', 'DivisionByZero', 'Division by zero', [VALUE, TYPE]),
    ('unsigned<2> N=4;', 'InvalidAssignmentType',
     'Cannot implicitly convert unsigned<3> to unsigned<2>', []),
]


def source(body):
    return 'Core C { architectural_state { ' + body + ' } }'


class ElaborationAggregateNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_zero_length_array_is_not_invalid(self):
        self.validate(source('register int R[0];'))

    def test_primary_diagnostics(self):
        for body, issue, message, summaries in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as exc:
                    self.validate(source(body))
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
                self.assertIn(message, str(exc.exception))
                self.assertEqual(len(exc.exception.related_diagnostics), len(summaries))
                for summary, diagnostic in zip(summaries, exc.exception.related_diagnostics):
                    self.assertIn(summary, str(diagnostic))
                    issue = ('InvalidIsaStateElementValue' if summary in (VALUE, ENUM_VALUE, ENUM_D, VALUE_BOTH) else
                             'MultidimensionalAddressSpace' if summary == 'Multidimensional address spaces are not allowed' else
                             'DivisionByZero' if summary == 'Division by zero' else
                             'IndeterminableIsaStateElementValue' if summary in (DEPENDENT, ENUM_DEPENDENT) else
                             'InvalidArraySize' if summary in (UNABLE, 'Negative array size is invalid') else
                             'IndeterminableIsaStateElementType' if summary in (INCOMPLETE, INCOMPLETE_BOTH) else 'InvalidIsaStateElementType')
                    self.assertEqual(diagnostic.issue_code, 'com.minres.coredsl.' + issue)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class ElaborationAggregateOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_zero_length_array_is_not_invalid(self):
        output, tree = self.probe(source('register int R[0];'))
        self.assertIn('WARNING:Array size is zero', output)
        self.assertNotIn('ERROR:', output, output)
        self.assertNotIn('The types of the following state elements', output)
        validate_source(tree, WarningsInfo())

    def test_release_summaries_and_native_primary(self):
        for body, issue, message, summaries in CASES:
            with self.subTest(body=body):
                output, tree = self.probe(source(body))
                self.assertIn(message, output, output)
                for text, count in Counter([message] + summaries).items():
                    if count > 1:
                        self.assertEqual(output.count('ERROR:' + text + ' (file:'), count, output)
                for summary in summaries:
                    if summary == VALUE_BOTH:
                        prefix = VALUE.rsplit(': ', 1)[0] + ': '
                        aggregate = next(line.split(prefix, 1)[1].split(' (file:', 1)[0]
                                         for line in output.splitlines() if prefix in line)
                        self.assertEqual(set(aggregate.split(', ')), {'N', 'M'}, output)
                    else:
                        self.assertIn(summary, output, output)
                if not summaries:
                    self.assertNotIn('The values of the following state elements', output)
                    self.assertNotIn('The types of the following state elements', output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
                self.assertEqual(len(exc.exception.related_diagnostics), len(summaries))
                for summary in summaries:
                    self.assertIn(summary, str(exc.exception))
