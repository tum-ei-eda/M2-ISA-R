"""Native and release-oracle tests for ISA elaboration, aliases and lists."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.warnings import WarningsInfo


def state(text):
    return 'Core C { architectural_state { ' + text + ' } }'


ERRORS = [
    ('InvalidIsaParameterAssignmentExpression', 'Only assignment expressions', state('int N = 1; N + 1;')),
    ('InvalidIsaParameterAssignmentOperator', 'Only regular assignments', state('int N = 1; N += 1;')),
    ('InvalidIsaParameterAssignmentTarget', 'non-constant ISA parameter', state('const int N = 1; N = 2;')),
    ('InvalidIsaParameterAssignmentTarget', 'non-constant ISA parameter', state('register int R; R = 1;')),
    ('UnassignedIsaParameter', 'ISA parameters are never assigned', state('int N;')),
    ('MultipleIdenticalProvides', 'multiple times', 'InstructionSet A {} Core C provides A, A {}'),
    ('DuplicateIsaStateElement', 'already been declared', state('register int R; register int R;')),
    ('MismatchingIsaStateElementSignatures', 'mismatching signatures', 'InstructionSet A { architectural_state { int N = 1; } } InstructionSet B { architectural_state { unsigned int N = 1; } } Core C provides A, B {}'),
    ('InvalidAliasSource', 'storage class param', state('int N = 1; int &A = N;')),
    ('InvalidAliasSource', 'Alias source must be an identifier', state('unsigned<1> &A = 1;')),
    ('InvalidAliasSource', 'Alias source must be an identifier', state('register int R; int &A = (R);')),
    ('InvalidAliasConstness', 'non-const alias to const item', state('register const unsigned<8> R; unsigned<8> &A = R;')),
    ('InvalidAssignmentType', 'exactly the same type', state('register unsigned<8> R; unsigned<16> &A = R[3:0];')),
    ('InvalidListInitializer', 'Cannot use list initializer', 'Core C { functions { void f() { int x = {1}; } } }'),
    ('InvalidAssignmentType', 'List initializer size does not match', 'Core C { functions { void f() { int x[2] = {1}; } } }'),
    ('InvalidAssignmentType', 'Cannot implicitly convert', 'Core C { functions { void f() { unsigned<1> x[1] = {2}; } } }'),
    ('UnsupportedLanguageFeature', 'Nested list initializers are unsupported', 'Core C { functions { void f() { int x[1][1] = {{1}}; } } }'),
    ('InvalidConstantExpressionNode', 'is not allowed in constant expression', 'Core C { functions { void f() { int x[+1]; } } }'),
    ('InvalidConstantExpressionNode', 'is not allowed in constant expression', 'Core C { functions { void f() { int x[~1]; } } }'),
    ('UnsupportedLanguageFeature', 'unsupported in constant expressions', 'Core C { functions { void f() { int x[3%2]; } } }'),
]

WARNINGS = [
    ('IndexOutOfRange', 'index-out-of-range', 'Index out of range', state('register unsigned<8> R[2]; unsigned<8> &A = R[2];')),
    ('IndexOutOfRange', 'index-out-of-range', 'Index out of range', state('register unsigned<8> R[2]; unsigned<8> &A = R[-1];')),
    ('DuplicateIsaStateElement', 'duplicate-isa-state-element', 'has been declared multiple times', 'InstructionSet A { architectural_state { int N = 1; } } InstructionSet B { architectural_state { int N = 2; } } Core C provides A, B {}'),
]

POSITIVES = [
    state('register unsigned<8> R; unsigned<8> &A = R;'),
    state('register const unsigned<8> R; const unsigned<8> &A = R;'),
    state('register unsigned<8> R; unsigned<8> &A = R[7:0];'),
    state('register unsigned<8> R[8]; unsigned<8> &A[4] = R[3:0];'),
    state('register int R; int &A = R; int &B = A;'),
    'Core C { functions { void f() { int x[2] = {1,2}; } } }',
    'InstructionSet A { architectural_state { int W; } } Core C provides A { architectural_state { W = 8; } }',
    state('register unsigned<8> CSR[4096]; CSR[0] = 11;'),
]


class IsaAliasNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_errors(self):
        for issue, _, source in ERRORS:
            with self.subTest(issue=issue, source=source):
                self.error(source, issue)

    def test_warnings(self):
        for issue, _, _, source in WARNINGS:
            with self.subTest(issue=issue), self.assertLogs('validate_source') as logs:
                self.validate(source)
            self.assertTrue(any('com.minres.coredsl.' + issue in line for line in logs.output))

    def test_positives(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                self.validate(source)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class IsaAliasOracleTest(unittest.TestCase):
    def probe(self, source, allow_internal_error=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'isa_alias.core_desc'
            path.write_text(source)
            result = subprocess.run(['java', '-jar', os.environ['COREDSL_VALIDATOR_JAR'], '-v', str(path)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=30, check=False)
            if not allow_internal_error:
                self.assertNotIn('internal error', result.stdout.lower(), result.stdout)
            return result.stdout, make_parser(path).description_content()

    def test_errors(self):
        for issue, message, source in ERRORS:
            with self.subTest(issue=issue, source=source):
                output, tree = self.probe(source)
                self.assertIn('ERROR:', output, output)
                self.assertIn(message, output, output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)

    def test_warnings(self):
        for issue, name, message, source in WARNINGS:
            with self.subTest(issue=issue, source=source):
                output, tree = self.probe(source)
                self.assertNotIn('ERROR:', output, output)
                self.assertIn('WARNING:', output, output)
                self.assertIn(message, output, output)
                with self.assertLogs('validate_source') as logs:
                    validate_source(tree, WarningsInfo())
                self.assertTrue(any('com.minres.coredsl.' + issue in line for line in logs.output))
                with self.assertNoLogs('validate_source', level='WARNING'):
                    validate_source(tree, WarningsInfo(disabled={name}))

    def test_positives(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertNotIn('ERROR:', output, output)
                validate_source(tree, WarningsInfo())

    def test_reference_limits(self):
        source = state('extern int M[4]; M[0] = 1;')
        output, tree = self.probe(source, allow_internal_error=True)
        self.assertIn('NullPointerException', output)
        with self.assertRaises(M2ValidationError) as exc:
            validate_source(tree, WarningsInfo())
        self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidIsaParameterAssignmentTarget')
        output, tree = self.probe(state('int A = B; int B = A;'))
        self.assertIn("Couldn't resolve reference to NamedEntity 'B'", output)
        with self.assertRaises(M2ValidationError) as exc:
            validate_source(tree, WarningsInfo())
        self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking')
        self.assertEqual(output.count('ERROR:'), 1, output)
