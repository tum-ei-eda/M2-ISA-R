"""Differential checks for source types and ISA-parameter environments."""
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.warnings import WarningsInfo


def core(sections):
    return 'Core C { ' + sections + ' }'


ERRORS = [
    ('InvalidArgumentCount', 'Incorrect argument count.', core('functions { void f(int x) {} void g() { f(); } }')),
    ('InvalidArgumentType', 'Cannot implicitly convert', core('functions { void f(unsigned<8> x) {} void g() { int x; f(x); } }')),
    ('InvalidFunction', 'Expected a function name', core('functions { void f() { int x; x(); } }')),
    ('ReferenceToFunction', 'Function used like a variable', core('functions { void f() {} void g() { int x = f; } }')),
    ('ReturnTypeNotConvertible', 'Cannot convert from', core('functions { unsigned<8> f(int x) { return x; } }')),
    ('ReturnTypeNotConvertible', 'Cannot convert from', core('functions { signed<1> f() { return 1; } }')),
    ('InvalidAssignmentType', 'Cannot implicitly convert', core('functions { void f() { int x; unsigned<8> y = x; } }')),
    ('InvalidAssignmentType', 'Cannot implicitly convert', core('functions { void f() { unsigned<8> x = 256; } }')),
    ('InvalidAssignmentTarget', 'Cannot assign to constant', core('functions { void f() { const int x = 1; x = 2; } }')),
    ('InvalidAssignmentTarget', 'Cannot assign to constant', core('architectural_state { int x = 1; } functions { void f() { x = 2; } }')),
    ('NonScalarCondition', 'The condition must be a scalar type', core('functions { void f() { int x[2]; if(x) {} } }')),
    ('SwitchConditionTypeInvalid', 'The switch condition must be an integer expression', core('functions { void f() { int x[2]; switch(x) {} } }')),
    ('InvalidCast', 'Cannot apply signedness cast to non-integer value', core('functions { void f() { int x[2]; int y = (signed)x; } }')),
    ('NonIndexableExpression', 'Cannot index into', core('functions { void g() {} void f() { int x = g()[0]; } }')),
    ('InvalidIndexType', 'Index must have an integer type', core('functions { void f() { int x[2]; int y[2]; int z = x[y]; } }')),
    ('InvalidRangePattern', 'Invalid range pattern', core('functions { void f() { unsigned<8> x; int a; int b; int z = x[a:b]; } }')),
    ('InvalidOperationType', 'Addition is only valid on integer types', core('functions { void f() { int x[2]; int y = x + 1; } }')),
    ('IncompatibleOptionTypes', 'Incompatible option types:', core('functions { void f() { int x[2]; int y = 1 ? x : 0; } }')),
    ('InvalidIntegerTypeSize', 'Integer type size must be greater than 0', core('architectural_state { int W = 0; } functions { void f() { unsigned<W> x; } }')),
    ('InvalidArraySize', 'Negative array size is invalid', core('architectural_state { int N = -1; } functions { void f() { int x[N]; } }')),
    ('InvalidConstantExpressionIdentifier', 'Identifiers in constant expressions may only refer', core('functions { void f() { const int N = 1; int x[N]; } }')),
    ('SwitchDuplicateCaseSection', 'Multiple case sections with condition', core('functions { void f() { switch(1) { case 1: break; case 1: break; } } }')),
    ('SwitchCaseConditionOutOfRange', 'can not be represented by condition type', core('functions { void f(unsigned<1> x) { switch(x) { case 2: break; } } }')),
]

POSITIVES = [
    core('functions { void f(unsigned<8> x) {} void g() { f(1); } }'),
    core("functions { void f(unsigned<8> x) {} void g() { f(16'h01); } }"),
    core('functions { void f() { unsigned<8> x; int a; unsigned<4> y = x[a:a+3]; } }'),
    core('architectural_state { int N = 8; } functions { void f() { { int N; } unsigned<N> x; } }'),
    'InstructionSet A { architectural_state { int W; } functions { void f() { unsigned<W> x; } } } Core C provides A { architectural_state { W = 8; } }',
]


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class SemanticParityTest(unittest.TestCase):
    def probe(self, source, strict=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'semantic.core_desc'
            path.write_text(source)
            command = ['java'] + (['-Dstrict=true'] if strict else [])
            command += ['-jar', os.environ['COREDSL_VALIDATOR_JAR'], '-v', str(path)]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=30, check=False)
            self.assertNotIn('internal error', result.stdout.lower(), result.stdout)
            tree = make_parser(path).description_content()
            return result.stdout, tree

    def test_error_cases(self):
        for issue, message, source in ERRORS:
            with self.subTest(issue=issue, source=source):
                oracle, tree = self.probe(source)
                self.assertIn('ERROR:', oracle, oracle)
                self.assertIn(message, oracle, oracle)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)

    def test_positive_cases(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                oracle, tree = self.probe(source)
                self.assertNotIn('ERROR:', oracle, oracle)
                validate_source(tree, WarningsInfo())

    def test_identity_cast_modes(self):
        source = core('functions { void f() { int x; int y = (signed)x; } }')
        oracle, tree = self.probe(source)
        self.assertNotIn('Identity cast', oracle)
        with self.assertNoLogs('validate_source', level=logging.WARNING):
            validate_source(tree, WarningsInfo())
        oracle, tree = self.probe(source, strict=True)
        self.assertIn('WARNING:Identity cast does nothing', oracle, oracle)
        with self.assertLogs('validate_source', level=logging.WARNING) as logs:
            validate_source(tree, WarningsInfo(enabled={'identity-cast'}))
        self.assertTrue(any('com.minres.coredsl.IdentityCast' in line for line in logs.output))

    def test_followup_cases(self):
        source = core('architectural_state { int W = 8; } functions { unsigned<W> f() { return 1; } void g() { int W; unsigned<8> y = f(); } }')
        oracle, tree = self.probe(source)
        self.assertNotIn('ERROR:', oracle, oracle)
        validate_source(tree, WarningsInfo())
        source = core("architectural_state { int W = 16; } instructions [[expected_encoding_size(W)]] { I { encoding: 8'h01; behavior: {} } }")
        oracle, tree = self.probe(source)
        self.assertIn('WARNING:Expected an encoding size of 16, but got 8', oracle, oracle)
        with self.assertLogs('validate_source') as logs:
            validate_source(tree, WarningsInfo())
        self.assertTrue(any('UnexpectedInstructionSize' in line for line in logs.output))
        for source in (
            core('functions { void f() { signed<1> x = 0; } }'),
            core('architectural_state { extern unsigned<8> RES[16]; } functions { void f() { unsigned<8> offs; RES[offs+3:offs] = -1; } }'),
        ):
            oracle, tree = self.probe(source)
            self.assertIn('ERROR:Cannot implicitly convert', oracle, oracle)
            with self.assertRaises(M2ValidationError) as exc:
                validate_source(tree, WarningsInfo())
            self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidAssignmentType')
